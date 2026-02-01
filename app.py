from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
import pandas as pd
import os
import json
from datetime import datetime
from functools import wraps
from analyze_portfolio import run_analysis
from functions import MAPPINGS_FILE, TRANSACTIONS_FILE, batch_update_historical_prices
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Change these or use Environment Variables for security
auth_username = os.environ.get('AUTH_USERNAME')
auth_password = os.environ.get('AUTH_PASSWORD')

if not auth_username or not auth_password:
    raise ValueError("No AUTH_USERNAME or AUTH_PASSWORD set for Flask application")

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flash messages

# --- Authentication Helpers ---
def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid."""
    return username == auth_username and password == auth_password

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

# Protect all views by default
@app.before_request
def require_login():
    # Exempt 'static' endpoint so styles/images load on the login prompt if browser implementation varies,
    # though usually browser sends auth header for subresources too. 
    # To be safe and block everything:
    if request.endpoint == 'static': 
        return
        
    auth = request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()

# Make sure paths are correct
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOLDINGS_FILE = os.path.join(BASE_DIR, 'current_holdings.csv')
# TRANSACTIONS_FILE and MAPPINGS_FILE are imported but let's ensure full paths if needed
# Assuming they are in the same dir
if not os.path.isabs(TRANSACTIONS_FILE):
    TRANSACTIONS_FILE = os.path.join(BASE_DIR, TRANSACTIONS_FILE)

@app.route('/')
def index():
    # Load Current Holdings
    holdings = []
    total_value = 0
    if os.path.exists(HOLDINGS_FILE):
        df = pd.read_csv(HOLDINGS_FILE)
        # Convert to dict
        holdings = df.to_dict('records')
        if not df.empty and 'Total Value' in df.columns:
            total_value = df['Total Value'].sum()

    # Read the graph content to embed it
    graph_html = ""
    graph_path = os.path.join(BASE_DIR, 'portfolio_graph.html')
    if os.path.exists(graph_path):
        with open(graph_path, 'r') as f:
            graph_html = f.read()

    performance_html = ""
    perf_path = os.path.join(BASE_DIR, 'performance_graph.html')
    if os.path.exists(perf_path):
        with open(perf_path, 'r') as f:
            performance_html = f.read()

    return render_template('index.html', holdings=holdings, total_value=total_value, graph_html=graph_html, performance_html=performance_html)

@app.route('/transactions')
def transactions():
    if os.path.exists(TRANSACTIONS_FILE):
        df = pd.read_csv(TRANSACTIONS_FILE)
        # Add an index column to identify rows for editing
        df['id'] = df.index
        transactions_list = df.to_dict('records')
    else:
        transactions_list = []
    return render_template('transactions.html', transactions=transactions_list)

@app.route('/transaction/add', methods=['GET', 'POST'])
def add_transaction():
    if request.method == 'POST':
        save_transaction(request.form)
        return redirect(url_for('transactions'))
    
    mappings = []
    if os.path.exists(MAPPINGS_FILE):
        with open(MAPPINGS_FILE, 'r') as f:
            mappings = json.load(f)
            
    return render_template('transaction_form.html', transaction={}, title="Add Transaction", mappings=mappings)

@app.route('/transaction/edit/<int:tx_id>', methods=['GET', 'POST'])
def edit_transaction(tx_id):
    if not os.path.exists(TRANSACTIONS_FILE):
        flash("Transactions file not found.", "error")
        return redirect(url_for('index'))

    df = pd.read_csv(TRANSACTIONS_FILE)
    
    if tx_id not in df.index:
        flash("Transaction not found.", "error")
        return redirect(url_for('transactions'))

    if request.method == 'POST':
        save_transaction(request.form, tx_id)
        return redirect(url_for('transactions'))
    
    mappings = []
    if os.path.exists(MAPPINGS_FILE):
        with open(MAPPINGS_FILE, 'r') as f:
            mappings = json.load(f)

    transaction = df.loc[tx_id].to_dict()
    return render_template('transaction_form.html', transaction=transaction, title="Edit Transaction", mappings=mappings)

@app.route('/transaction/delete/<int:tx_id>', methods=['POST'])
def delete_transaction(tx_id):
    if os.path.exists(TRANSACTIONS_FILE):
        df = pd.read_csv(TRANSACTIONS_FILE)
        if tx_id in df.index:
            # Capture date before deleting to optimize re-analysis
            affected_date = df.at[tx_id, 'Date Recieved']
            
            df = df.drop(tx_id)
            df.to_csv(TRANSACTIONS_FILE, index=False)
            flash("Transaction deleted.", "success")
            run_analysis_safe(resume_date=affected_date)
    return redirect(url_for('transactions'))

@app.route('/refresh')
def refresh_data():
    run_analysis_safe()
    flash("Data refreshed successfully!", "success")
    return redirect(url_for('index'))

def save_transaction(form_data, tx_id=None):
    # Extract data from form
    data = {
        'Date Purchased': form_data.get('date_purchased'),
        'Date Recieved': form_data.get('date_received'),
        'Transaction Type': form_data.get('transaction_type'),
        'Price Per Unit': form_data.get('price_per_unit'),
        'Quantity': form_data.get('quantity'),
        'Item': form_data.get('item'),
        'group_id': form_data.get('group_id'),
        'product_id': form_data.get('product_id'),
        'Method': form_data.get('method'),
        'Place': form_data.get('place'),
        'Notes': form_data.get('notes')
    }

    # --- Save New Mapping if provided ---
    new_pid = form_data.get('new_product_id')
    new_gid = form_data.get('new_group_id')
    new_cat_id = form_data.get('new_category_id')
    
    # If new IDs provided, and we have an Item name
    if new_pid and new_gid and data['Item']:
        # Override data with IDs from the manual section if they were not set correctly via hidden inputs (though JS handles it, it's safer)
        data['product_id'] = new_pid
        data['group_id'] = new_gid
        
        try:
            mappings = []
            if os.path.exists(MAPPINGS_FILE):
                with open(MAPPINGS_FILE, 'r') as f:
                    mappings = json.load(f)
            
            # Check if exists
            pid = str(new_pid).strip()
            gid = str(new_gid).strip()
            exists = any(str(m.get('product_id')) == pid and str(m.get('group_id')) == gid for m in mappings)
            
            if not exists:
                # Generate URLs
                # Image: https://tcgplayer-cdn.tcgplayer.com/product/{product_id}_200w.jpg
                # URL: https://www.tcgplayer.com/product/{product_id}/
                
                generated_img_url = f"https://tcgplayer-cdn.tcgplayer.com/product/{pid}_200w.jpg"
                generated_product_url = f"https://www.tcgplayer.com/product/{pid}/"
                
                new_entry = {
                    "product_id": pid,
                    "name": data['Item'],
                    "group_id": gid,
                    "imageUrl": generated_img_url,
                    "categoryId": int(new_cat_id) if new_cat_id else 3,
                    "url": generated_product_url
                }
                mappings.append(new_entry)
                with open(MAPPINGS_FILE, 'w') as f:
                    json.dump(mappings, f, indent=2)
                print(f"Added new mapping for {data['Item']}")
        except Exception as e:
            print(f"Error saving mapping: {e}")

    # Format currency/numbers
    # Basic cleanup, maybe move to a util
    try:
        if data['Price Per Unit']:
             # simple check, ideally more robust
             if not str(data['Price Per Unit']).startswith('$'):
                 data['Price Per Unit'] = f"${float(data['Price Per Unit']):.2f}"
    except:
        pass

    try:
        if data['Quantity']:
            data['Quantity'] = float(data['Quantity'])
            if data['Quantity'].is_integer():
                data['Quantity'] = int(data['Quantity'])
    except:
        pass

    if os.path.exists(TRANSACTIONS_FILE):
        df = pd.read_csv(TRANSACTIONS_FILE)
    else:
        # Create new DF with appropriate columns if not exists
        columns = ['Date Purchased','Date Recieved','Transaction Type','Price Per Unit','Quantity','Item','group_id','product_id','Method','Place','Notes']
        df = pd.DataFrame(columns=columns)

    # Logic to determine impact date for partial update
    impact_date = data['Date Recieved']
    
    # Check if this is a NEW product (not tracked before)
    # We need to ensure types match for comparison (float vs str)
    # data['product_id'] comes from form as string usually
    is_new_product = False
    try:
        if not df.empty:
            pid_float = float(data['product_id'])
            gid_float = float(data['group_id'])
            # Check if this pair exists already
            exists = ((df['product_id'] == pid_float) & (df['group_id'] == gid_float)).any()
            if not exists:
                is_new_product = True
        else:
            is_new_product = True
    except:
        pass # Ignore type errors, treat as not new to be safe

    if tx_id is not None:
        # Update existing
        # Check if date changed, we need the earlier of the two
        if tx_id in df.index:
            old_date = df.at[tx_id, 'Date Recieved']
            if old_date < impact_date:
                impact_date = old_date
        
        for key, value in data.items():
            df.at[tx_id, key] = value
    else:
        # Append new
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)

    df.to_csv(TRANSACTIONS_FILE, index=False)
    
    # If new product, try to fetch TODAY's price so it's not zero value
    if is_new_product:
        try:
            today_str = datetime.now().strftime('%Y-%m-%d')
            # Only fetch for this one product
            p_list = [{
                'group_id': data['group_id'], 
                'product_id': data['product_id'],
                'name': data['Item']
            }]
            print(f"Fetching initial price for new product: {data['Item']}")
            batch_update_historical_prices(today_str, today_str, p_list)
        except Exception as e:
            print(f"Error fetching initial price: {e}")

    run_analysis_safe(resume_date=impact_date)

def run_analysis_safe(resume_date=None):
    try:
        run_analysis(resume_date=resume_date)
    except Exception as e:
        print(f"Error running analysis: {e}")
        flash(f"Error updating analysis: {e}", "error")

@app.route('/api/summary')
def api_summary():
    summary = {
        "total_value": 0,
        "total_cost": 0,
        "profit": 0,
        "items_owned": 0,
        "date": "N/A",
        "history": [] 
    }

    # Try to read from daily_tracker.csv for the most consistent "latest" entries
    tracker_path = os.path.join(BASE_DIR, 'daily_tracker.csv')
    if os.path.exists(tracker_path):
        try:
            # Using pandas to handle CSV robustly
            df = pd.read_csv(tracker_path)
            if not df.empty:
                last_row = df.iloc[-1]
                summary["total_value"] = float(last_row['Total Value'])
                summary["total_cost"] = float(last_row['Cost Basis'])
                summary["profit"] = summary["total_value"] - summary["total_cost"]
                
                # Check if Items Owned exists (it might be a newer column)
                if 'Items Owned' in df.columns:
                     summary["items_owned"] = int(last_row['Items Owned']) if pd.notna(last_row['Items Owned']) else 0
                
                summary["date"] = str(last_row['Date'])

                # Add last 14 days history for widget graph
                if 'Date' in df.columns and 'Total Value' in df.columns:
                    history_df = df.tail(14)
                    summary["history"] = history_df[['Date', 'Total Value']].to_dict('records')

        except Exception as e:
            print(f"Error reading daily tracker: {e}")

    return jsonify(summary)

if __name__ == '__main__':
    # host='0.0.0.0' allows access from other devices on the network
    app.run(debug=True, port=5001, host='0.0.0.0')
