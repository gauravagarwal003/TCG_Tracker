"""
engine.py - Core engine for TCG Tracker

Derives the daily timeline (total_value, cost_basis) from:
  1. transactions.json  (source of truth for all transactions)
  2. prices/<cat>/<group>/<product>.json  (source of truth for market prices)

Products are uniquely identified by (categoryId, group_id, product_id).
Ownership date = Date Received.
"""

import json
import os
from datetime import datetime, timedelta, date
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
TRANSACTIONS_FILE = os.path.join(BASE_DIR, "transactions.json")
MAPPINGS_FILE = os.path.join(BASE_DIR, "mappings.json")
PRICES_DIR = os.path.join(BASE_DIR, "prices")
DAILY_SUMMARY_FILE = os.path.join(BASE_DIR, "daily_summary.json")
PRICE_GAPS_FILE = os.path.join(BASE_DIR, "price_gaps.json")


def _try_fix_mojibake(s: str) -> str:
    """Attempt to fix common double-encoding (mojibake) like 'PokÃ©mon' -> 'Pokémon'.

    The heuristic looks for common invalid sequences and tries to re-decode
    from latin-1 -> utf-8 up to a few times until stable.
    """
    if not isinstance(s, str):
        return s
    # Quick heuristic: these sequences commonly appear in mojibake
    if "Ã" not in s and "Â" not in s:
        return s
    out = s
    # Try repeated latin-1 -> utf-8 decoding which often recovers
    # text that has been double/triple encoded. Cap iterations to
    # avoid pathological loops.
    for _ in range(10):
        try:
            candidate = out.encode("latin-1").decode("utf-8")
        except Exception:
            break
        if candidate == out:
            break
        out = candidate
    return out


