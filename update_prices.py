import pandas as pd
import json
import os
from functions import batch_update_historical_prices, get_product_info_from_ids


def _normalize_id(value):
    try:
        return str(int(float(value)))
    except (ValueError, TypeError):
        return str(value).strip()

def main(start_from_date=None, product_filter=None, extra_active_transactions=None):
    """
    Fetch historical prices for tracked products.

    extra_active_transactions: list of transaction dicts (e.g. removed rows)
        whose date ranges should also be considered "active" when deciding
        which dates to download prices for.  This is critical for deletions:
        the product may no longer appear active in the current transactions,
        but we still need prices for the dates it WAS active to correctly
        reverse the value delta.
    """
    print("--- Starting Price Update (Batch Mode) ---")
    
    # 1. Load Configuration
    if not os.path.exists("data.json"):
        print("Error: data.json not found.")
        return
        
    with open("data.json") as f:
        config = json.load(f)
        
    transactions_file = config.get("transactions_file", "transactions.csv")
    start_date = start_from_date or config.get("start_date")
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

    if product_filter:
        filter_set = set((str(g), str(p)) for g, p in product_filter)
        df_clean = df_clean.assign(
            _gid=df_clean['group_id'].apply(_normalize_id),
            _pid=df_clean['product_id'].apply(_normalize_id)
        )
        df_clean = df_clean[df_clean.apply(lambda r: (r['_gid'], r['_pid']) in filter_set, axis=1)]
        df_clean = df_clean.drop(columns=['_gid', '_pid'])

        if df_clean.empty:
            print("No matching products found for provided filter. Skipping price update.")
            return

    product_list = []
    print(f"Found {len(df_clean)} unique products to track.")

    for index, row in df_clean.iterrows():
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
    
    # 3. Fetch Data in Batch
    if product_list:
        try:
            batch_update_historical_prices(
                start_date, latest_date, product_list,
                extra_active_transactions=extra_active_transactions,
            )
        except KeyboardInterrupt:
            print("\nStopped by user.")
        except Exception as e:
            print(f"Batch update failed: {e}")

    print("\n--- Update Complete ---")

if __name__ == "__main__":
    main()
