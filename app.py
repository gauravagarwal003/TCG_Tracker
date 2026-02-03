import os
import json
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSACTIONS_FILE = os.path.join(BASE_DIR, 'transactions.csv')
HOLDINGS_FILE = os.path.join(BASE_DIR, 'current_holdings.csv')
MAPPINGS_FILE = os.path.join(BASE_DIR, 'mappings.json')
PORTFOLIO_GRAPH = os.path.join(BASE_DIR, 'portfolio_graph.html')
PERFORMANCE_GRAPH = os.path.join(BASE_DIR, 'performance_graph.html')


def load_mappings():
    """Load product mappings from JSON file"""
    if os.path.exists(MAPPINGS_FILE):
        with open(MAPPINGS_FILE, 'r') as f:
            return json.load(f)
    return []


def save_mappings(mappings):
    """Save product mappings to JSON file"""
    with open(MAPPINGS_FILE, 'w') as f:
        json.dump(mappings, f, indent=2)


def get_product_from_mappings(product_id, group_id):
    """Get product info from mappings"""
    mappings = load_mappings()
    for mapping in mappings:
        if mapping['product_id'] == str(product_id) and mapping['group_id'] == str(group_id):
            return mapping
    return None


def add_product_to_mappings(name, product_id, group_id, category_id):
    """Add new product to mappings and generate URLs"""
    mappings = load_mappings()
    
    # Check if already exists
    for mapping in mappings:
        if mapping['product_id'] == str(product_id) and mapping['group_id'] == str(group_id):
            return mapping
    
    # Generate URLs
    image_url = f"https://tcgplayer-cdn.tcgplayer.com/product/{product_id}_200w.jpg"
    url = f"https://www.tcgplayer.com/product/{product_id}"
    
    new_mapping = {
        "product_id": str(product_id),
        "name": name,
        "group_id": str(group_id),
        "imageUrl": image_url,
        "categoryId": int(category_id),
        "url": url
    }
    
    mappings.append(new_mapping)
    save_mappings(mappings)
    
    return new_mapping


def load_transactions():
    """Load transactions from CSV"""
    if os.path.exists(TRANSACTIONS_FILE):
        df = pd.read_csv(TRANSACTIONS_FILE)
        df['id'] = df.index
        return df
    return pd.DataFrame()


def save_transactions(df):
    """Save transactions to CSV"""
    # Drop the id column before saving
    df_to_save = df.drop(columns=['id'], errors='ignore')
    df_to_save.to_csv(TRANSACTIONS_FILE, index=False)


def update_config_date():
    """Update data.json to today's date"""
    import json
    from datetime import date
    
    config_file = os.path.join(BASE_DIR, 'data.json')
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    today = date.today().strftime('%Y-%m-%d')
    config['latest_date'] = today
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=4)


def quick_refresh():
    """Quick refresh - only fetch today's prices and recalculate"""
    import subprocess
    
    # Update config to today
    update_config_date()
    
    # Run incremental update
    result = subprocess.run(
        ['python', 'daily_run.py', '--incremental'],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=120
    )
    
    return result.returncode == 0


@app.route('/')
def index():
    """Dashboard page"""
    # Load holdings
    holdings = []
    total_value = 0.0
    if os.path.exists(HOLDINGS_FILE):
        try:
            df = pd.read_csv(HOLDINGS_FILE)
            if not df.empty:
                holdings = df.to_dict('records')
                if 'Total Value' in df.columns:
                    total_value = df['Total Value'].sum()
        except Exception as e:
            flash(f'Error loading holdings: {e}', 'error')
    
    # Load graphs
    graph_html = ""
    if os.path.exists(PORTFOLIO_GRAPH):
        with open(PORTFOLIO_GRAPH, 'r') as f:
            graph_html = f.read()
    
    performance_html = ""
    if os.path.exists(PERFORMANCE_GRAPH):
        with open(PERFORMANCE_GRAPH, 'r') as f:
            performance_html = f.read()
    
    return render_template('index.html',
                         holdings=holdings,
                         total_value=total_value,
                         graph_html=graph_html,
                         performance_html=performance_html,
                         active_page='index')
                         is_static=False)


@app.route('/transactions')
def transactions():
    """Transactions page"""
    df = load_transactions()
    transactions_list = df.to_dict('records') if not df.empty else []
    
    # Add image URLs from mappings
    mappings = load_mappings()
    mappings_dict = {m['product_id']: m.get('imageUrl', '') for m in mappings}
    for tx in transactions_list:
        product_id = str(tx.get('product_id', ''))
        tx['Image URL'] = mappings_dict.get(product_id, '')
    
    return render_template('transactions.html',
                         transactions=transactions_list,
                         is_static=False,
                         active_page='transactions')


