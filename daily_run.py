"""
daily_run.py - Daily price update script for GitHub Actions.

Runs at 3:00 PM PST via GitHub Actions:
  1. Pull latest prices for all currently held products
  2. Re-derive daily summary
  3. Generate static site files (daily_summary.json for GitHub Pages)
"""

import sys
import json
import os
import shutil
from datetime import datetime, timezone

from engine import (
    load_transactions, today_pst, derive_daily_summary,
    save_daily_summary, get_current_holdings, load_daily_summary,
    BASE_DIR, load_mappings
)
from price_fetcher import (
    fetch_today_prices,
    update_prices,
    fetch_prices_for_product_keys_on_date,
    update_prices_for_product_date_ranges,
)

# For static site generation
try:
    from app import app as flask_app
    from flask import render_template
except Exception:
    flask_app = None
    render_template = None


def build_widget_summary(summary, holdings):
    summary_dates = sorted((summary or {}).keys())
    latest_date = summary_dates[-1] if summary_dates else None
    previous_date = summary_dates[-2] if len(summary_dates) > 1 else None

    latest = summary.get(latest_date, {}) if latest_date else {}
    previous = summary.get(previous_date, {}) if previous_date else {}

    total_value = float(latest.get("total_value", 0) or 0)
    cost_basis = float(latest.get("cost_basis", 0) or 0)
    previous_total_value = float(previous.get("total_value", 0) or 0)
    previous_cost_basis = float(previous.get("cost_basis", 0) or 0)

    lifetime_gain_loss = total_value - cost_basis
    previous_lifetime_gain_loss = previous_total_value - previous_cost_basis
    day_value_change = total_value - previous_total_value if previous_date else 0
    day_cost_basis_change = cost_basis - previous_cost_basis if previous_date else 0
    day_gain_loss = lifetime_gain_loss - previous_lifetime_gain_loss if previous_date else 0

    return {
        "latest_date": latest_date,
        "previous_date": previous_date,
        "total_value": round(total_value, 2),
        "cost_basis": round(cost_basis, 2),
        "gain_loss": round(lifetime_gain_loss, 2),
        "return_pct": round((lifetime_gain_loss / cost_basis) * 100, 2) if cost_basis else 0,
        "day_value_change": round(day_value_change, 2),
        "day_cost_basis_change": round(day_cost_basis_change, 2),
        "day_gain_loss": round(day_gain_loss, 2),
        "day_gain_loss_pct": round((day_gain_loss / previous_total_value) * 100, 2) if previous_total_value else 0,
        "holdings_count": len(holdings),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def generate_static_site(transactions, summary):
    print("\n--- Step 3: Generating static data ---")

    # Scriptable widgets read these public GitHub Pages JSON files directly.
    holdings = get_current_holdings(transactions)
    widget_summary = build_widget_summary(summary, holdings)

    holdings_file = os.path.join(BASE_DIR, "docs", "data", "holdings.json")
    os.makedirs(os.path.dirname(holdings_file), exist_ok=True)
    with open(holdings_file, "w") as f:
        json.dump(holdings, f, indent=2)

    summary_file = os.path.join(BASE_DIR, "docs", "data", "daily_summary.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    widget_summary_file = os.path.join(BASE_DIR, "docs", "data", "widget_summary.json")
    with open(widget_summary_file, "w") as f:
        json.dump(widget_summary, f, indent=2)

    # Transactions placeholder
    txn_file = os.path.join(BASE_DIR, "docs", "data", "transactions.json")
    with open(txn_file, "w") as f:
        json.dump([], f)

    # Copy mappings to docs for frontend (metadata / names / images)
    mappings = load_mappings() if load_mappings else {}
    mappings_file = os.path.join(BASE_DIR, "docs", "data", "mappings.json")
    with open(mappings_file, "w") as f:
        json.dump(mappings, f, indent=2)

    # Sync static assets for GitHub Pages (CSS/JS/etc.)
    static_src = os.path.join(BASE_DIR, "static")
    static_dest = os.path.join(BASE_DIR, "docs", "static")
    if os.path.isdir(static_src):
        shutil.copytree(static_src, static_dest, dirs_exist_ok=True)

    # Sync prices directory for GitHub Pages (needed for 1-week change calculations)
    prices_src = os.path.join(BASE_DIR, "prices")
    prices_dest = os.path.join(BASE_DIR, "docs", "prices")
    if os.path.isdir(prices_src):
        shutil.copytree(prices_src, prices_dest, dirs_exist_ok=True)

    print(f"  Wrote public widget data: {len(holdings)} holdings")

    # Static HTML pages are now maintained directly in docs/ so they can
    # contain the Firebase auth and Firestore client logic. Do not overwrite
    # them from the Flask templates anymore.
    print("  Skipped HTML regeneration (docs pages are Firebase client pages now)")


def main():
    print("=" * 60)
    print(f"TCG Tracker - Daily Run")
    print(f"Date: {today_pst()}")
    print("=" * 60)
    
    transactions = load_transactions()
    if not transactions:
        print("No transactions found. Exiting.")
        return
    
    # Step 1: Fetch today's prices for all products owned today
    # Use update_prices constrained to today's date so the daily job
    # fetches and saves prices (and fills gaps) as the single committer.
    print("\n--- Step 1: Fetching today's prices ---")
    td = today_pst().strftime("%Y-%m-%d")
    try:
        update_prices(start_date_str=td, end_date_str=td)
    except Exception as e:
        print('fetch/update today prices failed:', e)
        raise
    
    # Step 2: Re-derive summary
    print("\n--- Step 2: Deriving daily summary ---")
    summary = derive_daily_summary(transactions)
    save_daily_summary(summary)
    
    td = today_pst().strftime("%Y-%m-%d")
    if td in summary:
        s = summary[td]
        print(f"  Today: value=${s['total_value']:.2f}, cost_basis=${s['cost_basis']:.2f}")
    
    # Step 3: Generate static files for GitHub Pages
    generate_static_site(transactions, summary)

    print("\n✅ Daily run complete.")


def firebase_union_daily_run():
    """
    Daily mode for owner Firestore setup:
      1) Build product list from Firestore transactions
      2) Fetch today's prices once for that product set
      3) Publish shared prices and derived local docs assets
    """
    print("=" * 60)
    print("TCG Tracker - Firestore Daily Run")
    print(f"Date: {today_pst()}")
    print("=" * 60)

    td = today_pst().strftime("%Y-%m-%d")

    try:
        from firebase_union import (
            init_firestore_from_env,
            get_union_product_date_ranges,
            get_union_product_keys,
        )
    except Exception as e:
        raise RuntimeError(
            "Firebase union mode requires firebase_union.py and firebase-admin dependency"
        ) from e

    print("\n--- Step 1: Loading union product keys from Firestore ---")
    db = init_firestore_from_env()
    product_ranges = get_union_product_date_ranges(db, end_date_str=td)
    union_keys = set(product_ranges.keys())
    if not union_keys:
        union_keys = get_union_product_keys(db)
    print(f"  Loaded {len(union_keys)} unique product keys")

    if not union_keys:
        print("No active products found in Firestore. Exiting without fetch.")
        return

    print("\n--- Step 2: Fetching prices for union product ranges ---")
    if product_ranges:
        gaps = update_prices_for_product_date_ranges(product_ranges, end_date_str=td)
        print(f"  Range fetch complete: products={len(product_ranges)}, gaps={len(gaps)}")
    else:
        stats = fetch_prices_for_product_keys_on_date(td, union_keys, carry_forward=True)
        print(
            f"  Requested={stats['requested']}, found={stats['found']}, carried={stats['carried']}, missing={len(stats['missing'])}"
        )

    # Keep current local docs generation path so GitHub Pages static assets remain updated.
    print("\n--- Step 3: Rebuilding local derived assets ---")
    transactions = load_transactions()
    summary = derive_daily_summary(transactions)
    save_daily_summary(summary)
    generate_static_site(transactions, summary)

    print("\n✅ Firebase union daily run complete.")


def backfill():
    """Backfill all missing prices for all owned products."""
    print("=" * 60)
    print("Backfilling all missing prices...")
    print("=" * 60)
    
    gaps = update_prices()
    
    print("\nRe-deriving summary...")
    summary = derive_daily_summary()
    save_daily_summary(summary)
    
    print("✅ Backfill complete.")


def docs_only():
    """Regenerate GitHub Pages assets without fetching new prices."""
    print("=" * 60)
    print("TCG Tracker - Docs-Only Rebuild")
    print("=" * 60)

    transactions = load_transactions()
    if not transactions:
        print("No transactions found. Exiting.")
        return

    # Always re-derive from transactions in docs-only mode.
    # Relying on cached daily_summary.json can keep stale/incorrect graph data
    # after transaction recovery or manual edits.
    print("Deriving daily summary from transactions...")
    summary = derive_daily_summary(transactions)
    save_daily_summary(summary)

    generate_static_site(transactions, summary)

    print("\n✅ Docs-only rebuild complete.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        backfill()
    elif len(sys.argv) > 1 and sys.argv[1] == "--docs-only":
        docs_only()
    elif len(sys.argv) > 1 and sys.argv[1] == "--firebase-union":
        firebase_union_daily_run()
    else:
        main()
