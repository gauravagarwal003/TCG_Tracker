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
    BASE_DIR
)
from price_fetcher import fetch_today_prices, update_prices

# For static site generation
try:
    from app import app as flask_app
    from engine import load_mappings
    from flask import render_template
except Exception:
    flask_app = None
    render_template = None
    load_mappings = None


def generate_static_site(transactions, summary):
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

    print(
        f"  Wrote holdings ({len(holdings)} items), summary ({len(summary)} days), transactions ({len(transactions)})"
    )

    # Attempt to regenerate static HTML pages in docs/ so GitHub Pages shows
    # the latest derived data (only if Flask app is importable).
    try:
        if flask_app and render_template:
            print("\n--- Rendering static HTML pages to docs/ ---")
            with flask_app.app_context():
                static_css_path = os.path.join(BASE_DIR, "static", "css", "styles.css")
                try:
                    static_version = int(os.path.getmtime(static_css_path))
                except OSError:
                    static_version = int(datetime.utcnow().timestamp())

                # Index
                total_value = sum(h.get("total_value", 0) for h in holdings)
                total_cost_basis = 0
                if summary:
                    latest = max(summary.keys())
                    total_cost_basis = summary[latest].get("cost_basis", 0)

                index_html = render_template(
                    "index.html",
                    holdings=holdings,
                    total_value=total_value,
                    total_cost_basis=total_cost_basis,
                    summary=summary,
                    active_page="index",
                    is_static=True,
                    static_version=static_version
                )
                with open(os.path.join(BASE_DIR, "docs", "index.html"), "w") as f:
                    f.write(index_html)

                # Transactions
                transactions_html = render_template(
                    "transactions.html",
                    transactions=transactions,
                    mappings=mappings,
                    active_page="transactions",
                    is_static=True,
                    static_version=static_version
                )
                with open(os.path.join(BASE_DIR, "docs", "transactions.html"), "w") as f:
                    f.write(transactions_html)

                # Add-transaction (transaction form) -> docs/add-transaction.html
                add_tx_html = render_template(
                    "transaction_form.html",
                    transaction=None,
                    mappings=mappings,
                    is_edit=False,
                    is_static=True,
                    static_version=static_version
                )
                with open(os.path.join(BASE_DIR, "docs", "add-transaction.html"), "w") as f:
                    f.write(add_tx_html)

            print("  Regenerated docs/index.html, docs/transactions.html, docs/add-transaction.html")
    except Exception as e:
        print("  Skipped static HTML regeneration:", e)


def main():
    print("=" * 60)
    print(f"TCG Tracker - Daily Run")
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
    generate_static_site(transactions, summary)

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


def docs_only():
    """Regenerate GitHub Pages assets without fetching new prices."""
    print("=" * 60)
    print("TCG Tracker - Docs-Only Rebuild")
    print("=" * 60)

    transactions = load_transactions()
    if not transactions:
        print("No transactions found. Exiting.")
        return

    summary = load_daily_summary()
    if not summary:
        print("Daily summary missing, deriving from existing prices...")
        summary = derive_daily_summary(transactions)
        save_daily_summary(summary)

    generate_static_site(transactions, summary)

    print("\n✅ Docs-only rebuild complete.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--backfill":
        backfill()
    elif len(sys.argv) > 1 and sys.argv[1] == "--docs-only":
        docs_only()
    else:
        main()
