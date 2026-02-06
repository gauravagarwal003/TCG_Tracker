"""
Incremental portfolio update for Pokemon Tracker.

Instead of rebuilding the entire daily_tracker.csv from scratch (which requires
price data for ALL products on ALL days), this script applies targeted deltas
for only the changed transactions.  This ensures that adding/editing/deleting a
single transaction never affects unrelated products.

Flow (when run as __main__):
  1. Read transaction_changes.json   (written by detect_changes.py)
  2. Fetch prices for changed products only
  3. Validate inventory won't go negative
  4. Apply deltas to daily_tracker.csv
  5. Rebuild current_holdings.csv & regenerate graphs
  6. Clean up the temp JSON file

Falls back to a full analyze_portfolio rebuild if incremental isn't possible.
"""

import pandas as pd
import json
import math
import os
from datetime import datetime
from functions import get_price_for_date, get_product_info_from_ids
import plotly.graph_objects as go


CHANGES_FILE = "transaction_changes.json"


# ── Small helpers ────────────────────────────────────────────────────────────

def _parse_currency(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value.replace("$", "").replace(",", "").strip() or 0)
    return 0.0


def _normalize_id(value):
    try:
        return str(int(float(value)))
    except (ValueError, TypeError):
        return str(value).strip()


def _parse_tx_date(date_str):
    if date_str is None:
        return None
    s = str(date_str).strip()
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _category_for(gid, pid):
    info = get_product_info_from_ids(gid, pid)
    if info and info.get("categoryId"):
        return info["categoryId"]
    return 3  # default: Pokemon


def _get_latest_price(gid, pid, date_str, category_id=3, max_lookback=7):
    """
    Try to get the price for date_str.  If no file exists, search backwards
    up to max_lookback days to find the most recent available price.
    Used for the holdings snapshot where we want the "latest known" price,
    not a hard 0.0 just because today's dump hasn't arrived yet.
    """
    from datetime import timedelta
    d = datetime.strptime(date_str, "%Y-%m-%d")
    for i in range(max_lookback + 1):
        check = (d - timedelta(days=i)).strftime("%Y-%m-%d")
        price = get_price_for_date(gid, pid, check, category_id)
        if price > 0:
            return price
    return 0.0


# ── Validation ───────────────────────────────────────────────────────────────

def validate_inventory(transactions_file, changed_products):
    """
    Replay every transaction for each changed product and ensure inventory
    never goes negative.  Returns (ok, error_message).
    """
    try:
        df = pd.read_csv(transactions_file)
    except Exception as e:
        return False, f"Cannot read transactions: {e}"

    for gid_raw, pid_raw in changed_products:
        gid, pid = _normalize_id(gid_raw), _normalize_id(pid_raw)

        txs = []
        for _, row in df.iterrows():
            try:
                if _normalize_id(row["group_id"]) != gid or _normalize_id(row["product_id"]) != pid:
                    continue
                d = _parse_tx_date(row.get("Date Recieved", ""))
                if not d:
                    continue
                txs.append({
                    "date": d,
                    "type": str(row.get("Transaction Type", "")).strip().upper(),
                    "qty": float(row["Quantity"]) if pd.notna(row.get("Quantity")) else 1.0,
                })
            except (ValueError, TypeError):
                continue

        txs.sort(key=lambda t: t["date"])
        qty = 0.0
        for t in txs:
            qty += t["qty"] if t["type"] in ("BUY", "PULL") else -t["qty"]
            if qty < -0.001:
                return False, (
                    f"Product ({gid}, {pid}) would go to {qty:.1f} "
                    f"on {t['date'].strftime('%m/%d/%Y')}."
                )

    return True, ""


# ── Date gap validation ──────────────────────────────────────────────────────

def validate_no_missing_dates(tracker_df):
    """
    Check that the tracker has no date gaps.  If any are found, print them
    and HALT the process so the user can investigate.
    Returns the list of missing dates (empty = all good).
    """
    if tracker_df.empty:
        return []
    dates = pd.to_datetime(tracker_df["Date"])
    expected = set(pd.date_range(dates.min(), dates.max(), freq="D"))
    actual = set(dates)
    missing = sorted(expected - actual)
    if missing:
        print(f"\n🚨🚨🚨 MISSING DATES DETECTED ({len(missing)}): 🚨🚨🚨")
        for d in missing:
            print(f"   - {d.date()}")
        print("\nProcess STOPPED. Fix the missing price data before continuing.")
        print("daily_tracker.csv has been saved but contains gaps.")
        import sys
        sys.exit(1)
    else:
        print(f"✅ Date continuity verified: {len(actual)} days, no gaps.")
    return missing


