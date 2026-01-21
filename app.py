from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import pandas as pd
import os
import json
from datetime import datetime
from analyze_portfolio import run_analysis
from functions import MAPPINGS_FILE, TRANSACTIONS_FILE

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flash messages

# Ensure paths are correct
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
            df = df.drop(tx_id)
            df.to_csv(TRANSACTIONS_FILE, index=False)
            flash("Transaction deleted.", "success")
            run_analysis_safe()
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
    new_cat_id = form_data.get('new_category_id')
    new_img = form_data.get('new_image_url')
    new_url = form_data.get('new_product_url')
    
    if new_img and new_url and data['group_id'] and data['product_id']:
        try:
            mappings = []
            if os.path.exists(MAPPINGS_FILE):
                with open(MAPPINGS_FILE, 'r') as f:
                    mappings = json.load(f)
            
            # Check if exists
            pid = str(data['product_id']).strip()
            gid = str(data['group_id']).strip()
            exists = any(str(m.get('product_id')) == pid and str(m.get('group_id')) == gid for m in mappings)
            
            if not exists:
                new_entry = {
                    "product_id": pid,
                    "name": data['Item'],
                    "group_id": gid,
                    "imageUrl": new_img,
                    "categoryId": int(new_cat_id) if new_cat_id else 3,
                    "url": new_url
                }
                mappings.append(new_entry)
                with open(MAPPINGS_FILE, 'w') as f:
                    json.dump(mappings, f, indent=2)
                print(f"Added mapping for {data['Item']}")
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

    if tx_id is not None:
        # Update existing
        for key, value in data.items():
            df.at[tx_id, key] = value
    else:
        # Append new
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)

    df.to_csv(TRANSACTIONS_FILE, index=False)
    run_analysis_safe()

def run_analysis_safe():
    try:
        run_analysis()
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
        "date": "N/A"
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
        except Exception as e:
            print(f"Error reading daily tracker: {e}")

    return jsonify(summary)

if __name__ == '__main__':
    # host='0.0.0.0' allows access from other devices on the network
    app.run(debug=True, port=5001, host='0.0.0.0')