def _fix_mojibake_in_obj(obj):
    """Recursively fix strings inside lists/dicts returned from JSON files."""
    if isinstance(obj, str):
        return _try_fix_mojibake(obj)
    if isinstance(obj, list):
        return [_fix_mojibake_in_obj(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _fix_mojibake_in_obj(v) for k, v in obj.items()}
    return obj


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return _fix_mojibake_in_obj(json.load(f))


def save_config(cfg):
    """Save config dict back to CONFIG_FILE."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, sort_keys=True)


def today_pst():
    """Return today's date in Pacific time."""
    import pytz
    tz = pytz.timezone("US/Pacific")
    return datetime.now(tz).date()


# ---------------------------------------------------------------------------
# Transactions I/O
# ---------------------------------------------------------------------------
def load_transactions():
    """Load all transactions from transactions.json."""
    if not os.path.exists(TRANSACTIONS_FILE):
        return []
    with open(TRANSACTIONS_FILE, "r", encoding="utf-8") as f:
        return _fix_mojibake_in_obj(json.load(f))


def save_transactions(txns):
    """Save all transactions to transactions.json."""
    with open(TRANSACTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(txns, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Price I/O
# ---------------------------------------------------------------------------
def _price_file_path(category_id, group_id, product_id):
    return os.path.join(PRICES_DIR, str(category_id), str(group_id), f"{product_id}.json")


def load_prices(category_id, group_id, product_id):
    """Load price dict {date_str: float} for a product."""
    path = _price_file_path(category_id, group_id, product_id)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return _fix_mojibake_in_obj(json.load(f))


def save_prices(category_id, group_id, product_id, price_dict):
    """Save price dict {date_str: float} for a product."""
    path = _price_file_path(category_id, group_id, product_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(price_dict, f, indent=2, sort_keys=True, ensure_ascii=False)


def get_price(category_id, group_id, product_id, date_str):
    """Get price for a product on a specific date. Returns 0.0 if not found."""
    prices = load_prices(category_id, group_id, product_id)
    return prices.get(date_str, 0.0)


# ---------------------------------------------------------------------------
# Mappings I/O
# ---------------------------------------------------------------------------
def load_mappings():
    if not os.path.exists(MAPPINGS_FILE):
        return []
    with open(MAPPINGS_FILE, "r", encoding="utf-8") as f:
        return _fix_mojibake_in_obj(json.load(f))


def save_mappings(mappings):
    with open(MAPPINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(mappings, f, indent=2, ensure_ascii=False)


def get_mapping(group_id, product_id):
    """Find mapping entry for a product."""
    mappings = load_mappings()
    for m in mappings:
        if str(m["group_id"]) == str(group_id) and str(m["product_id"]) == str(product_id):
            return m
    return None


# ---------------------------------------------------------------------------
# Inventory helpers
# ---------------------------------------------------------------------------
def parse_date(d):
    """Parse YYYY-MM-DD string to date object."""
    return datetime.strptime(d, "%Y-%m-%d").date()


def _product_key(item):
    """Return (categoryId, group_id, product_id) tuple from an item dict.

    Require that `categoryId` is present on the item. This prevents silently
    assuming a magic default and ensures transactions explicitly state the
    product category.
    """
    if "categoryId" not in item:
        raise ValueError(f"Item missing 'categoryId': {item}")
    return (str(item["categoryId"]), str(item["group_id"]), str(item["product_id"]))


def compute_inventory_timeline(transactions):
    """
    Walk through all transactions sorted by date_received and compute
    the quantity owned of each product on each date.
    
    Returns:
        inventory: dict mapping (cat, gid, pid) -> {date_str: qty}
            Only includes dates where ownership changed. To get qty on
            any date, use the most recent date <= target.
    """
    # Sort by date_received
    sorted_txns = sorted(transactions, key=lambda t: t["date_received"])
    
    # (cat, gid, pid) -> list of (date, delta)
    deltas = defaultdict(list)
    
    for txn in sorted_txns:
        txn_date = txn["date_received"]
        txn_type = txn["type"].upper()
        
        if txn_type in ("BUY",):
            for item in txn["items"]:
                key = _product_key(item)
                deltas[key].append((txn_date, item["quantity"]))
                
        elif txn_type in ("SELL", "OPEN"):
            for item in txn["items"]:
                key = _product_key(item)
                deltas[key].append((txn_date, -item["quantity"]))
                
        elif txn_type == "TRADE":
            for item in txn.get("items_out", []):
                key = _product_key(item)
                deltas[key].append((txn_date, -item["quantity"]))
            for item in txn.get("items_in", []):
                key = _product_key(item)
                deltas[key].append((txn_date, item["quantity"]))
    
    # Build inventory snapshots
    inventory = {}
    for key, changes in deltas.items():
        changes.sort(key=lambda x: x[0])
        running_qty = 0
        inv = {}
        for d, delta in changes:
            running_qty += delta
            inv[d] = running_qty
        inventory[key] = inv
    
    return inventory


def get_quantity_on_date(inventory_for_product, date_str):
    """
    Given an inventory dict {date_str: qty} for a single product,
    return the quantity owned on date_str by finding the latest entry <= date_str.
    """
    if not inventory_for_product:
        return 0
    
    best_date = None
    for d in inventory_for_product:
        if d <= date_str:
            if best_date is None or d > best_date:
                best_date = d
    
    if best_date is None:
        return 0
    return inventory_for_product[best_date]


def validate_inventory(transactions, new_txn=None, exclude_txn_id=None):
    """
    Validate that no product quantity goes negative at any point in time.
    
    Args:
        transactions: current list of transactions
        new_txn: optional new transaction to add for validation
        exclude_txn_id: optional transaction id to exclude (for delete validation)
    
    Returns:
        (is_valid, error_message)
    """
    test_txns = [t for t in transactions if t["id"] != exclude_txn_id] if exclude_txn_id else list(transactions)
    if new_txn:
        test_txns.append(new_txn)
    
    inventory = compute_inventory_timeline(test_txns)
    
    for key, inv in inventory.items():
        for d, qty in sorted(inv.items()):
            if qty < 0:
                cat, gid, pid = key
                mapping = get_mapping(gid, pid)
                name = mapping["name"] if mapping else f"{gid}/{pid}"
                return False, f"Inventory for '{name}' goes to {qty} on {d}"
    
    return True, ""


# ---------------------------------------------------------------------------
# Price gap filling
# ---------------------------------------------------------------------------
def fill_price_gaps(price_dict, start_date_str, end_date_str):
    """
    Fill gaps in a price dict using carry-forward strategy.
    Also fills backward at the start of ownership with the next available price.
    Returns (filled_dict, gap_dates) where gap_dates is a list of dates
    that were filled.
    """
    start = parse_date(start_date_str)
    end = parse_date(end_date_str)
    filled = dict(price_dict)
    gap_dates = []
    current = start
    last_known_price = None
    # Find the first known price before or at start
    for d_str in sorted(filled.keys()):
        d = parse_date(d_str)
        if d <= start and filled[d_str] is not None and filled[d_str] > 0:
            last_known_price = filled[d_str]
    # If no price before or at start, fill with next available price
    if last_known_price is None:
        future_prices = [(parse_date(d_str), filled[d_str]) for d_str in filled if filled[d_str] is not None and filled[d_str] > 0 and parse_date(d_str) > start]
        if future_prices:
            next_date, next_price = min(future_prices, key=lambda x: x[0])
            # Fill the first day of ownership explicitly
            first_day_str = start.strftime("%Y-%m-%d")
            filled[first_day_str] = next_price
            gap_dates.append(first_day_str)
            last_known_price = next_price
    while current <= end:
        d_str = current.strftime("%Y-%m-%d")
        if d_str in filled and filled[d_str] is not None and filled[d_str] > 0:
            last_known_price = filled[d_str]
        elif last_known_price is not None:
            filled[d_str] = last_known_price
            gap_dates.append(d_str)
        current += timedelta(days=1)
    return filled, gap_dates


# ---------------------------------------------------------------------------
# Core: Derive daily summary
# ---------------------------------------------------------------------------
def derive_daily_summary(transactions=None):
    """
    Derive the complete daily summary from transactions + prices.
    
    Returns:
        summary: dict {date_str: {"total_value": float, "cost_basis": float}}
    """
    if transactions is None:
        transactions = load_transactions()
    
    if not transactions:
        return {}
    
    config = load_config()
    start_date_str = config.get("start_date", "2024-11-19")
    end_date_str = today_pst().strftime("%Y-%m-%d")
    
    start = parse_date(start_date_str)
    end = parse_date(end_date_str)
    
    # Sort transactions by date_received
    sorted_txns = sorted(transactions, key=lambda t: t["date_received"])
    
    # Preload all needed prices into memory
    price_cache = {}  # (cat, gid, pid) -> {date: price}
    all_product_keys = set()
    
    for txn in sorted_txns:
        if txn["type"].upper() == "TRADE":
            for item in txn.get("items_out", []):
                all_product_keys.add(_product_key(item))
            for item in txn.get("items_in", []):
                all_product_keys.add(_product_key(item))
        else:
            for item in txn.get("items", []):
                all_product_keys.add(_product_key(item))
    
    for key in all_product_keys:
        cat, gid, pid = key
        price_cache[key] = load_prices(cat, gid, pid)
    
    # Build daily summary by walking through each day
    summary = {}
    
    # Track cumulative cost_basis and compute total_value each day
    # Cost basis changes are discrete events; total_value depends on daily prices.
    
    # Compute inventory timeline
    inventory = compute_inventory_timeline(sorted_txns)
    
    # Build cost_basis events: {date_str: cost_basis_delta}
    cost_basis_deltas = defaultdict(float)
    
    for txn in sorted_txns:
        txn_date = txn["date_received"]
        txn_type = txn["type"].upper()
        
        if txn_type == "BUY":
            # Cost basis increases by total amount paid
            amount = txn.get("amount", 0)
            cost_basis_deltas[txn_date] += amount
            
        elif txn_type == "SELL":
            # Cost basis decreases by total amount received
            amount = txn.get("amount", 0)
            cost_basis_deltas[txn_date] -= amount
            
        elif txn_type == "OPEN":
            # No cost basis change
            pass
            
        elif txn_type == "TRADE":
            # Cost basis: decrease by cost_basis_out, increase by cost_basis_in
            cost_basis_deltas[txn_date] -= txn.get("cost_basis_out", 0)
            cost_basis_deltas[txn_date] += txn.get("cost_basis_in", 0)
    
    # Pre-sort price dates for each product so we can carry forward efficiently
    sorted_price_dates = {}
    for key, prices in price_cache.items():
        sorted_price_dates[key] = sorted(prices.keys())
    
    # Track the last known price per product for carry-forward
    last_known_price = {}  # key -> float
    
    # Walk through each day
    running_cost_basis = 0.0
    current = start
    
    while current <= end:
        d_str = current.strftime("%Y-%m-%d")
        
        # Update cost basis
        running_cost_basis += cost_basis_deltas.get(d_str, 0)
        
        # Compute total value: sum of (qty * price) for all products owned
        total_value = 0.0
        
        for key, inv in inventory.items():
            qty = get_quantity_on_date(inv, d_str)
            if qty > 0:
                prices = price_cache.get(key, {})
                price = prices.get(d_str, None)
                if price is not None and price > 0:
                    last_known_price[key] = price
                    total_value += qty * price
                elif key in last_known_price:
                    # Carry forward the most recent known price
                    total_value += qty * last_known_price[key]
        
        summary[d_str] = {
            "total_value": round(total_value, 2),
            "cost_basis": round(running_cost_basis, 2)
        }
        
        current += timedelta(days=1)
    
    return summary


def save_daily_summary(summary=None):
    """Derive and save the daily summary."""
    if summary is None:
        summary = derive_daily_summary()
    with open(DAILY_SUMMARY_FILE, "w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    # Update config with latest derived date so other parts of the app
    # can read the most recent summary date. Do this only if summary
    # has at least one date.
    try:
        if summary:
            latest = max(summary.keys())
            cfg = load_config()
            cfg["latest_date"] = latest
            save_config(cfg)
    except Exception:
        # Keep summary saving best-effort; don't raise on config write failures
        pass

    return summary


def load_daily_summary():
    """Load cached daily summary."""
    if not os.path.exists(DAILY_SUMMARY_FILE):
        return {}
    with open(DAILY_SUMMARY_FILE, "r") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Current holdings view
# ---------------------------------------------------------------------------
def get_current_holdings(transactions=None):
    """
    Returns list of currently held products with quantities and latest prices.
    """
    if transactions is None:
        transactions = load_transactions()
    
    inventory = compute_inventory_timeline(transactions)
    td = today_pst().strftime("%Y-%m-%d")
    
    holdings = []
    for key, inv in inventory.items():
        qty = get_quantity_on_date(inv, td)
        if qty > 0:
            cat, gid, pid = key
            mapping = get_mapping(gid, pid)
            prices = load_prices(cat, gid, pid)
            
            # Get latest available price
            latest_price = 0.0
            for d_str in sorted(prices.keys(), reverse=True):
                if d_str <= td and prices[d_str] and prices[d_str] > 0:
                    latest_price = prices[d_str]
                    break
            
            holdings.append({
                "categoryId": cat,
                "group_id": gid,
                "product_id": pid,
                "name": mapping["name"] if mapping else f"Unknown ({gid}/{pid})",
                "imageUrl": mapping.get("imageUrl", "") if mapping else "",
                "url": mapping.get("url", "") if mapping else "",
                "quantity": qty,
                "latest_price": latest_price,
                "total_value": round(qty * latest_price, 2)
            })
    
    holdings.sort(key=lambda h: h["total_value"], reverse=True)
    return holdings


# ---------------------------------------------------------------------------
# Helper: get all products ever owned (for price fetching)
# ---------------------------------------------------------------------------
def get_all_products(transactions=None):
    """Return set of (categoryId, group_id, product_id) for all products ever transacted."""
    if transactions is None:
        transactions = load_transactions()
    
    products = set()
    for txn in transactions:
        if txn["type"].upper() == "TRADE":
            for item in txn.get("items_out", []):
                products.add(_product_key(item))
            for item in txn.get("items_in", []):
                products.add(_product_key(item))
        else:
            for item in txn.get("items", []):
                products.add(_product_key(item))
    
    return products


def get_owned_date_ranges(transactions=None):
    """
    For each product, return the date ranges when it was owned.
    Used to know which dates need prices.
    
    Returns: dict (cat, gid, pid) -> list of (start_date_str, end_date_str)
    """
    if transactions is None:
        transactions = load_transactions()
    
    inventory = compute_inventory_timeline(transactions)
    td = today_pst().strftime("%Y-%m-%d")
    
    ranges = {}
    for key, inv in inventory.items():
        sorted_dates = sorted(inv.keys())
        if not sorted_dates:
            continue
        
        product_ranges = []
        range_start = None
        
        for d_str in sorted_dates:
            qty = inv[d_str]
            if qty > 0 and range_start is None:
                range_start = d_str
            elif qty <= 0 and range_start is not None:
                product_ranges.append((range_start, d_str))
                range_start = None
        
        # If still owned, range extends to today
        if range_start is not None:
            product_ranges.append((range_start, td))
        
        if product_ranges:
            ranges[key] = product_ranges
    
    return ranges