# ── Core: apply one delta ────────────────────────────────────────────────────

def _apply_delta(tracker_df, tx, removing=False):
    """
    Adjust every tracker row from the transaction date onward.

    Adding a BUY  → +price*qty to value, +cost to basis, +qty to items
    Adding a SELL → −price*qty to value, −cost to basis, −qty to items
    Adding an OPEN/TRADE → −price*qty to value, basis unchanged, −qty to items
    Removing any of the above flips every sign.
    """
    tx_type = str(tx.get("Transaction Type", "")).strip().upper()

    raw_qty = tx.get("Quantity", "")
    if raw_qty == "" or raw_qty is None or (isinstance(raw_qty, float) and math.isnan(raw_qty)):
        quantity = 1.0
    else:
        try:
            quantity = float(raw_qty)
        except (ValueError, TypeError):
            quantity = 1.0

    cost = _parse_currency(tx.get("Price Per Unit", 0)) * quantity
    gid = _normalize_id(tx.get("group_id", ""))
    pid = _normalize_id(tx.get("product_id", ""))
    tx_date = _parse_tx_date(tx.get("Date Recieved", ""))
    if not tx_date:
        print(f"  Warning: Skipping (unparseable date): {tx.get('Date Recieved')}")
        return

    # Base signs for an ADD
    if tx_type in ("BUY", "PULL"):
        val_sign, basis_delta, items_delta = +1, +cost, +quantity
    elif tx_type == "SELL":
        val_sign, basis_delta, items_delta = -1, -cost, -quantity
    elif tx_type in ("OPEN", "TRADE"):
        val_sign, basis_delta, items_delta = -1, 0, -quantity
    else:
        print(f"  Warning: Skipping unknown type: {tx_type}")
        return

    if removing:
        val_sign *= -1
        basis_delta *= -1
        items_delta *= -1

    label = "Removing" if removing else "Adding"
    name = tx.get("Item", tx.get("Product Name", "?"))
    print(f"  {label} {tx_type}: {name} x{quantity}  (from {tx.get('Date Recieved', '?')})")

    cat = _category_for(gid, pid)
    mask = tracker_df["Date"] >= pd.to_datetime(tx_date)

    for idx in tracker_df[mask].index:
        day = tracker_df.at[idx, "Date"].strftime("%Y-%m-%d")
        price = get_price_for_date(gid, pid, day, cat)
        if price <= 0:
            # Fallback: search nearby dates for a known price.
            # This handles cases where a specific day's price file is
            # missing (e.g. holidays, data-source gaps).
            price = _get_latest_price(gid, pid, day, cat, max_lookback=7)
        if price <= 0:
            print(f"    WARNING: No price found for ({gid},{pid}) on {day} — value delta will be $0")
        tracker_df.at[idx, "Total Value"]  += val_sign * price * quantity
        tracker_df.at[idx, "Cost Basis"]   += basis_delta
        tracker_df.at[idx, "Items Owned"]  += items_delta

    print(f"    -> Updated {mask.sum()} days in tracker")


# ── Apply all deltas ─────────────────────────────────────────────────────────

