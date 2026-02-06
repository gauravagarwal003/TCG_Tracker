import pandas as pd
import json
import os
import plotly.graph_objects as go
from datetime import datetime, timedelta
from functions import get_price_for_date, get_product_info_from_ids

def _get_latest_price(gid, pid, date_str, category_id=3, max_lookback=7):
    """Search backwards up to max_lookback days to find the most recent price."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    for i in range(max_lookback + 1):
        check = (d - timedelta(days=i)).strftime("%Y-%m-%d")
        price = get_price_for_date(gid, pid, check, category_id)
        if price > 0:
            return price
    return 0.0

def parse_currency(value):
    if pd.isna(value) or value == '':
        return 0.0
    if isinstance(value, str):
        clean = value.replace('$', '').replace(',', '').strip()
        return float(clean) if clean else 0.0
    return float(value)

def run_analysis(resume_date=None):
    print("--- Starting Portfolio Analysis ---")
    if resume_date:
        print(f"Resuming analysis from {resume_date}...")
    
    with open("data.json") as f:
        config = json.load(f)

    START_DATE = config.get("start_date")
    TARGET_DATE = config.get("latest_date")
    TRANSACTIONS_FILE = config.get("transactions_file", "transactions.csv")
    MAPPINGS_FILE = config.get("mappings_file", "mappings.json")

    # Load mappings for names
    name_map = {}
    image_map = {}
    try:
        with open(MAPPINGS_FILE, 'r') as mf:
            m_data = json.load(mf)
            for item in m_data:
                # Ensure keys match the string format used later
                gid = str(item.get('group_id', ''))
                pid = str(item.get('product_id', ''))
                name_map[(gid, pid)] = item.get('name', 'Unknown')
                image_map[(gid, pid)] = item.get('imageUrl', '')
    except Exception as e:
        print(f"Warning: Could not load mappings {MAPPINGS_FILE}: {e}")

    # 1. Load and Prepare Transactions
    print("Loading transactions...")
    try:
        df = pd.read_csv(TRANSACTIONS_FILE)
    except FileNotFoundError:
        print(f"Error: {TRANSACTIONS_FILE} not found.")
        return

    df['Date Recieved'] = pd.to_datetime(df['Date Recieved'])
    
    # Handle missing Quantity: Default to 1.0 so "OPEN" rows without quantity still work
    if df['Quantity'].isna().any():
        num_missing = df['Quantity'].isna().sum()
        print(f"  - Note: {num_missing} transaction(s) missing 'Quantity'. Defaulting them to 1.0.")
        df['Quantity'] = df['Quantity'].fillna(1.0)

    df['Price Per Unit'] = df['Price Per Unit'].apply(parse_currency)
    df['Total Transaction Value'] = df['Price Per Unit'] * df['Quantity']

    # 2. Initialize Loop
    current_date = pd.to_datetime(START_DATE)
    end_date = pd.to_datetime(TARGET_DATE)
    if end_date > datetime.now(): 
        end_date = datetime.now() # Don't graph the future

    daily_records = []
    
    # NEW: Handle resume logic
    if resume_date:
         resume_dt = pd.to_datetime(resume_date)
    else:
         resume_dt = current_date
         
    if resume_dt > current_date and os.path.exists("daily_tracker.csv"):
        try:
            print("Loading existing daily_tracker.csv for incremental update...")
            existing_df = pd.read_csv("daily_tracker.csv")
            if not existing_df.empty:
                existing_df['Date'] = pd.to_datetime(existing_df['Date'])
                existing_df['Items Owned'] = existing_df['Items Owned'].fillna(0)
                # Keep historical data strictly BEFORE the resume date
                existing_df = existing_df[existing_df['Date'] < resume_dt]
                daily_records = existing_df.to_dict('records')
        except Exception as e:
            print(f"Warning: Could not load existing tracker data: {e}")
            daily_records = []
    
    # State: { (group_id, product_id): quantity }
    inventory = {} 
    running_cost_basis = 0.0

    print("Calculating daily positions...")
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Get transactions strictly for this day
        # Ensure we are comparing dates correctly
        day_txs = df[df['Date Recieved'].dt.date == current_date.date()]
        
        # --- A. Process Transactions (Start of Day logic) ---
        for _, tx in day_txs.iterrows():
            # Handle float vs int vs str issues in IDs
            try:
                g_id = str(int(float(tx['group_id'])))
                p_id = str(int(float(tx['product_id'])))
            except (ValueError, TypeError):
                continue

            qty = tx['Quantity']
            t_type = str(tx['Transaction Type']).strip().upper()
            total_cost = tx['Total Transaction Value']
            
            key = (g_id, p_id)
            
            if t_type in ['BUY', 'PULL']:
                # PULL is effectively a BUY at $0 cost
                inventory[key] = inventory.get(key, 0) + qty
                running_cost_basis += total_cost
                
            elif t_type == 'SELL':
                inventory[key] = inventory.get(key, 0) - qty
                if inventory[key] < 0: inventory[key] = 0
                # Basis decreases by REVENUE (Net Investment Logic)
                running_cost_basis -= total_cost
                
            elif t_type == 'OPEN':
                inventory[key] = inventory.get(key, 0) - qty
                if inventory[key] < 0: inventory[key] = 0
                # Basis: No change
                # Value: Decreases naturally in step B because inventory count drops

        # --- B. Calculate Portfolio Value (End of Day logic) ---
        if current_date < resume_dt:
            # Rebuilding inventory state only. Skip expensive calculations.
            current_date += timedelta(days=1)
            continue

        daily_portfolio_value = 0.0
        
        for (g_id, p_id), quantity in inventory.items():
            if quantity > 0:
                # Get categoryId from mappings
                product_info = get_product_info_from_ids(g_id, p_id)
                category_id = 3  # Default to Pokemon
                if product_info and product_info.get('categoryId'):
                    category_id = product_info.get('categoryId')
                
                price = get_price_for_date(g_id, p_id, date_str, category_id)
                daily_portfolio_value += (price * quantity)

        items_owned = sum(inventory.values())

        # Safety Check: If value is 0 but we own items, it's likely a data error.
        if items_owned > 0 and daily_portfolio_value == 0:
             print(f"⚠️  WARNING {date_str}: Price data missing (Value is $0 but {items_owned} items owned). Skipping date.")
             current_date += timedelta(days=1)
             continue

        daily_records.append({
            'Date': current_date,
            'Total Value': round(daily_portfolio_value, 2),
            'Cost Basis': round(running_cost_basis, 2),
            'Items Owned': items_owned
        })
        
        current_date += timedelta(days=1)

    # 3. Save Data
    results_df = pd.DataFrame(daily_records)
    results_df.to_csv("daily_tracker.csv", index=False)

    # 3b. Validate no missing dates
    if not results_df.empty:
        results_df['Date'] = pd.to_datetime(results_df['Date'])
        expected = set(pd.date_range(results_df['Date'].min(), results_df['Date'].max(), freq='D'))
        actual = set(results_df['Date'])
        missing = sorted(expected - actual)
        if missing:
            print(f"\n🚨🚨🚨 MISSING DATES DETECTED ({len(missing)}): 🚨🚨🚨")
            for d in missing:
                print(f"   - {d.date()}")
            print("\nProcess STOPPED. Fix the missing price data before continuing.")
            print("daily_tracker.csv has been saved but contains gaps.")
            import sys
            sys.exit(1)
        else:
            print(f"✅ Date continuity verified: {len(actual)} days, no gaps.")

    # 4. Generate Graph
    if not results_df.empty:
        fig = go.Figure()
        
        # Value Area
        fig.add_trace(go.Scatter(
            x=results_df['Date'], 
            y=results_df['Total Value'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color='#00C851', width=3),
            stackgroup='one' # Creates a filled area
        ))
        
        # Cost Basis Line
        fig.add_trace(go.Scatter(
            x=results_df['Date'], 
            y=results_df['Cost Basis'],
            mode='lines',
            name='Net Investment (Cost Basis)',
            line=dict(color='#ff4444', width=2, dash='dash')
        ))

        fig.update_layout(
            title='Pokemon Investment Tracker',
            xaxis_title='Date',
            yaxis_title='Value ($)',
            hovermode="x unified",
            template="plotly_white",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )
        
        output_html = "portfolio_graph.html"
        fig.write_html(output_html)

        # --- Performance Ratio Graph ---
        fig_ratio = go.Figure()
        
        # Calculate ratio safely. 
        # If Cost Basis <= 0 (Free roll or Profitable), ratio is mathematically tricky.
        # We will handle 0 avoid errors, but negative basis will yield negative ratios which indicate "House Money" status visually.
        results_df['Performance Ratio'] = results_df.apply(
            lambda row: row['Total Value'] / row['Cost Basis'] if abs(row['Cost Basis']) > 0.01 else 0.0, 
            axis=1
        )
        
        fig_ratio.add_trace(go.Scatter(
            x=results_df['Date'], 
            y=results_df['Performance Ratio'],
            mode='lines',
            name='Value / Net Investment',
            line=dict(color='#4f46e5', width=3)
        ))

        # Add a reference line at 1.0 (Break Even)
        fig_ratio.add_shape(
            type="line",
            x0=results_df['Date'].min(),
            y0=1,
            x1=results_df['Date'].max(),
            y1=1,
            line=dict(color="#64748b", width=2, dash="dot"),
        )

        fig_ratio.update_layout(
            title='Portfolio Performance (Value / Net Investment)',
            xaxis_title='Date',
            yaxis_title='Ratio (>1 = Profit)',
            hovermode="x unified",
            template="plotly_white",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )
        
        ratio_html = "performance_graph.html"
        fig_ratio.write_html(ratio_html)

        print(f"Success! \n - Data saved to daily_tracker.csv\n - Graph saved to {output_html}\n - Performance Graph saved to {ratio_html}")
    else:
        print("No daily records generated.")
    
    # 5. Generate Current Holdings Snapshot
    print("Generating current holdings snapshot...")
    holdings_list = []
    
    # Calculate most recent prices for the snapshot
    last_date_str = end_date.strftime('%Y-%m-%d')
    
    for (g_id, p_id), qty in inventory.items():
        if qty > 0:
            # Get categoryId from mappings
            product_info = get_product_info_from_ids(g_id, p_id)
            category_id = 3  # Default to Pokemon
            if product_info and product_info.get('categoryId'):
                category_id = product_info.get('categoryId')
            
            price = _get_latest_price(g_id, p_id, last_date_str, category_id)
            holdings_list.append({
                'Product Name': name_map.get((g_id, p_id), "Unknown"),
                'group_id': g_id,
                'product_id': p_id,
                'Quantity': qty,
                'Latest Price': price,
                'Total Value': price * qty,
                'Image URL': image_map.get((g_id, p_id), "")
            })
    
    if holdings_list:
        pd.DataFrame(holdings_list).to_csv("current_holdings.csv", index=False)
    else:
        # Create empty if nothing held
        pd.DataFrame(columns=['Product Name', 'group_id', 'product_id', 'Quantity', 'Latest Price', 'Total Value']).to_csv("current_holdings.csv", index=False)

if __name__ == "__main__":
    run_analysis()
