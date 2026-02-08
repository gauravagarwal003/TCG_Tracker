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
from datetime import datetime

from engine import (
    load_transactions, today_pst, derive_daily_summary,
    save_daily_summary, get_current_holdings, load_daily_summary,
    BASE_DIR
)
from price_fetcher import fetch_today_prices, update_prices


def main():
    print("=" * 60)
    print(f"Pokemon Tracker - Daily Run")
    print(f"Date: {today_pst()}")
    print("=" * 60)
    
    transactions = load_transactions()
    if not transactions:
        print("No transactions found. Exiting.")
        return
    
    # Step 1: Fetch today's prices
    print("\n--- Step 1: Fetching today's prices ---")
    fetch_today_prices()
    
    # Step 2: Re-derive summary
    print("\n--- Step 2: Deriving daily summary ---")
    summary = derive_daily_summary(transactions)
    save_daily_summary(summary)
    
    td = today_pst().strftime("%Y-%m-%d")
    if td in summary:
        s = summary[td]
        print(f"  Today: value=${s['total_value']:.2f}, cost_basis=${s['cost_basis']:.2f}")
    
    # Step 3: Generate static files for GitHub Pages
    print("\n--- Step 3: Generating static data ---")
    
    # Write holdings for frontend
    holdings = get_current_holdings(transactions)
    holdings_file = os.path.join(BASE_DIR, "docs", "data", "holdings.json")
    os.makedirs(os.path.dirname(holdings_file), exist_ok=True)
    with open(holdings_file, "w") as f:
        json.dump(holdings, f, indent=2)
    
    # Copy summary to docs for frontend
    summary_file = os.path.join(BASE_DIR, "docs", "data", "daily_summary.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f)
    
    # Copy transactions to docs for frontend
    txn_file = os.path.join(BASE_DIR, "docs", "data", "transactions.json")
    with open(txn_file, "w") as f:
        json.dump(transactions, f)
    
    print(f"  Wrote holdings ({len(holdings)} items), summary ({len(summary)} days), transactions ({len(transactions)})")
    
    print("\n✅ Daily run complete.")


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


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        backfill()
    else:
        main()
