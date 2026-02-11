"""
price_fetcher.py - Fetch historical market prices from tcgcsv.com

Downloads daily price archives and extracts market prices for tracked products.
Prices are stored as single JSON files per product: prices/<cat>/<group>/<product>.json
Format: {"2024-11-19": 52.75, "2024-11-20": 53.10, ...}
"""

import requests
import subprocess
import os
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path

from engine import (
    load_config, load_prices, save_prices, today_pst,
    get_owned_date_ranges, load_transactions, fill_price_gaps,
    PRICES_DIR, PRICE_GAPS_FILE, BASE_DIR
)


def cleanup_files(*paths):
    """Remove files and directories."""
    for p in paths:
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            elif os.path.isfile(p):
                os.remove(p)
        except Exception as e:
            print(f"  ⚠️  Cleanup warning: {e}")


def fetch_prices_for_date(date_str, products_by_category):
    """
    Download the price archive for a single date and extract prices for
    all requested products.
    
    Args:
        date_str: "YYYY-MM-DD"
        products_by_category: {cat_id: {group_id: [product_id, ...]}}
    
    Returns:
        dict: {(cat, gid, pid): price} for all found products
    """
    archive_url = f"https://tcgcsv.com/archive/tcgplayer/prices-{date_str}.ppmd.7z"
    archive_filename = os.path.join(BASE_DIR, f"prices-{date_str}.ppmd.7z")
    extracted_folder = os.path.join(BASE_DIR, f"temp_extract_{date_str}")
    
    found_prices = {}
    
    try:
        resp = requests.get(archive_url, stream=True, timeout=60)
        if resp.status_code != 200:
            return found_prices
        
        with open(archive_filename, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        result = subprocess.run(
            ["7z", "x", archive_filename, f"-o{extracted_folder}", "-y"],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            cleanup_files(archive_filename, extracted_folder)
            return found_prices
        
        base_path = Path(extracted_folder)
        
        for cat_id, groups in products_by_category.items():
            cat_path = base_path / str(cat_id)
            if not cat_path.exists():
                # Try nested date folder
                nested = base_path / date_str / str(cat_id)
                if nested.exists():
                    cat_path = nested
            
            if not cat_path.exists():
                continue
            
            for group_id, product_ids in groups.items():
                group_file = cat_path / str(group_id) / "prices"
                if not group_file.exists():
                    continue
                
                try:
                    with open(group_file, "r") as gf:
                        data = json.load(gf)
                    
                    if isinstance(data, dict) and "results" in data:
                        price_map = {}
                        for res in data["results"]:
                            pid = str(res.get("productId"))
                            mp = res.get("marketPrice")
                            if mp is not None:
                                try:
                                    price_map[pid] = float(mp)
                                except (ValueError, TypeError):
                                    pass
                        
                        for pid in product_ids:
                            if pid in price_map:
                                found_prices[(str(cat_id), str(group_id), pid)] = price_map[pid]
                
                except (json.JSONDecodeError, Exception):
                    pass
        
        cleanup_files(archive_filename, extracted_folder)
    
    except Exception as e:
        print(f"  Error fetching {date_str}: {e}")
        cleanup_files(archive_filename, extracted_folder)
    
    return found_prices


def build_products_by_category(product_keys):
    """
    Convert set of (cat, gid, pid) to {cat: {gid: [pid, ...]}}.
    """
    by_cat = {}
    for cat, gid, pid in product_keys:
        if cat not in by_cat:
            by_cat[cat] = {}
        if gid not in by_cat[cat]:
            by_cat[cat][gid] = []
        if pid not in by_cat[cat][gid]:
            by_cat[cat][gid].append(pid)
    return by_cat


def update_prices(start_date_str=None, end_date_str=None, product_keys=None, force=False):
    """
    Fetch and store prices for all owned products for all dates they were owned.
    
    Args:
        start_date_str: Override start date (YYYY-MM-DD)
        end_date_str: Override end date (YYYY-MM-DD)
        product_keys: Optional set of (cat, gid, pid) to limit fetching
        force: If True, re-fetch even if data exists
    
    Returns:
        all_gaps: dict {product_key: [gap_dates]}
    """
    transactions = load_transactions()
    owned_ranges = get_owned_date_ranges(transactions)
    
    if not owned_ranges:
        print("No products with owned date ranges found.")
        return {}
    
    td = today_pst().strftime("%Y-%m-%d")
    
    # Determine which (product, date) pairs need fetching
    # product -> set of dates needed
    needed = {}  # (cat, gid, pid) -> set of date_strs
    
    for key, ranges in owned_ranges.items():
        if product_keys and key not in product_keys:
            continue
        
        existing_prices = load_prices(*key)
        
        for range_start, range_end in ranges:
            # Respect overrides
            eff_start = max(range_start, start_date_str) if start_date_str else range_start
            eff_end = min(range_end, end_date_str) if end_date_str else min(range_end, td)
            
            current = datetime.strptime(eff_start, "%Y-%m-%d").date()
            end = datetime.strptime(eff_end, "%Y-%m-%d").date()
            
            while current <= end:
                d_str = current.strftime("%Y-%m-%d")
                if force or d_str not in existing_prices or existing_prices[d_str] is None:
                    if key not in needed:
                        needed[key] = set()
                    needed[key].add(d_str)
                current += timedelta(days=1)
    
    if not needed:
        print("All prices are up to date.")
        return {}
    
    # Collect all dates that need fetching
    all_dates = set()
    for dates in needed.values():
        all_dates.update(dates)
    
    all_dates = sorted(all_dates)
    all_product_keys = set(needed.keys())
    products_by_category = build_products_by_category(all_product_keys)
    
    print(f"Fetching prices for {len(all_product_keys)} products across {len(all_dates)} dates...")
    
    # Fetch date by date
    for i, date_str in enumerate(all_dates):
        # Only fetch products that need this specific date
        date_product_keys = {k for k, dates in needed.items() if date_str in dates}
        date_products_by_cat = build_products_by_category(date_product_keys)
        
        print(f"  [{i+1}/{len(all_dates)}] {date_str}...", end="", flush=True)
        
        found = fetch_prices_for_date(date_str, date_products_by_cat)
        
        if found:
            # Merge found prices into existing files
            for key, price in found.items():
                existing = load_prices(*key)
                existing[date_str] = price
                save_prices(*key, existing)
            print(f" [{len(found)} prices]")
        else:
            print(" [no data]")
    
    # Fill gaps and record them
    print("\nFilling price gaps...")
    all_gaps = {}
    
    for key in all_product_keys:
        prices = load_prices(*key)
        ranges = owned_ranges.get(key, [])
        for range_start, range_end in ranges:
            eff_end = min(range_end, td)
            filled, gaps = fill_price_gaps(prices, range_start, eff_end)
            # Ensure the first day of ownership is present in the price file
            first_day_str = range_start
            if first_day_str not in filled or filled[first_day_str] is None or filled[first_day_str] == 0:
                # Find the next available price
                future_prices = [(d, filled[d]) for d in filled if filled[d] is not None and filled[d] > 0 and d > first_day_str]
                if future_prices:
                    next_date, next_price = min(future_prices, key=lambda x: x[0])
                    filled[first_day_str] = next_price
                    if f"{key[0]}/{key[1]}/{key[2]}" not in all_gaps:
                        all_gaps[f"{key[0]}/{key[1]}/{key[2]}"] = []
                    all_gaps[f"{key[0]}/{key[1]}/{key[2]}"] += [first_day_str]
            if gaps:
                if f"{key[0]}/{key[1]}/{key[2]}" not in all_gaps:
                    all_gaps[f"{key[0]}/{key[1]}/{key[2]}"] = []
                all_gaps[f"{key[0]}/{key[1]}/{key[2]}"] += gaps
            save_prices(*key, filled)
            if gaps:
                print(f"  {key[1]}/{key[2]}: {len(gaps)} gaps filled (carry-forward)")
    
    # Save gap report
    if all_gaps:
        with open(PRICE_GAPS_FILE, "w") as f:
            json.dump(all_gaps, f, indent=2)
        print(f"\n⚠️  Price gaps recorded in {PRICE_GAPS_FILE}")
    
    print("\n✅ Price update complete.")
    return all_gaps


def fetch_today_prices():
    """
    Fetch only today's prices for all currently held products.
    Used by the daily GitHub Actions job.
    """
    td = today_pst().strftime("%Y-%m-%d")
    transactions = load_transactions()
    
    # Get currently held products
    from engine import compute_inventory_timeline, get_quantity_on_date, _product_key
    inventory = compute_inventory_timeline(transactions)
    
    held_keys = set()
    for key, inv in inventory.items():
        qty = get_quantity_on_date(inv, td)
        if qty > 0:
            held_keys.add(key)
    
    if not held_keys:
        print("No products currently held.")
        return
    
    products_by_cat = build_products_by_category(held_keys)
    
    print(f"Fetching today's prices ({td}) for {len(held_keys)} products...")
    found = fetch_prices_for_date(td, products_by_cat)
    
    for key, price in found.items():
        existing = load_prices(*key)
        existing[td] = price
        save_prices(*key, existing)
    
    print(f"  Saved {len(found)} prices for {td}")
    
    # Fill any gaps for today
    all_gaps = {}
    for key in held_keys:
        prices = load_prices(*key)
        if td not in prices or prices[td] is None or prices[td] <= 0:
            # Carry forward
            sorted_dates = sorted(d for d in prices if prices[d] and prices[d] > 0)
            if sorted_dates:
                last_price = prices[sorted_dates[-1]]
                prices[td] = last_price
                save_prices(*key, prices)
                gap_key = f"{key[0]}/{key[1]}/{key[2]}"
                all_gaps[gap_key] = all_gaps.get(gap_key, []) + [td]
    
    if all_gaps:
        # Merge with existing gaps
        existing_gaps = {}
        if os.path.exists(PRICE_GAPS_FILE):
            with open(PRICE_GAPS_FILE, "r") as f:
                existing_gaps = json.load(f)
        existing_gaps.update(all_gaps)
        with open(PRICE_GAPS_FILE, "w") as f:
            json.dump(existing_gaps, f, indent=2)
        print(f"⚠️  {len(all_gaps)} products had no price today — carried forward")
    
    return found


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--today":
        fetch_today_prices()
    else:
        update_prices()
