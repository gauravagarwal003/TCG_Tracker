#!/usr/bin/env python3
"""
Single-day update script for Pokemon Tracker.

Usage:
    python update_single_day.py 2024-12-15        # Update specific date
    python update_single_day.py                    # Update yesterday (default)
    python update_single_day.py --today            # Update today (may have incomplete data)

This script:
1. Fetches price data for ONLY the specified date
2. Updates daily_tracker.csv with that date's portfolio value
3. Rebuilds the static site
"""

import sys
import os
import argparse
import json
import subprocess
from datetime import datetime, timedelta, date
import pandas as pd
from pathlib import Path

# Import local modules
from functions import batch_update_historical_prices, get_price_for_date, get_product_info_from_ids


def fetch_prices_for_date(target_date: str, product_list: list) -> bool:
    """
    Fetch price data for a single date only.
    Returns True if successful, False otherwise.
    """
    print(f"Fetching prices for {target_date}...")
    
    try:
        # Call batch update with same start and end date = single day
        batch_update_historical_prices(target_date, target_date, product_list)
        return True
    except Exception as e:
        print(f"Error fetching prices: {e}")
        return False


def update_tracker_for_date(target_date: str) -> bool:
    """
    Update daily_tracker.csv with portfolio value for a single date.
    Appends or updates the row for that date.
    """
    print(f"Updating tracker for {target_date}...")
    
    # Load config
    with open("data.json") as f:
        config = json.load(f)
    
    TRANSACTIONS_FILE = config.get("transactions_file", "transactions.csv")
    MAPPINGS_FILE = config.get("mappings_file", "mappings.json")
    
    # Load mappings for names
    name_map = {}
    image_map = {}
    try:
        with open(MAPPINGS_FILE, 'r') as mf:
            m_data = json.load(mf)
            for item in m_data:
                gid = str(item.get('group_id', ''))
                pid = str(item.get('product_id', ''))
                name_map[(gid, pid)] = item.get('name', 'Unknown')
                image_map[(gid, pid)] = item.get('imageUrl', '')
    except Exception as e:
        print(f"Warning: Could not load mappings: {e}")
    
    # Load transactions
    try:
        df = pd.read_csv(TRANSACTIONS_FILE)
    except FileNotFoundError:
        print(f"Error: {TRANSACTIONS_FILE} not found.")
        return False
    
    df['Date Recieved'] = pd.to_datetime(df['Date Recieved'])
    df['Quantity'] = df['Quantity'].fillna(1.0)
    
    def parse_currency(value):
        if pd.isna(value) or value == '':
            return 0.0
        if isinstance(value, str):
            clean = value.replace('$', '').replace(',', '').strip()
            return float(clean) if clean else 0.0
        return float(value)
    
    df['Price Per Unit'] = df['Price Per Unit'].apply(parse_currency)
    df['Total Transaction Value'] = df['Price Per Unit'] * df['Quantity']
    
    # Calculate holdings as of target_date
    target_dt = pd.to_datetime(target_date)
    tx_before = df[df['Date Recieved'] <= target_dt]
    
    holdings = {}
    total_cost_basis = 0.0
    
    for _, row in tx_before.iterrows():
        g_id = str(row.get('group_id', ''))
        p_id = str(row.get('product_id', ''))
        key = (g_id, p_id)
        tx_type = str(row.get('Transaction Type', '')).upper()
        qty = row.get('Quantity', 0)
        price = row.get('Price Per Unit', 0)
        
        if not g_id or not p_id or g_id == 'nan' or p_id == 'nan':
            continue
        
        if key not in holdings:
            holdings[key] = {'qty': 0, 'cost': 0}
        
        if tx_type == 'BUY':
            holdings[key]['qty'] += qty
            holdings[key]['cost'] += qty * price
            total_cost_basis += qty * price
        elif tx_type == 'SELL':
            holdings[key]['qty'] -= qty
            total_cost_basis -= qty * price
        elif tx_type in ['OPEN', 'PULL', 'TRADE']:
            holdings[key]['qty'] -= qty
    
    # Calculate current value using prices for target_date
    total_market_value = 0.0
    for (g_id, p_id), data in holdings.items():
        if data['qty'] > 0:
            # Get categoryId from mappings
            product_info = get_product_info_from_ids(g_id, p_id)
            category_id = 3  # Default to Pokemon
            if product_info and product_info.get('categoryId'):
                category_id = product_info.get('categoryId')
            
            price = get_price_for_date(g_id, p_id, target_date, category_id)
            if price:
                total_market_value += data['qty'] * price
    
    # Count items owned
    items_owned = sum(1 for data in holdings.values() if data['qty'] > 0)
    
    # Create/update daily_tracker.csv
    tracker_file = "daily_tracker.csv"
    if os.path.exists(tracker_file):
        tracker_df = pd.read_csv(tracker_file)
        tracker_df['Date'] = pd.to_datetime(tracker_df['Date']).dt.strftime('%Y-%m-%d')
    else:
        tracker_df = pd.DataFrame(columns=['Date', 'Total Value', 'Cost Basis', 'Items Owned', 'Portfolio Value', 'Gain/Loss', 'Gain/Loss %'])
    
    # Calculate gain/loss
    gain_loss = total_market_value - total_cost_basis
    gain_loss_pct = (gain_loss / total_cost_basis * 100) if total_cost_basis > 0 else 0
    
    new_row = {
        'Date': target_date,
        'Total Value': round(total_market_value, 2),
        'Cost Basis': round(total_cost_basis, 2),
        'Items Owned': items_owned,
        'Portfolio Value': round(total_market_value, 2),
        'Gain/Loss': round(gain_loss, 2),
        'Gain/Loss %': round(gain_loss_pct, 2)
    }
    
    # Remove existing row for this date if present, then append new one
    tracker_df = tracker_df[tracker_df['Date'] != target_date]
    tracker_df = pd.concat([tracker_df, pd.DataFrame([new_row])], ignore_index=True)
    
    # Sort by date and save
    tracker_df['Date'] = pd.to_datetime(tracker_df['Date'])
    tracker_df = tracker_df.sort_values('Date')
    tracker_df['Date'] = tracker_df['Date'].dt.strftime('%Y-%m-%d')
    tracker_df.to_csv(tracker_file, index=False)
    
    print(f"  Portfolio Value: ${total_market_value:,.2f}")
    print(f"  Cost Basis: ${total_cost_basis:,.2f}")
    print(f"  Gain/Loss: ${gain_loss:,.2f} ({gain_loss_pct:.1f}%)")
    
    return True


