import requests
import subprocess
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import csv
import json

with open("data.json") as f:
    data = json.load(f)
MAPPINGS_FILE = data.get("mappings_file")
TRANSACTIONS_FILE = data.get("transactions_file")

def get_product_active_ranges():
    """
    Parses transactions and returns a dictionary mapping (group_id, product_id) to
    a list of date ranges [(start_date, end_date), ...] when the product was owned.
    """
    if not os.path.exists(TRANSACTIONS_FILE):
        return {}

    transactions = []
    with open(TRANSACTIONS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        transactions = list(reader)

    # Sort by date received
    def parse_date(d):
        try:
             return datetime.strptime(d, '%m/%d/%Y').date()
        except:
             return datetime.min.date()
    
    transactions.sort(key=lambda x: parse_date(x.get('Date Recieved', '')))

    active_ranges = {} # (gid, pid) -> [(start, end), ...]
    product_states = {} # (gid, pid) -> { 'qty': 0, 'range_start': None }

    for tx in transactions:
        try:
            # Clean IDs
            gid = str(int(float(tx['group_id'])))
            pid = str(int(float(tx['product_id'])))
            key = (gid, pid)
            
            date_str = tx['Date Recieved']
            tx_date = datetime.strptime(date_str, '%m/%d/%Y').date()
            
            tx_type = str(tx['Transaction Type']).strip().upper()
            qty = float(tx['Quantity'])

            if key not in product_states:
                product_states[key] = {'qty': 0.0, 'range_start': None}
                active_ranges[key] = []

            state = product_states[key]
            current_qty = state['qty']

            if tx_type in ['BUY', 'PULL']:
                new_qty = current_qty + qty
                if current_qty <= 0 and new_qty > 0:
                     state['range_start'] = tx_date
                state['qty'] = new_qty

            elif tx_type in ['SELL', 'OPEN', 'TRADE']:
                new_qty = current_qty - qty
                if current_qty > 0 and new_qty <= 0:
                    if state['range_start']:
                        # Determine end date (inclusive or exclusive? usually exclusive for check)
                        # "Still owned in any of those dates". 
                        # If I sell on Day X, I owned it on Day X (start of day). 
                        # So range should cover Day X.
                        active_ranges[key].append( (state['range_start'], tx_date) )
                        state['range_start'] = None
                state['qty'] = new_qty

        except (ValueError, KeyError, TypeError):
            continue

    # Close open ranges
    for key, state in product_states.items():
        if state['qty'] > 0 and state['range_start']:
            active_ranges[key].append( (state['range_start'], None) )

    return active_ranges

def is_product_active(gid, pid, date_obj, active_ranges):
    """
    Checks if a product was owned on a specific date.
    date_obj should be datetime.date
    """
    key = (str(gid), str(pid))
    ranges = active_ranges.get(key, [])
    
    for start, end in ranges:
        if start <= date_obj:
            if end is None: 
                return True
            if date_obj <= end:
                return True
    return False

# collect_historical_data("2025-08-11", "2025-08-13", 24269, 628395)
# [{'date': '2025-08-11', 'marketPrice': 14.2}, {'date': '2025-08-12', 'marketPrice': None}, {'date': '2025-08-13', 'marketPrice': 14.42}]
def collect_historical_data(start_date_str, end_date_str, group_id, product_id):
    """
    Return a list of dicts with only date and marketPrice for the specified
    group_id and product_id over the date range:
      - date (YYYY-MM-DD)
      - marketPrice (float or None)
    Missing or error days will have marketPrice set to None.
    """
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    current_date = start_date
    results = []

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        archive_url = f"https://tcgcsv.com/archive/tcgplayer/prices-{date_str}.ppmd.7z"
        archive_filename = f"prices-{date_str}.ppmd.7z"
        extracted_folder = date_str

        try:
            resp = requests.get(archive_url, stream=True)
            if resp.status_code != 200:
                results.append({'date': date_str, 'marketPrice': None})
                current_date += timedelta(days=1)
                continue

            with open(archive_filename, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            # extract
            result = subprocess.run(['7z', 'x', archive_filename, '-y'],
                                    capture_output=True, text=True)
            if result.returncode != 0:
                results.append({'date': date_str, 'marketPrice': None})
                cleanup_files(archive_filename, extracted_folder)
                current_date += timedelta(days=1)
                continue

            prices_file = Path(extracted_folder) / "3" / str(group_id) / "prices"
            if not prices_file.exists():
                results.append({'date': date_str, 'marketPrice': None})
                cleanup_files(archive_filename, extracted_folder)
                current_date += timedelta(days=1)
                continue

            # read JSON and find product
            import json
            with open(prices_file, 'r') as f:
                data = json.load(f)

            found_price = None
            if isinstance(data, dict) and 'results' in data and isinstance(data['results'], list):
                for prod in data['results']:
                    if str(prod.get('productId')) == str(product_id):
                        mp = prod.get('marketPrice')
                        if mp is None or mp == '':
                            found_price = None
                        else:
                            try:
                                found_price = float(mp)
                            except (ValueError, TypeError):
                                found_price = None
                        break

            results.append({'date': date_str, 'marketPrice': found_price})

            cleanup_files(archive_filename, extracted_folder)

        except Exception:
            cleanup_files(archive_filename, extracted_folder)
            results.append({'date': date_str, 'marketPrice': None})

        current_date += timedelta(days=1)

    return results

def cleanup_files(archive_filename, extracted_folder):
    """
    Clean up downloaded and extracted files
    """
    try:
        if os.path.exists(archive_filename):
            os.remove(archive_filename)
        if os.path.exists(extracted_folder):
            shutil.rmtree(extracted_folder)
    except Exception as e:
        print(f"  ⚠️  Warning: Could not clean up files: {e}")    
        
def get_product_info_from_ids(group_id, product_id):
    """
    Given group_id and product_id, return info (imageUrl, name, categoryId, and url) using the provided mappings dictionary.
    """
    if not os.path.exists(MAPPINGS_FILE):
        raise FileNotFoundError(f"Mappings file '{MAPPINGS_FILE}' not found.")

    with open(MAPPINGS_FILE, 'r') as f:
        mappings = json.load(f)

    group_str = str(group_id)
    product_str = str(product_id)

    for mapping in mappings:
        if mapping["group_id"] == group_str and mapping["product_id"] == product_str:
            return {
                'categoryId': mapping.get('categoryId'),
                'name': mapping.get('name'),
                'imageUrl': mapping.get('imageUrl'),
                'url': mapping.get('url')
            }

    return None

def get_product_info_from_name(product_name):
    """
    Given product name, return info (group_id, product_id, imageUrl, categoryId, and url) using the provided mappings dictionary.
    """
    if not os.path.exists(MAPPINGS_FILE):
        raise FileNotFoundError(f"Mappings file '{MAPPINGS_FILE}' not found.")

    with open(MAPPINGS_FILE, 'r') as f:
        mappings = json.load(f)

    name = str(product_name)

    for mapping in mappings:
        if mapping["name"] == name:
            return {
                'group_id': mapping.get('group_id'),
                'product_id': mapping.get('product_id'),
                'categoryId': mapping.get('categoryId'),
                'imageUrl': mapping.get('imageUrl'),
                'url': mapping.get('url')
            }

    return None    

def update_historical_price_files(start_date_str, end_date_str, group_id, product_id, output_folder='historical_prices'):
    """
    Update historical price files for the specified group_id and product_id
    over the date range. Saves individual date files in output_folder.
    Any missing dates are filled with a best-guess price using nearby known values.
    """
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    records = collect_historical_data(start_date_str, end_date_str, group_id, product_id)

    def best_guess_price(idx):
        price = records[idx].get('marketPrice')
        if price is not None:
            return price

        prev_price = None
        for j in range(idx - 1, -1, -1):
            candidate = records[j].get('marketPrice')
            if candidate is not None:
                prev_price = candidate
                break

        next_price = None
        for j in range(idx + 1, len(records)):
            candidate = records[j].get('marketPrice')
            if candidate is not None:
                next_price = candidate
                break

        if prev_price is not None and next_price is not None:
            return round((prev_price + next_price) / 2, 2)
        if prev_price is not None:
            return prev_price
        if next_price is not None:
            return next_price
        return None

    base_path = Path(output_folder) / str(group_id) / str(product_id)
    base_path.mkdir(parents=True, exist_ok=True)

    saved_files = []

    for idx, record in enumerate(records):
        date_str = record.get('date')
        if not date_str:
            continue  # Skip malformed entries

        file_path = base_path / f"{date_str}.json"

        # Ignore/overwrite any existing data for the date in range
        if file_path.exists():
            file_path.unlink()

        payload = {
            'date': date_str,
            'group_id': str(group_id),
            'product_id': str(product_id),
            'marketPrice': best_guess_price(idx)
        }

        with open(file_path, 'w') as f:
            json.dump(payload, f)

        saved_files.append(str(file_path))

    return saved_files

def get_price_for_date(group_id, product_id, date_str, historical_folder='historical_prices'):
    """
    Retrieve the market price for a specific product on a specific date from local files.
    Returns 0.0 if not found.
    """
    file_path = Path(historical_folder) / str(group_id) / str(product_id) / f"{date_str}.json"
    
    if not file_path.exists():
        return 0.0
        
    try:
        with open(file_path, 'r') as f:
            try:
                data = json.load(f)
                price = data.get('marketPrice')
                return float(price) if price is not None else 0.0
            except json.JSONDecodeError:
                return 0.0
    except (ValueError, TypeError):
        return 0.0

def batch_update_historical_prices(start_date_str, end_date_str, product_list, output_folder='historical_prices'):
    """
    Downloads daily price dumps ONCE per day, extracts prices for ALL products in product_list,
    and saves them to the file system.
    
    product_list: List of dicts with 'group_id' and 'product_id' keys.
    """
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    now = datetime.now()
    if end_date > now: 
        end_date = now
    
    # NEW: Get active ranges to determine what to fetch
    active_ranges = get_product_active_ranges()

    current_date = start_date
    
    # Pre-organize products by group_id for faster lookup {group_id: [product_id, ...]}
    products_by_group = {}
    for p in product_list:
        g_id = str(p['group_id']).strip()
        p_id = str(p['product_id']).strip()
        if g_id not in products_by_group:
            products_by_group[g_id] = []
        products_by_group[g_id].append(p_id)

    print(f"Batch processing from {start_date_str} to {end_date.strftime('%Y-%m-%d')}...")

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # 1. Identify which products are ACTIVE on this date
        active_products_today = []
        for p in product_list:
            g_id = str(p['group_id']).strip()
            p_id = str(p['product_id']).strip()
            
            if is_product_active(g_id, p_id, current_date.date(), active_ranges):
                active_products_today.append(p)

        if not active_products_today:
             # No products active on this day, skip
             # print(f"Skipping {date_str} - No active products.")
             current_date += timedelta(days=1)
             continue

        # 2. Check if we already have data for these ACTIVE products
        missing_data = False
        for p in active_products_today:
            g_id = str(p['group_id'])
            p_id = str(p['product_id'])
            check_path = Path(output_folder) / g_id / p_id / f"{date_str}.json"
            if not check_path.exists():
                missing_data = True
                break
        
        if not missing_data:
            print(f"Skipping {date_str} - All required data present.")
            current_date += timedelta(days=1)
            continue
        
        archive_url = f"https://tcgcsv.com/archive/tcgplayer/prices-{date_str}.ppmd.7z"
        archive_filename = f"prices-{date_str}.ppmd.7z"

        extracted_folder = f"temp_extract_{date_str}" 

        try:
            print(f"Processing {date_str}...", end='', flush=True)
            
            # Download
            resp = requests.get(archive_url, stream=True)
            if resp.status_code != 200:
                print(f" [Skipped - No Data]")
                current_date += timedelta(days=1)
                continue

            with open(archive_filename, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract
            # We assume Pokemon is Category 3
            result = subprocess.run(['7z', 'x', archive_filename, f'-o{extracted_folder}', '-y'],
                                    capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f" [Extraction Failed]")
                cleanup_files(archive_filename, extracted_folder)
                current_date += timedelta(days=1)
                continue
            
            found_count = 0
            
            # Process Groups
            # The structure is sometimes `extracted_folder/3/...` and sometimes `extracted_folder/date_str/3/...`
            # or even `extracted_folder/prices-date/3` depending on how 7z behaves with the archive internal structure.
            
            base_path = Path(extracted_folder)
            
            # Hunting for the '3' folder (Pokemon)
            category_path = base_path / "3" 
            if not category_path.exists():
                # Check if there is a nested folder with the date name (common with some archives)
                nested = base_path / date_str / "3"
                if nested.exists():
                    category_path = nested
            
            if not category_path.exists():
                # DEBUG: Check what IS there
                existing = list(base_path.iterdir()) if base_path.exists() else "Folder Missing"
                print(f" [Debug: No '3' folder. Found: {[p.name for p in existing]}]", end='')

            if category_path.exists():
                # NEW: Filter to only active products
                active_by_group = {}
                for p in active_products_today:
                     g_id = str(p['group_id']).strip()
                     p_id = str(p['product_id']).strip()
                     if g_id not in active_by_group:
                         active_by_group[g_id] = []
                     active_by_group[g_id].append(p_id)
                
                for group_id, target_product_ids in active_by_group.items():
                    # The file inside is usually named 'prices' (no extension) which contains JSON
                    group_file = category_path / group_id / "prices"
                    
                    if not group_file.exists():
                        # DEBUG: detailed fail for the first group to help diagnose
                        # print(f"[Missing Group {group_id}]", end='')
                        continue

                    if group_file.exists():
                        try:
                            with open(group_file, 'r') as gf:
                                data = json.load(gf)
                            
                            if isinstance(data, dict) and 'results' in data:
                                # Create map for O(1) lookup
                                day_prices = {}
                                for res in data['results']:
                                    pid = str(res.get('productId'))
                                    day_prices[pid] = res.get('marketPrice')

                                # Save requested products
                                for pid in target_product_ids:
                                    if pid in day_prices:
                                        val = day_prices[pid]
                                        if val is not None:
                                            # Write file
                                            out_dir = Path(output_folder) / group_id / pid
                                            out_dir.mkdir(parents=True, exist_ok=True)
                                            
                                            out_file = out_dir / f"{date_str}.json"
                                            with open(out_file, 'w') as of:
                                                json.dump({
                                                    'date': date_str,
                                                    'group_id': group_id,
                                                    'product_id': pid,
                                                    'marketPrice': float(val)
                                                }, of)
                                            found_count += 1
                        except Exception:
                            pass
            
            print(f" [OK - Saved {found_count} prices]")
            cleanup_files(archive_filename, extracted_folder)

        except Exception as e:
            print(f" [Error: {e}]")
            cleanup_files(archive_filename, extracted_folder)

        current_date += timedelta(days=1)



