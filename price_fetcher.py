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

REQUEST_HEADERS = {
    "User-Agent": "TCG_Tracker/1.0 (GitHub Actions price updater)"
}


class PriceArchiveFetchError(RuntimeError):
    """Raised when a daily tcgcsv archive cannot be downloaded or extracted."""


_ARCHIVE_AVAILABLE = None
_LIVE_GROUP_CACHE = {}


def fetch_live_group_prices(cat_id, group_id, session=None):
    """
    Fetch current market prices for a group from tcgcsv live endpoint:
      https://tcgcsv.com/tcgplayer/{cat_id}/{group_id}/prices
    Returns {product_id_str: marketPrice_float}. Cached in memory per process run.
    """
    cache_key = (str(cat_id), str(group_id))
    if cache_key in _LIVE_GROUP_CACHE:
        return _LIVE_GROUP_CACHE[cache_key]

    url = f"https://tcgcsv.com/tcgplayer/{cat_id}/{group_id}/prices"
    http = session or requests.Session()
    price_map = {}
    try:
        resp = http.get(url, timeout=20, headers=REQUEST_HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "results" in data:
                for res in data["results"]:
                    pid = str(res.get("productId"))
                    mp = res.get("marketPrice")
                    if mp is not None:
                        try:
                            price_map[pid] = float(mp)
                        except (ValueError, TypeError):
                            pass
        else:
            print(f" [HTTP {resp.status_code} from {url}]", end="")
    except Exception as e:
        print(f" [Error fetching {url}: {e}]", end="")

    _LIVE_GROUP_CACHE[cache_key] = price_map
    return price_map


def fetch_live_prices_for_products(products_by_category, session=None):
    """
    Fetch current market prices for a set of products using tcgcsv live group endpoints.
    Args:
        products_by_category: {cat_id: {group_id: [product_id, ...]}}
    Returns:
        dict: {(cat, gid, pid): price}
    """
    found_prices = {}
    http = session or requests.Session()
    for cat_id, groups in products_by_category.items():
        for group_id, product_ids in groups.items():
            price_map = fetch_live_group_prices(cat_id, group_id, session=http)
            for pid in product_ids:
                pid_str = str(pid)
                if pid_str in price_map:
                    found_prices[(str(cat_id), str(group_id), pid_str)] = price_map[pid_str]
    return found_prices


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
    Download or fetch prices for a single date and extract prices for
    all requested products.
    
    If date_str >= today (PST), fetches current prices via tcgcsv live per-group endpoints:
      https://tcgcsv.com/tcgplayer/{cat_id}/{group_id}/prices
    
    If date_str < today (past date), attempts to download daily price archive:
      https://tcgcsv.com/archive/tcgplayer/prices-{date_str}.ppmd.7z
    If the archive is unavailable (e.g. HTTP 403 / temporarily removed), it logs
    a notice and returns an empty dict without crashing, allowing fill_price_gaps to
    carry forward prices.
    
    Args:
        date_str: "YYYY-MM-DD"
        products_by_category: {cat_id: {group_id: [product_id, ...]}}
    
    Returns:
        dict: {(cat, gid, pid): price} for all found products
    """
    global _ARCHIVE_AVAILABLE
    td_str = today_pst().strftime("%Y-%m-%d")

    # For today or later, use live per-group API
    if date_str >= td_str:
        return fetch_live_prices_for_products(products_by_category)

    # For historical dates, if archive is known to be disabled, return empty
    if _ARCHIVE_AVAILABLE is False:
        return {}

    archive_url = f"https://tcgcsv.com/archive/tcgplayer/prices-{date_str}.ppmd.7z"
    archive_filename = os.path.join(BASE_DIR, f"prices-{date_str}.ppmd.7z")
    extracted_folder = os.path.join(BASE_DIR, f"temp_extract_{date_str}")
    
    found_prices = {}
    
    try:
        resp = requests.get(
            archive_url,
            stream=True,
            timeout=60,
            headers=REQUEST_HEADERS,
        )
        if resp.status_code == 403:
            _ARCHIVE_AVAILABLE = False
            print(f" [archive HTTP 403: tcgcsv price archive temporarily removed by host]", end="")
            return {}
        elif resp.status_code != 200:
            print(f" [archive HTTP {resp.status_code}]", end="")
            return {}
        
        with open(archive_filename, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        result = subprocess.run(
            ["7z", "x", archive_filename, f"-o{extracted_folder}", "-y"],
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            cleanup_files(archive_filename, extracted_folder)
            detail = result.stderr.strip() or result.stdout.strip()
            print(f" [7z extract failed: {detail[:100]}]", end="")
            return {}
        
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
        cleanup_files(archive_filename, extracted_folder)
        print(f" [error: {e}]", end="")
    
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
                existing_price = existing_prices.get(d_str)
                if force or d_str not in existing_prices or existing_price is None or existing_price <= 0:
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

        if force:
            # A forced repair should not leave old carried-forward values in
            # place for products that were absent from the fetched archive.
            for key in date_product_keys - set(found.keys()):
                existing = load_prices(*key)
                if date_str in existing:
                    del existing[date_str]
                    save_prices(*key, existing)
    
    # Fill gaps and record them
    print("\nFilling price gaps...")
    all_gaps = {}
    
    for key in all_product_keys:
        prices = load_prices(*key)
        ranges = owned_ranges.get(key, [])
        for range_start, range_end in ranges:
            eff_end = min(range_end, end_date_str) if end_date_str else min(range_end, td)
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
    
    # Save a fresh gap report for this run. Rewriting even when empty prevents
    # stale carry-forward warnings from surviving after a successful refetch.
    with open(PRICE_GAPS_FILE, "w") as f:
        json.dump(all_gaps, f, indent=2)
    if all_gaps:
        print(f"\n⚠️  Price gaps recorded in {PRICE_GAPS_FILE}")
    
    print("\n✅ Price update complete.")
    return all_gaps


def update_prices_for_product_date_ranges(product_ranges, start_date_str=None, end_date_str=None, force=False):
    """
    Fetch and store prices for explicit product ownership ranges.

    Args:
        product_ranges: dict {(cat, gid, pid): [(start, end), ...]}
        start_date_str: Optional lower bound (YYYY-MM-DD)
        end_date_str: Optional upper bound (YYYY-MM-DD)
        force: If True, re-fetch even if data exists.

    Returns:
        all_gaps: dict {product_key: [gap_dates]}
    """
    normalized_ranges = {}
    for key, ranges in (product_ranges or {}).items():
        cat, gid, pid = key
        norm_key = (str(cat), str(gid), str(pid))
        normalized_ranges.setdefault(norm_key, [])
        for range_start, range_end in ranges:
            if not range_start or not range_end:
                continue
            normalized_ranges[norm_key].append((str(range_start), str(range_end)))

    if not normalized_ranges:
        print("No product date ranges provided.")
        return {}

    td = today_pst().strftime("%Y-%m-%d")
    needed = {}

    for key, ranges in normalized_ranges.items():
        existing_prices = load_prices(*key)
        for range_start, range_end in ranges:
            eff_start = max(range_start, start_date_str) if start_date_str else range_start
            eff_end = min(range_end, end_date_str) if end_date_str else min(range_end, td)

            current = datetime.strptime(eff_start, "%Y-%m-%d").date()
            end = datetime.strptime(eff_end, "%Y-%m-%d").date()
            while current <= end:
                d_str = current.strftime("%Y-%m-%d")
                existing_price = existing_prices.get(d_str)
                if force or d_str not in existing_prices or existing_price is None or existing_price <= 0:
                    needed.setdefault(key, set()).add(d_str)
                current += timedelta(days=1)

    if not needed:
        print("All explicit product range prices are up to date.")
        return {}

    all_dates = sorted({d for dates in needed.values() for d in dates})
    print(f"Fetching range prices for {len(needed)} products across {len(all_dates)} dates...")

    for i, date_str in enumerate(all_dates):
        date_product_keys = {k for k, dates in needed.items() if date_str in dates}
        date_products_by_cat = build_products_by_category(date_product_keys)

        print(f"  [{i+1}/{len(all_dates)}] {date_str}...", end="", flush=True)
        found = fetch_prices_for_date(date_str, date_products_by_cat)

        if found:
            for key, price in found.items():
                existing = load_prices(*key)
                existing[date_str] = price
                save_prices(*key, existing)
            print(f" [{len(found)} prices]")
        else:
            print(" [no data]")

        if force:
            for key in date_product_keys - set(found.keys()):
                existing = load_prices(*key)
                if date_str in existing:
                    del existing[date_str]
                    save_prices(*key, existing)

    print("\nFilling explicit range price gaps...")
    all_gaps = {}
    for key, ranges in normalized_ranges.items():
        prices = load_prices(*key)
        for range_start, range_end in ranges:
            eff_end = min(range_end, end_date_str) if end_date_str else min(range_end, td)
            filled, gaps = fill_price_gaps(prices, range_start, eff_end)
            if gaps:
                gap_key = f"{key[0]}/{key[1]}/{key[2]}"
                all_gaps.setdefault(gap_key, [])
                all_gaps[gap_key] += gaps
            save_prices(*key, filled)

    with open(PRICE_GAPS_FILE, "w") as f:
        json.dump(all_gaps, f, indent=2)

    if all_gaps:
        print(f"\n⚠️  Price gaps recorded in {PRICE_GAPS_FILE}")

    print("\n✅ Explicit range price update complete.")
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


def fetch_prices_for_product_keys_on_date(date_str, product_keys, carry_forward=True):
    """
    Fetch prices for an explicit set of product keys on a single date.

    Args:
        date_str: YYYY-MM-DD
        product_keys: iterable of (cat, gid, pid)
        carry_forward: if True, fill missing date price from last known value

    Returns:
        dict with stats and missing keys
    """
    key_set = {(str(cat), str(gid), str(pid)) for cat, gid, pid in product_keys}
    if not key_set:
        print("No product keys provided for explicit date fetch.")
        return {
            "requested": 0,
            "found": 0,
            "carried": 0,
            "missing": [],
        }

    products_by_cat = build_products_by_category(key_set)
    print(f"Fetching prices for {len(key_set)} explicit products on {date_str}...")
    found = fetch_prices_for_date(date_str, products_by_cat)

    for key, price in found.items():
        existing = load_prices(*key)
        existing[date_str] = price
        save_prices(*key, existing)

    missing = []
    carried = 0
    if carry_forward:
        for key in key_set:
            if key in found:
                continue
            prices = load_prices(*key)
            sorted_dates = sorted(d for d in prices if prices[d] and prices[d] > 0 and d < date_str)
            if sorted_dates:
                prices[date_str] = prices[sorted_dates[-1]]
                save_prices(*key, prices)
                carried += 1
            else:
                missing.append(key)

    print(
        f"  Explicit fetch complete: found={len(found)}, carried={carried}, missing={len(missing)}"
    )

    return {
        "requested": len(key_set),
        "found": len(found),
        "carried": carried,
        "missing": sorted(missing),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--today":
        fetch_today_prices()
    else:
        update_prices()
