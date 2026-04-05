"""
Migrate local transactions.json into Firestore for a specific user.

Usage:
  python migrate_transactions_to_firestore.py --uid <FIREBASE_UID>

Environment:
  FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_FILE must be set.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Set, Tuple

from engine import load_transactions
from firebase_union import init_firestore_from_env


ProductKey = Tuple[str, str, str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_all_keys(txn: Dict) -> Set[ProductKey]:
    keys: Set[ProductKey] = set()

    def add_items(items: Iterable[Dict]) -> None:
        for item in items:
            cat = item.get("categoryId")
            gid = item.get("group_id")
            pid = item.get("product_id")
            if cat is None or gid is None or pid is None:
                continue
            keys.add((str(cat), str(gid), str(pid)))

    add_items(txn.get("items", []))
    add_items(txn.get("items_in", []))
    add_items(txn.get("items_out", []))
    return keys


def _compute_current_holdings(transactions: List[Dict]) -> Set[ProductKey]:
    """Compute current positive holdings from the local transaction timeline."""
    balances: Dict[ProductKey, float] = {}

    ordered = sorted(transactions, key=lambda t: str(t.get("date_received", "")))
    for txn in ordered:
        ttype = str(txn.get("type", "")).upper()

        if ttype == "BUY":
            for item in txn.get("items", []):
                key = _item_key(item)
                if not key:
                    continue
                balances[key] = balances.get(key, 0) + float(item.get("quantity", 0) or 0)

        elif ttype in ("SELL", "OPEN"):
            for item in txn.get("items", []):
                key = _item_key(item)
                if not key:
                    continue
                balances[key] = balances.get(key, 0) - float(item.get("quantity", 0) or 0)

        elif ttype == "TRADE":
            for item in txn.get("items_in", []):
                key = _item_key(item)
                if not key:
                    continue
                balances[key] = balances.get(key, 0) + float(item.get("quantity", 0) or 0)
            for item in txn.get("items_out", []):
                key = _item_key(item)
                if not key:
                    continue
                balances[key] = balances.get(key, 0) - float(item.get("quantity", 0) or 0)

    return {k for k, qty in balances.items() if qty > 0}


def _item_key(item: Dict) -> ProductKey | None:
    cat = item.get("categoryId")
    gid = item.get("group_id")
    pid = item.get("product_id")
    if cat is None or gid is None or pid is None:
        return None
    return (str(cat), str(gid), str(pid))


def _batched(iterable: List[Dict], size: int = 400):
    for i in range(0, len(iterable), size):
        yield iterable[i : i + size]


def migrate(uid: str, overwrite: bool) -> None:
    db = init_firestore_from_env()
    txns = load_transactions()

    if not txns:
        print("No local transactions found in transactions.json")
        return

    txns_ref = db.collection("users").document(uid).collection("transactions")
    existing_docs = list(txns_ref.stream())
    if existing_docs and not overwrite:
        print(
            f"Refusing to migrate: users/{uid}/transactions already has {len(existing_docs)} docs. "
            "Re-run with --overwrite to replace existing docs."
        )
        return

    now = _now_iso()

    if existing_docs and overwrite:
        delete_batch = db.batch()
        for d in existing_docs:
            delete_batch.delete(d.reference)
        delete_batch.commit()
        print(f"Deleted {len(existing_docs)} existing transaction docs for user {uid}.")

    normalized: List[Dict] = []
    for txn in txns:
        tid = str(txn.get("id") or "").strip()
        if not tid:
            continue
        normalized.append(
            {
                **txn,
                "id": tid,
                "migrated_from": "local_transactions_json",
                "migrated_at": now,
                "updated_at": txn.get("updated_at") or now,
                "created_at": txn.get("created_at") or now,
            }
        )

    written = 0
    for chunk in _batched(normalized, size=400):
        batch = db.batch()
        for txn in chunk:
            ref = txns_ref.document(txn["id"])
            batch.set(ref, txn)
            written += 1
        batch.commit()

    # Rebuild active_products entries for this user based on current positive holdings.
    held_keys = _compute_current_holdings(normalized)
    touched = 0
    for cat, gid, pid in held_keys:
        doc_id = f"{cat}_{gid}_{pid}"
        ref = db.collection("active_products").document(doc_id)
        snap = ref.get()
        prev = snap.to_dict() if snap.exists else {}
        users = set(str(u) for u in (prev.get("users") or []))
        users.add(uid)
        count = max(int(prev.get("count") or 0), len(users))
        ref.set(
            {
                "categoryId": cat,
                "group_id": gid,
                "product_id": pid,
                "users": sorted(users),
                "count": count,
                "last_updated": now,
                "updated_via": "migrate_transactions_to_firestore.py",
            },
            merge=True,
        )
        touched += 1

    meta_ref = db.collection("users").document(uid).collection("meta").document("seeded")
    meta_ref.set(
        {
            "legacy_seeded": True,
            "seeded_at": now,
            "source": "local_transactions_json",
            "total_seeded": written,
            "active_products_touched": touched,
            "seeded_via": "migrate_transactions_to_firestore.py",
        },
        merge=True,
    )

    print(f"Migrated {written} transactions into users/{uid}/transactions")
    print(f"Updated {touched} active_products docs")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate local transactions.json to Firestore")
    parser.add_argument("--uid", required=True, help="Target Firebase Auth user UID")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete existing users/{uid}/transactions before writing.",
    )
    args = parser.parse_args()

    migrate(uid=args.uid, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
