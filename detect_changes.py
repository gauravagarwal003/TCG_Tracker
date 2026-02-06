"""
Detect transaction changes by diffing current transactions.csv against the
previous git commit.  Writes transaction_changes.json consumed by
incremental_update.py.

Also updates data.json (start_date → earliest transaction, latest_date → yesterday).
"""

import json
import math
import os
import io
import subprocess
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter, defaultdict


# ── Normalizers (must match the ones used when the tracker was built) ────────

def _normalize_id(v):
    try:
        return str(int(float(v)))
    except (ValueError, TypeError):
        return str(v).strip()


def _normalize_date(v):
    raw = str(v).strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except Exception:
            continue
    return None


def _normalize_price(v):
    raw = str(v).strip().replace("$", "").replace(",", "")
    if raw == "" or raw.lower() == "nan":
        return None
    try:
        return round(float(raw), 4)
    except Exception:
        return None


def _normalize_qty(v):
    raw = str(v).strip()
    if raw == "" or raw.lower() == "nan":
        return None
    try:
        return round(float(raw), 4)
    except Exception:
        return None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_key(row, columns):
    """Hashable fingerprint of a single transaction row."""
    col = {c: i for i, c in enumerate(columns)}
    if "Date Recieved" not in col:
        return None
    d = _normalize_date(row[col["Date Recieved"]])
    if d is None:
        return None
    t = str(row[col.get("Transaction Type", -1)]).strip().upper() if "Transaction Type" in col else ""
    g = _normalize_id(row[col["group_id"]]) if "group_id" in col else ""
    p = _normalize_id(row[col["product_id"]]) if "product_id" in col else ""
    q = _normalize_qty(row[col["Quantity"]]) if "Quantity" in col else None
    pr = _normalize_price(row[col["Price Per Unit"]]) if "Price Per Unit" in col else None
    return (d, t, g, p, q, pr)


def _make_serializable(d):
    """Convert numpy / NaN values so json.dump doesn't choke."""
    out = {}
    for k, v in d.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            out[k] = ""
        elif hasattr(v, "item"):          # numpy scalar
            out[k] = v.item()
        else:
            out[k] = v
    return out


# ── Main ─────────────────────────────────────────────────────────────────────

def detect_changes():
    """
    Compare current transactions.csv with the version from the previous commit.
    Write transaction_changes.json with added/removed rows + metadata.
    """
    print("=== Detecting Transaction Changes ===")

    # ── 1. Load current transactions & update data.json ─────────────────────
    df = pd.read_csv("transactions.csv")

    with open("data.json", "r") as f:
        config = json.load(f)

    dates = []
    for d in df["Date Recieved"].dropna():
        try:
            dates.append(datetime.strptime(str(d), "%m/%d/%Y").date())
        except Exception:
            pass

    if dates:
        config["start_date"] = min(dates).strftime("%Y-%m-%d")
    config["latest_date"] = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    with open("data.json", "w") as f:
        json.dump(config, f, indent=4)
    print(f"  Config updated: start={config['start_date']}, latest={config['latest_date']}")

    # ── 2. Load previous transactions from git ──────────────────────────────
    try:
        prev_csv = subprocess.check_output(
            ["git", "show", "HEAD^:transactions.csv"], text=True
        )
        prev_df = pd.read_csv(io.StringIO(prev_csv))
    except Exception:
        prev_df = pd.DataFrame(columns=df.columns)

    # ── 3. Build fingerprint keys for every row ─────────────────────────────
    cur_cols = list(df.columns)
    prev_cols = list(prev_df.columns)

    cur_str = df.fillna("").astype(str).values.tolist()
    prev_str = prev_df.fillna("").astype(str).values.tolist()

    cur_keys = [k for k in (_build_key(r, cur_cols) for r in cur_str) if k]
    prev_keys = [k for k in (_build_key(r, prev_cols) for r in prev_str) if k]

    # ── 4. Diff using multiset subtraction ──────────────────────────────────
    added_counter = Counter(cur_keys) - Counter(prev_keys)
    removed_counter = Counter(prev_keys) - Counter(cur_keys)

    if not added_counter and not removed_counter:
        print("  No meaningful changes detected.")
        return

    # ── 5. Map keys → full row dicts ────────────────────────────────────────
    cur_by_key = defaultdict(list)
    for i, row_str in enumerate(cur_str):
        k = _build_key(row_str, cur_cols)
        if k:
            cur_by_key[k].append(df.iloc[i].to_dict())

    prev_by_key = defaultdict(list)
    for i, row_str in enumerate(prev_str):
        k = _build_key(row_str, prev_cols)
        if k:
            prev_by_key[k].append(prev_df.iloc[i].to_dict())

    added_rows = []
    for key, count in added_counter.items():
        added_rows.extend(cur_by_key.get(key, [])[:count])

    removed_rows = []
    for key, count in removed_counter.items():
        removed_rows.extend(prev_by_key.get(key, [])[:count])

    # ── 6. Collect metadata ─────────────────────────────────────────────────
    all_changed = list(added_counter.elements()) + list(removed_counter.elements())

    changed_dates = [k[0] for k in all_changed if k and k[0]]
    resume_date = min(changed_dates).strftime("%Y-%m-%d") if changed_dates else None

    changed_products = set()
    for k in all_changed:
        if not k:
            continue
        g, p = str(k[2]).strip(), str(k[3]).strip()
        if g and p and g.lower() != "nan" and p.lower() != "nan":
            changed_products.add((g, p))

    # ── 7. Write output file ────────────────────────────────────────────────
    output = {
        "resume_date": resume_date,
        "changed_products": sorted(changed_products),
        "added": [_make_serializable(r) for r in added_rows],
        "removed": [_make_serializable(r) for r in removed_rows],
    }

    with open("transaction_changes.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"  {len(added_rows)} added, {len(removed_rows)} removed")
    print(f"  Resume date: {resume_date}")
    print(f"  Changed products: {sorted(changed_products)}")


if __name__ == "__main__":
    detect_changes()