def apply_incremental_update(added_txs, removed_txs, changed_products=None):
    """Read the existing tracker, apply deltas, save everything."""
    print("--- Incremental Portfolio Update ---")

    with open("data.json") as f:
        config = json.load(f)

    # ── Load tracker ────────────────────────────────────────────────────────
    if not os.path.exists("daily_tracker.csv"):
        print("No daily_tracker.csv — falling back to full rebuild.")
        _full_rebuild()
        return

    tracker = pd.read_csv("daily_tracker.csv")
    if tracker.empty:
        print("Empty daily_tracker.csv — falling back to full rebuild.")
        _full_rebuild()
        return

    tracker["Date"] = pd.to_datetime(tracker["Date"])
    earliest_tracker = tracker["Date"].min()

    # Bail out if any change predates the tracker
    for tx in removed_txs + added_txs:
        d = _parse_tx_date(tx.get("Date Recieved", ""))
        if d and pd.to_datetime(d) < earliest_tracker:
            print(f"Transaction on {tx.get('Date Recieved')} predates tracker — full rebuild.")
            _full_rebuild()
            return

    # ── Apply deltas (removals first, then adds) ───────────────────────────
    print(f"Applying {len(removed_txs)} removals, {len(added_txs)} additions...")
    for tx in removed_txs:
        _apply_delta(tracker, tx, removing=True)
    for tx in added_txs:
        _apply_delta(tracker, tx, removing=False)

    tracker["Total Value"] = tracker["Total Value"].round(2)
    tracker["Cost Basis"]  = tracker["Cost Basis"].round(2)
    tracker["Items Owned"] = tracker["Items Owned"].round(1)

    tracker.to_csv("daily_tracker.csv", index=False)
    print("daily_tracker.csv saved.")

    # ── Validate no date gaps ───────────────────────────────────────────────
    validate_no_missing_dates(tracker)

    # ── Rebuild holdings & graphs ───────────────────────────────────────────
    _rebuild_holdings(config, changed_products or [])
    _rebuild_graphs(tracker)
    print("--- Done ---")


# ── Holdings snapshot ────────────────────────────────────────────────────────

def _rebuild_holdings(config, changed_products):
    """
    Incrementally update current_holdings.csv — only re-compute rows for
    products that actually changed.  Every other row is left untouched,
    which avoids the need to look up prices for products whose price
    files may not exist on the CI runner (historical_prices/ is gitignored).
    """
    mappings_file = config.get("mappings_file", "mappings.json")
    name_map, image_map = {}, {}
    try:
        with open(mappings_file) as f:
            for m in json.load(f):
                key = (str(m.get("group_id", "")), str(m.get("product_id", "")))
                name_map[key]  = m.get("name", "Unknown")
                image_map[key] = m.get("imageUrl", "")
    except Exception:
        pass

    tx_file = config.get("transactions_file", "transactions.csv")
    latest  = config.get("latest_date", datetime.now().strftime("%Y-%m-%d"))

    # Normalize the changed set for fast lookup
    changed_set = set()
    for g, p in changed_products:
        changed_set.add((_normalize_id(g), _normalize_id(p)))

    # ── Replay transactions only for changed products to get new qty ─────
    try:
        df = pd.read_csv(tx_file)
    except Exception as e:
        print(f"  Error reading {tx_file}: {e}")
        return

    inv = {}  # only for changed products
    for _, r in df.iterrows():
        try:
            key = (_normalize_id(r["group_id"]), _normalize_id(r["product_id"]))
            if key not in changed_set:
                continue
            t = str(r["Transaction Type"]).strip().upper()
            q = float(r["Quantity"]) if pd.notna(r.get("Quantity")) else 1.0
            if t in ("BUY", "PULL"):
                inv[key] = inv.get(key, 0) + q
            elif t in ("SELL", "OPEN", "TRADE"):
                inv[key] = max(inv.get(key, 0) - q, 0)
        except (ValueError, TypeError):
            continue

    # ── Load existing holdings (untouched rows are kept as-is) ──────────
    cols = ["Product Name", "group_id", "product_id", "Quantity",
            "Latest Price", "Total Value", "Image URL"]
    if os.path.exists("current_holdings.csv"):
        try:
            holdings = pd.read_csv("current_holdings.csv")
        except Exception:
            holdings = pd.DataFrame(columns=cols)
    else:
        holdings = pd.DataFrame(columns=cols)

    # Index existing rows by (group_id, product_id) for fast patching
    holdings["_key"] = holdings.apply(
        lambda r: (_normalize_id(r["group_id"]), _normalize_id(r["product_id"])), axis=1
    )

    # ── Patch changed rows ──────────────────────────────────────────────
    for (gid, pid) in changed_set:
        qty = inv.get((gid, pid), 0)
        mask = holdings["_key"] == (gid, pid)

        if qty > 0:
            cat   = _category_for(gid, pid)
            price = _get_latest_price(gid, pid, latest, cat)
            row_data = {
                "Product Name": name_map.get((gid, pid), "Unknown"),
                "group_id": gid, "product_id": pid,
                "Quantity": qty, "Latest Price": price,
                "Total Value": price * qty,
                "Image URL": image_map.get((gid, pid), ""),
            }
            if mask.any():
                # Update existing row
                for col, val in row_data.items():
                    holdings.loc[mask, col] = val
            else:
                # New product — append
                new_row = pd.DataFrame([row_data], columns=cols)
                new_row["_key"] = [(gid, pid)]
                holdings = pd.concat([holdings, new_row], ignore_index=True)
        else:
            # Product fully sold / removed — drop from holdings
            holdings = holdings[~mask]

    holdings.drop(columns=["_key"], inplace=True)
    holdings.to_csv("current_holdings.csv", index=False)
    print(f"  current_holdings.csv: {len(holdings)} products (patched {len(changed_set)})")


