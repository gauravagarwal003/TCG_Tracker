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
from datetime import datetime

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


def generate_static_site(transactions, summary):
    print("\n--- Step 3: Generating static data ---")

    # The public GitHub Pages site now reads user-specific data from Firestore.
    # Keep docs/data as empty placeholders so no user portfolio data is exposed
    # via public static JSON files.
    holdings = []
    holdings_file = os.path.join(BASE_DIR, "docs", "data", "holdings.json")
    os.makedirs(os.path.dirname(holdings_file), exist_ok=True)
    with open(holdings_file, "w") as f:
        json.dump(holdings, f, indent=2)

    # Summary placeholder
    summary_file = os.path.join(BASE_DIR, "docs", "data", "daily_summary.json")
    with open(summary_file, "w") as f:
        json.dump({}, f)

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

    print(
        "  Wrote empty public placeholders for holdings, summary, and transactions"
    )

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
    Daily mode for multi-user setup:
      1) Build union product list from Firestore
      2) Fetch today's prices once for that union
      3) Publish shared prices and derived local docs assets
    """
    print("=" * 60)
    print("TCG Tracker - Firebase Union Daily Run")
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
