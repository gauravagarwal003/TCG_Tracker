"""
transaction_manager.py - Add, edit, delete transactions

All mutations go through this module. After any change:
  1. Validates inventory (no negatives)
  2. Fetches any missing prices
  3. Re-derives and saves daily_summary.json
"""

import uuid
from datetime import datetime

from engine import (
    load_transactions, save_transactions, validate_inventory,
    save_daily_summary, derive_daily_summary, today_pst,
    get_mapping, load_mappings, save_mappings,
    _product_key, parse_date
)
from price_fetcher import update_prices


def _generate_id():
    return str(uuid.uuid4())[:8]


def _validate_date(date_str):
    """Validate date is not in the future (PST)."""
    try:
        d = parse_date(date_str)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")
    
    if d > today_pst():
        raise ValueError(f"Date {date_str} is in the future. Transactions cannot be future-dated.")
    
    return date_str


def _ensure_mapping(items):
    """Ensure all items in a transaction have mappings. Auto-create if needed."""
    mappings = load_mappings()
    mapping_keys = {(str(m["group_id"]), str(m["product_id"])) for m in mappings}
    
    for item in items:
        # Require explicit categoryId on items
        if "categoryId" not in item:
            raise ValueError(f"Transaction item missing 'categoryId': {item}")
        key = (str(item["group_id"]), str(item["product_id"]))
        if key not in mapping_keys:
            new_mapping = {
                "product_id": str(item["product_id"]),
                "name": item.get("name", f"Product {item['product_id']}"),
                "group_id": str(item["group_id"]),
                "imageUrl": f"https://tcgplayer-cdn.tcgplayer.com/product/{item['product_id']}_200w.jpg",
                "categoryId": int(item["categoryId"]),
                "url": f"https://www.tcgplayer.com/product/{item['product_id']}"
            }
            mappings.append(new_mapping)
            mapping_keys.add(key)
    
    save_mappings(mappings)


def _get_all_items(txn):
    """Get all items from a transaction regardless of type."""
    if txn["type"].upper() == "TRADE":
        return txn.get("items_out", []) + txn.get("items_in", [])
    return txn.get("items", [])


def _fetch_prices_for_transaction(txn):
    """Fetch any missing prices for a transaction's products."""
    items = _get_all_items(txn)
    product_keys = set()
    for item in items:
        product_keys.add(_product_key(item))
    
    if product_keys:
        print(f"Checking prices for {len(product_keys)} product(s)...")
        update_prices(product_keys=product_keys)


def add_transaction(txn_data):
    """
    Add a new transaction.
    
    Args:
        txn_data: dict with keys:
            - date_purchased: str (YYYY-MM-DD) - informational only
            - date_received: str (YYYY-MM-DD) - used for all calculations
            - type: str (BUY, SELL, OPEN, TRADE)
            - items: list of {group_id, product_id, categoryId, name, quantity}
              (for BUY, SELL, OPEN)
            - items_out / items_in: (for TRADE)
            - amount: float (total paid for BUY, total received for SELL)
            - cost_basis_out / cost_basis_in: float (for TRADE)
            - method, place, notes: str (optional)
    
    Returns:
        (success: bool, message: str, txn: dict)
    """
    # Validate date
    try:
        _validate_date(txn_data["date_received"])
        if txn_data.get("date_purchased"):
            _validate_date(txn_data["date_purchased"])
    except ValueError as e:
        return False, str(e), None
    
    # Assign ID
    txn_data["id"] = _generate_id()
    
    # Ensure mappings exist (and that items include categoryId)
    try:
        _ensure_mapping(_get_all_items(txn_data))
    except ValueError as e:
        return False, str(e), None
    
    # Validate inventory
    transactions = load_transactions()
    valid, error = validate_inventory(transactions, new_txn=txn_data)
    if not valid:
        return False, f"Inventory validation failed: {error}", None
    
    # Add transaction
    transactions.append(txn_data)
    save_transactions(transactions)
    
    # Fetch prices
    _fetch_prices_for_transaction(txn_data)
    
    # Re-derive summary
    summary = derive_daily_summary(transactions)
    save_daily_summary(summary)
    
    return True, "Transaction added successfully.", txn_data


def delete_transaction(txn_id):
    """
    Delete a transaction by ID.
    
    Returns:
        (success: bool, message: str)
    """
    transactions = load_transactions()
    
    # Find transaction
    txn = None
    txn_index = None
    for i, t in enumerate(transactions):
        if t["id"] == txn_id:
            txn = t
            txn_index = i
            break
    
    if txn is None:
        return False, f"Transaction {txn_id} not found."
    
    # Validate inventory after removal
    valid, error = validate_inventory(transactions, exclude_txn_id=txn_id)
    if not valid:
        return False, f"Cannot delete: {error}"
    
    # Remove transaction
    transactions.pop(txn_index)
    save_transactions(transactions)
    
    # Re-derive summary (prices already exist)
    summary = derive_daily_summary(transactions)
    save_daily_summary(summary)
    
    return True, f"Transaction {txn_id} deleted successfully."


def edit_transaction(txn_id, new_data):
    """
    Edit a transaction = delete old + add new.
    
    Returns:
        (success: bool, message: str, txn: dict)
    """
    transactions = load_transactions()
    
    # Find old transaction
    old_txn = None
    old_index = None
    for i, t in enumerate(transactions):
        if t["id"] == txn_id:
            old_txn = t
            old_index = i
            break
    
    if old_txn is None:
        return False, f"Transaction {txn_id} not found.", None
    
    # Validate date
    try:
        _validate_date(new_data["date_received"])
        if new_data.get("date_purchased"):
            _validate_date(new_data["date_purchased"])
    except ValueError as e:
        return False, str(e), None
    
    # Keep the same ID
    new_data["id"] = txn_id
    
    # Ensure mappings (and that items include categoryId)
    try:
        _ensure_mapping(_get_all_items(new_data))
    except ValueError as e:
        return False, str(e), None
    
    # Validate: remove old, add new
    test_txns = [t for t in transactions if t["id"] != txn_id]
    test_txns.append(new_data)
    valid, error = validate_inventory(test_txns)
    if not valid:
        return False, f"Inventory validation failed: {error}", None
    
    # Apply
    transactions[old_index] = new_data
    save_transactions(transactions)
    
    # Fetch prices for new data
    _fetch_prices_for_transaction(new_data)
    
    # Re-derive summary
    summary = derive_daily_summary(transactions)
    save_daily_summary(summary)
    
    return True, "Transaction updated successfully.", new_data