@app.route('/transactions/add', methods=['GET', 'POST'])
def add_transaction():
    """Add new transaction"""
    if request.method == 'POST':
        try:
            # Get form data
            product_name = request.form.get('product_name')
            product_id = request.form.get('product_id')
            group_id = request.form.get('group_id')
            category_id = request.form.get('category_id')
            
            # If new product, add to mappings
            if product_id and group_id and category_id:
                add_product_to_mappings(product_name, product_id, group_id, category_id)
            
            # Create transaction record
            transaction = {
                'Date Purchased': request.form.get('date_purchased'),
                'Date Recieved': request.form.get('date_received'),
                'Transaction Type': request.form.get('transaction_type'),
                'Price Per Unit': request.form.get('price_per_unit', ''),
                'Quantity': float(request.form.get('quantity', 0)),
                'Item': product_name,
                'group_id': group_id,
                'product_id': product_id,
                'Method': request.form.get('method', ''),
                'Place': request.form.get('place', ''),
                'Notes': request.form.get('notes', '')
            }
            
            # Load existing transactions and append
            df = load_transactions()
            new_row = pd.DataFrame([transaction])
            df = pd.concat([df, new_row], ignore_index=True)
            
            # Save
            save_transactions(df)
            
            # Trigger smart refresh
            try:
                quick_refresh()
                flash('Transaction added and data updated successfully!', 'success')
            except Exception as e:
                flash(f'Transaction added, but data refresh failed: {e}', 'warning')
            
            return redirect(url_for('transactions'))
            
        except Exception as e:
            flash(f'Error adding transaction: {e}', 'error')
    
    # GET request - show form
    mappings = load_mappings()
    return render_template('transaction_form.html',
                         transaction=None,
                         mappings=mappings,
                         is_edit=False)


@app.route('/transactions/edit/<int:tx_id>', methods=['GET', 'POST'])
def edit_transaction(tx_id):
    """Edit existing transaction"""
    df = load_transactions()
    
    if tx_id >= len(df):
        flash('Transaction not found', 'error')
        return redirect(url_for('transactions'))
    
    if request.method == 'POST':
        try:
            # Get form data
            product_name = request.form.get('product_name')
            product_id = request.form.get('product_id')
            group_id = request.form.get('group_id')
            category_id = request.form.get('category_id')
            
            # If new product, add to mappings
            if product_id and group_id and category_id:
                add_product_to_mappings(product_name, product_id, group_id, category_id)
            
            # Update transaction
            df.at[tx_id, 'Date Purchased'] = request.form.get('date_purchased')
            df.at[tx_id, 'Date Recieved'] = request.form.get('date_received')
            df.at[tx_id, 'Transaction Type'] = request.form.get('transaction_type')
            df.at[tx_id, 'Price Per Unit'] = request.form.get('price_per_unit', '')
            df.at[tx_id, 'Quantity'] = float(request.form.get('quantity', 0))
            df.at[tx_id, 'Item'] = product_name
            df.at[tx_id, 'group_id'] = group_id
            df.at[tx_id, 'product_id'] = product_id
            df.at[tx_id, 'Method'] = request.form.get('method', '')
            df.at[tx_id, 'Place'] = request.form.get('place', '')
            df.at[tx_id, 'Notes'] = request.form.get('notes', '')
            
            # Save
            save_transactions(df)
            
            # Trigger smart refresh
            try:
                quick_refresh()
                flash('Transaction updated and data recalculated successfully!', 'success')
            except Exception as e:
                flash(f'Transaction updated, but data refresh failed: {e}', 'warning')
            
            return redirect(url_for('transactions'))
            
        except Exception as e:
            flash(f'Error updating transaction: {e}', 'error')
    
    # GET request - show form with existing data
    transaction = df.iloc[tx_id].to_dict()
    transaction['id'] = tx_id
    mappings = load_mappings()
    
    return render_template('transaction_form.html',
                         transaction=transaction,
                         mappings=mappings,
                         is_edit=True)


@app.route('/transactions/delete/<int:tx_id>', methods=['POST'])
def delete_transaction(tx_id):
    """Delete transaction"""
    try:
        df = load_transactions()
        
        if tx_id >= len(df):
            flash('Transaction not found', 'error')
            return redirect(url_for('transactions'))
        
        # Drop the row
        df = df.drop(tx_id).reset_index(drop=True)
        
        # Save
        save_transactions(df)
        
        # Trigger smart refresh
        try:
            quick_refresh()
            flash('Transaction deleted and data recalculated successfully!', 'success')
        except Exception as e:
            flash(f'Transaction deleted, but data refresh failed: {e}', 'warning')
    except Exception as e:
        flash(f'Error deleting transaction: {e}', 'error')
    
    return redirect(url_for('transactions'))


@app.route('/api/search_products')
def search_products():
    """API endpoint to search products in mappings"""
    query = request.args.get('q', '').lower()
    mappings = load_mappings()
    
    results = [
        {
            'name': m['name'],
            'product_id': m['product_id'],
            'group_id': m['group_id'],
            'categoryId': m.get('categoryId', 3)
        }
        for m in mappings
        if query in m['name'].lower()
    ]
    
    return jsonify(results[:20])  # Limit to 20 results


@app.route('/refresh_data')
def refresh_data():
    """Refresh portfolio data by running daily_run.py"""
    try:
        if quick_refresh():
            flash('Data refreshed successfully!', 'success')
        else:
            flash('Error refreshing data', 'error')
    except subprocess.TimeoutExpired:
        flash('Refresh timed out. Please try again.', 'error')
    except Exception as e:
        flash(f'Error refreshing data: {e}', 'error')
    
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