def update_current_holdings():
    """Update current_holdings.csv based on latest tracker data."""
    print("Updating current holdings...")
    
    with open("data.json") as f:
        config = json.load(f)
    
    TRANSACTIONS_FILE = config.get("transactions_file", "transactions.csv")
    MAPPINGS_FILE = config.get("mappings_file", "mappings.json")
    
    # Load mappings
    name_map = {}
    image_map = {}
    try:
        with open(MAPPINGS_FILE, 'r') as mf:
            m_data = json.load(mf)
            for item in m_data:
                gid = str(item.get('group_id', ''))
                pid = str(item.get('product_id', ''))
                name_map[(gid, pid)] = item.get('name', 'Unknown')
                image_map[(gid, pid)] = item.get('imageUrl', '')
    except Exception:
        pass
    
    # Load transactions
    df = pd.read_csv(TRANSACTIONS_FILE)
    df['Quantity'] = df['Quantity'].fillna(1.0)
    
    def parse_currency(value):
        if pd.isna(value) or value == '':
            return 0.0
        if isinstance(value, str):
            clean = value.replace('$', '').replace(',', '').strip()
            return float(clean) if clean else 0.0
        return float(value)
    
    df['Price Per Unit'] = df['Price Per Unit'].apply(parse_currency)
    
    # Calculate current holdings
    holdings = {}
    for _, row in df.iterrows():
        g_id = str(row.get('group_id', ''))
        p_id = str(row.get('product_id', ''))
        key = (g_id, p_id)
        tx_type = str(row.get('Transaction Type', '')).upper()
        qty = row.get('Quantity', 0)
        
        if not g_id or not p_id or g_id == 'nan' or p_id == 'nan':
            continue
        
        if key not in holdings:
            holdings[key] = 0
        
        if tx_type == 'BUY':
            holdings[key] += qty
        elif tx_type == 'SELL':
            holdings[key] -= qty
        elif tx_type in ['OPEN', 'PULL', 'TRADE']:
            holdings[key] -= qty
    
    # Get latest prices
    tracker_df = pd.read_csv("daily_tracker.csv")
    latest_date = tracker_df['Date'].max()
    
    # Build holdings list
    holdings_list = []
    for (g_id, p_id), qty in holdings.items():
        if qty > 0:
            # Get categoryId from mappings
            product_info = get_product_info_from_ids(g_id, p_id)
            category_id = 3  # Default to Pokemon
            if product_info and product_info.get('categoryId'):
                category_id = product_info.get('categoryId')
            
            price = get_price_for_date(g_id, p_id, latest_date, category_id) or 0
            holdings_list.append({
                'Product Name': name_map.get((g_id, p_id), 'Unknown'),
                'group_id': g_id,
                'product_id': p_id,
                'Quantity': int(qty),
                'Latest Price': price,
                'Total Value': qty * price,
                'Image URL': image_map.get((g_id, p_id), '')
            })
    
    holdings_df = pd.DataFrame(holdings_list)
    holdings_df.to_csv("current_holdings.csv", index=False)
    print(f"  Updated {len(holdings_list)} holdings")


