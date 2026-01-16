import pandas as pd
import json
import os
from functions import batch_update_historical_prices

def main():
    print("--- Starting Price Update (Batch Mode) ---")
    
    # 1. Load Configuration
    if not os.path.exists("data.json"):
        print("Error: data.json not found.")
        return
        
    with open("data.json") as f:
        config = json.load(f)
        
    transactions_file = config.get("transactions_file", "transactions.csv")
    start_date = config.get("start_date")
    # Default to today if latest_date is far in future or not set
    latest_date = config.get("latest_date") 
    
    print(f"Reading products from {transactions_file}...")
    
    # 2. Extract Unique Products
    try:
        df = pd.read_csv(transactions_file)
        # Filter for valid IDs
        df_clean = df[['group_id', 'product_id', 'Item']].dropna(subset=['group_id', 'product_id']).drop_duplicates()
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    product_list = []
    print(f"Found {len(df_clean)} unique products to track.")

    for index, row in df_clean.iterrows():
        try:
            g_id = int(float(row['group_id']))
            p_id = int(float(row['product_id']))
            product_list.append({
                'group_id': g_id,
                'product_id': p_id,
                'name': row['Item']
            })
        except ValueError:
            continue
    
    # 3. Fetch Data in Batch
    if product_list:
        try:
            batch_update_historical_prices(start_date, latest_date, product_list)
        except KeyboardInterrupt:
            print("\nStopped by user.")
        except Exception as e:
            print(f"Batch update failed: {e}")

    print("\n--- Update Complete ---")

if __name__ == "__main__":
    main()