# ── Graphs ───────────────────────────────────────────────────────────────────

def _rebuild_graphs(df):
    if df.empty:
        return

    # Portfolio value
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Total Value"],
        mode="lines", name="Portfolio Value",
        line=dict(color="#00C851", width=3), stackgroup="one",
    ))
    fig.add_trace(go.Scatter(
        x=df["Date"], y=df["Cost Basis"],
        mode="lines", name="Net Investment (Cost Basis)",
        line=dict(color="#ff4444", width=2, dash="dash"),
    ))
    fig.update_layout(
        title="Pokemon Investment Tracker",
        xaxis_title="Date", yaxis_title="Value ($)",
        hovermode="x unified", template="plotly_white",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )
    fig.write_html("portfolio_graph.html")

    # Performance ratio
    ratio = df.copy()
    ratio["Performance Ratio"] = ratio.apply(
        lambda r: r["Total Value"] / r["Cost Basis"] if abs(r["Cost Basis"]) > 0.01 else 0.0,
        axis=1,
    )
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=ratio["Date"], y=ratio["Performance Ratio"],
        mode="lines", name="Value / Net Investment",
        line=dict(color="#4f46e5", width=3),
    ))
    fig2.add_shape(
        type="line",
        x0=ratio["Date"].min(), y0=1,
        x1=ratio["Date"].max(), y1=1,
        line=dict(color="#64748b", width=2, dash="dot"),
    )
    fig2.update_layout(
        title="Portfolio Performance (Value / Net Investment)",
        xaxis_title="Date", yaxis_title="Ratio (>1 = Profit)",
        hovermode="x unified", template="plotly_white",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )
    fig2.write_html("performance_graph.html")
    print("  Graphs regenerated.")


# ── Fallback ─────────────────────────────────────────────────────────────────

def _full_rebuild(resume_date=None):
    import update_prices
    import analyze_portfolio
    update_prices.main(start_from_date=resume_date)
    analyze_portfolio.run_analysis(resume_date=resume_date)


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(CHANGES_FILE):
        print("No transaction_changes.json found — running full rebuild.")
        _full_rebuild()
        return

    with open(CHANGES_FILE) as f:
        changes = json.load(f)

    resume_date      = changes.get("resume_date")
    changed_products = changes.get("changed_products", [])
    added            = changes.get("added", [])
    removed          = changes.get("removed", [])

    if not added and not removed:
        print("No changes to apply.")
        _cleanup()
        return

    # 1. Fetch prices for changed products only
    #    Pass removed transactions so prices are fetched for dates that
    #    WERE active before the removal (needed to reverse the value delta).
    import update_prices
    if changed_products:
        print(f"Fetching prices for {len(changed_products)} products...")
        update_prices.main(
            start_from_date=resume_date,
            product_filter=changed_products,
            extra_active_transactions=removed,
        )

    # 2. Validate inventory constraints
    ok, err = validate_inventory("transactions.csv", changed_products)
    if not ok:
        print(f"WARNING: Inventory validation failed: {err}")
        print("Falling back to full rebuild.")
        _full_rebuild(resume_date=resume_date)
        _cleanup()
        return

    # 3. Apply incremental deltas
    apply_incremental_update(added, removed, changed_products)
    _cleanup()


def _cleanup():
    if os.path.exists(CHANGES_FILE):
        os.remove(CHANGES_FILE)


if __name__ == "__main__":
    main()