def rebuild_graphs():
    """Rebuild portfolio graphs from daily_tracker.csv."""
    print("Rebuilding graphs...")
    
    if not os.path.exists("daily_tracker.csv"):
        print("  No tracker data, skipping graphs")
        return
    
    import plotly.graph_objects as go
    
    tracker_df = pd.read_csv("daily_tracker.csv")
    tracker_df['Date'] = pd.to_datetime(tracker_df['Date'])
    tracker_df = tracker_df.sort_values('Date')
    
    # Use 'Total Value' column (has all historical data), fall back to 'Portfolio Value'
    value_col = 'Total Value' if 'Total Value' in tracker_df.columns else 'Portfolio Value'
    
    # Calculate Gain/Loss % from Total Value and Cost Basis if not present
    if 'Gain/Loss %' not in tracker_df.columns or tracker_df['Gain/Loss %'].isna().all():
        tracker_df['Gain/Loss %'] = ((tracker_df[value_col] - tracker_df['Cost Basis']) / tracker_df['Cost Basis'] * 100).round(2)
    
    # Portfolio value graph
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=tracker_df['Date'],
        y=tracker_df[value_col],
        mode='lines',
        name='Portfolio Value',
        line=dict(color='#00C851', width=3),
        stackgroup='one'
    ))
    fig.add_trace(go.Scatter(
        x=tracker_df['Date'],
        y=tracker_df['Cost Basis'],
        mode='lines',
        name='Net Investment (Cost Basis)',
        line=dict(color='#ff4444', width=2, dash='dash')
    ))
    fig.update_layout(
        title='Portfolio Value Over Time',
        xaxis_title='Date',
        yaxis_title='Value ($)',
        template='plotly_white',
        hovermode='x unified',
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    fig.write_html("portfolio_graph.html", include_plotlyjs=True, full_html=True)
    
    # Performance graph - calculate from value and cost basis
    gain_loss_pct = ((tracker_df[value_col] - tracker_df['Cost Basis']) / tracker_df['Cost Basis'] * 100)
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=tracker_df['Date'],
        y=gain_loss_pct,
        mode='lines',
        name='Gain/Loss %',
        line=dict(color='#4f46e5', width=3)
    ))
    fig2.add_hline(y=0, line_dash="dot", line_color="#64748b")
    fig2.update_layout(
        title='Portfolio Performance (%)',
        xaxis_title='Date',
        yaxis_title='Gain/Loss (%)',
        template='plotly_white',
        hovermode='x unified',
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    fig2.write_html("performance_graph.html", include_plotlyjs=True, full_html=True)
    
    print("  Graphs rebuilt")


def update_data_json(target_date: str):
    """Update data.json with the latest_date."""
    print("Updating data.json...")
    
    with open("data.json", "r") as f:
        config = json.load(f)
    
    # Only update if this date is newer than current latest_date
    current_latest = config.get("latest_date", "")
    if target_date > current_latest:
        config["latest_date"] = target_date
        with open("data.json", "w") as f:
            json.dump(config, f, indent=4)
        print(f"  Updated latest_date to {target_date}")
    else:
        print(f"  latest_date unchanged ({current_latest})")


def rebuild_site():
    """Rebuild the static site."""
    print("Rebuilding static site...")
    try:
        result = subprocess.run(
            [sys.executable, "build_site.py"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("  Site rebuilt successfully")
        else:
            print(f"  Error: {result.stderr}")
    except Exception as e:
        print(f"  Error rebuilding site: {e}")


def get_product_list() -> list:
    """Get list of products from transactions with categoryId."""
    with open("data.json") as f:
        config = json.load(f)
    
    df = pd.read_csv(config.get("transactions_file", "transactions.csv"))
    df_clean = df[['group_id', 'product_id', 'Item']].dropna(subset=['group_id', 'product_id']).drop_duplicates()
    
    product_list = []
    for _, row in df_clean.iterrows():
        try:
            g_id = int(float(row['group_id']))
            p_id = int(float(row['product_id']))
            
            # Get categoryId from mappings
            product_info = get_product_info_from_ids(g_id, p_id)
            category_id = 3  # Default to Pokemon
            if product_info and product_info.get('categoryId'):
                category_id = product_info.get('categoryId')
            
            product_list.append({
                'group_id': g_id,
                'product_id': p_id,
                'name': row['Item'],
                'categoryId': category_id
            })
        except ValueError:
            continue
    
    return product_list


def update_for_date(target_date: str):
    """
    Main function: Update everything for a single date.
    
    Args:
        target_date: Date string in YYYY-MM-DD format
    """
    print("=" * 50)
    print(f"  POKEMON TRACKER - SINGLE DAY UPDATE")
    print(f"  Target Date: {target_date}")
    print(f"  Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Step 1: Fetch prices for this date
    product_list = get_product_list()
    print(f"\nTracking {len(product_list)} products...")
    
    success = fetch_prices_for_date(target_date, product_list)
    if not success:
        print("Warning: Price fetch may have failed, continuing anyway...")
    
    # Step 2: Update tracker for this date
    update_tracker_for_date(target_date)
    
    # Step 3: Update current holdings
    update_current_holdings()
    
    # Step 4: Update data.json with latest date
    update_data_json(target_date)
    
    # Step 5: Rebuild graphs
    rebuild_graphs()
    
    # Step 6: Rebuild static site
    rebuild_site()
    
    print("\n" + "=" * 50)
    print("  UPDATE COMPLETE")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Update Pokemon Tracker for a single date",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python update_single_day.py                  # Update for yesterday
    python update_single_day.py 2024-12-15       # Update for specific date
    python update_single_day.py --today          # Update for today (may have incomplete data)
    
For backfilling multiple dates, run the script multiple times:
    for d in 2024-12-{10..15}; do python update_single_day.py $d; done
        """
    )
    parser.add_argument(
        'date',
        nargs='?',
        help='Date to update (YYYY-MM-DD format). Defaults to yesterday.'
    )
    parser.add_argument(
        '--today',
        action='store_true',
        help='Use today\'s date instead of yesterday'
    )
    
    args = parser.parse_args()
    
    # Determine target date
    if args.date:
        target_date = args.date
        # Validate date format
        try:
            datetime.strptime(target_date, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid date format '{target_date}'. Use YYYY-MM-DD.")
            sys.exit(1)
    elif args.today:
        target_date = date.today().strftime('%Y-%m-%d')
    else:
        # Default: yesterday (TCGPlayer data has 1-day lag)
        target_date = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    update_for_date(target_date)


if __name__ == "__main__":
    main()
