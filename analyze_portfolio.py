import pandas as pd
import json
import plotly.graph_objects as go
from datetime import datetime, timedelta
from functions import get_price_for_date

def parse_currency(value):
    if pd.isna(value) or value == '':
        return 0.0
    if isinstance(value, str):
        clean = value.replace('$', '').replace(',', '').strip()
        return float(clean) if clean else 0.0
    return float(value)

def run_analysis():
    print("--- Starting Portfolio Analysis ---")
    
    with open("data.json") as f:
        config = json.load(f)

    START_DATE = config.get("start_date")
    TARGET_DATE = config.get("latest_date")
    TRANSACTIONS_FILE = config.get("transactions_file", "transactions.csv")

    # 1. Load and Prepare Transactions
    print("Loading transactions...")
    try:
        df = pd.read_csv(TRANSACTIONS_FILE)
    except FileNotFoundError:
        print(f"Error: {TRANSACTIONS_FILE} not found.")
        return

    df['Date Recieved'] = pd.to_datetime(df['Date Recieved'])
    df['Price Per Unit'] = df['Price Per Unit'].apply(parse_currency)
    df['Total Transaction Value'] = df['Price Per Unit'] * df['Quantity']

    # 2. Initialize Loop
    current_date = pd.to_datetime(START_DATE)
    end_date = pd.to_datetime(TARGET_DATE)
    if end_date > datetime.now(): 
        end_date = datetime.now() # Don't graph the future

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
        daily_portfolio_value = 0.0
        
        for (g_id, p_id), quantity in inventory.items():
            if quantity > 0:
                price = get_price_for_date(g_id, p_id, date_str)
                daily_portfolio_value += (price * quantity)

        daily_records.append({
            'Date': current_date,
            'Total Value': round(daily_portfolio_value, 2),
            'Cost Basis': round(running_cost_basis, 2),
            'Items Owned': sum(inventory.values())
        })
        
        current_date += timedelta(days=1)

    # 3. Save Data
    results_df = pd.DataFrame(daily_records)
    results_df.to_csv("daily_tracker.csv", index=False)
    
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
            template="plotly_dark",
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )
        
        output_html = "portfolio_graph.html"
        fig.write_html(output_html)
        print(f"Success! \n - Data saved to daily_tracker.csv\n - Graph saved to {output_html}")
    else:
        print("No daily records generated.")
    
    # 5. Generate Current Holdings Snapshot
    print("Generating current holdings snapshot...")
    holdings_list = []
    
    # Calculate most recent prices for the snapshot
    last_date_str = end_date.strftime('%Y-%m-%d')
    
    for (g_id, p_id), qty in inventory.items():
        if qty > 0:
            price = get_price_for_date(g_id, p_id, last_date_str)
            holdings_list.append({
                'group_id': g_id,
                'product_id': p_id,
                'Quantity': qty,
                'Latest Price': price,
                'Total Value': price * qty
            })
    
    if holdings_list:
        pd.DataFrame(holdings_list).to_csv("current_holdings.csv", index=False)
    else:
        # Create empty if nothing held
        pd.DataFrame(columns=['group_id', 'product_id', 'Quantity', 'Latest Price', 'Total Value']).to_csv("current_holdings.csv", index=False)

if __name__ == "__main__":
    run_analysis()
