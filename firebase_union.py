"""
firebase_union.py - Firestore helpers for union product price fetching.

This module is intentionally read-only for the daily fetch path:
it builds a deduplicated union of product keys across all users.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Iterable, Optional, Set, Tuple

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except Exception:  # pragma: no cover - handled at runtime when feature is enabled
    firebase_admin = None
    credentials = None
    firestore = None


ProductKey = Tuple[str, str, str]


def _normalize_key_fields(data: Dict) -> Optional[ProductKey]:
    """Extract (categoryId, group_id, product_id) from a document-like dict."""
    category_id = data.get("categoryId")
    group_id = data.get("group_id")
    product_id = data.get("product_id")
    quantity = data.get("quantity")
    count = data.get("count")

    # For holdings docs, require quantity > 0 if present.
    if quantity is not None:
        try:
            if float(quantity) <= 0:
                return None
        except (TypeError, ValueError):
            return None

    # For active_products docs, require count > 0 if present.
    if count is not None:
        try:
            if float(count) <= 0:
                return None
        except (TypeError, ValueError):
            return None

    if category_id is None or group_id is None or product_id is None:
        return None

    return (str(category_id), str(group_id), str(product_id))


def init_firestore_from_env():
    """
    Initialize Firebase Admin using one of these env vars:
      - FIREBASE_SERVICE_ACCOUNT_JSON (raw service account JSON string)
      - FIREBASE_SERVICE_ACCOUNT_FILE (path to service account JSON file)
    """
    if firebase_admin is None or credentials is None or firestore is None:
        raise RuntimeError(
            "firebase-admin is not installed. Add it to requirements and install dependencies."
        )

    if firebase_admin._apps:
        return firestore.client()

    svc_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    svc_file = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", "").strip()

    if svc_json:
        try:
            info = json.loads(svc_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
        cred = credentials.Certificate(info)
    elif svc_file:
        cred = credentials.Certificate(svc_file)
    else:
        raise RuntimeError(
            "Missing Firebase credentials. Set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_FILE."
        )

    firebase_admin.initialize_app(cred)
    return firestore.client()


def _read_active_products_index(db) -> Set[ProductKey]:
    """
    Preferred source: active_products index docs.

    Expected doc shape:
      active_products/{cat}_{gid}_{pid}
        - categoryId
        - group_id
        - product_id
        - count
    """
    keys: Set[ProductKey] = set()
    docs = db.collection("active_products").stream()
    for doc in docs:
        data = doc.to_dict() or {}
        key = _normalize_key_fields(data)
        if key:
            keys.add(key)
    return keys


def _scan_user_holdings(db) -> Set[ProductKey]:
    """
    Fallback source: users/{uid}/holdings docs.

    Expected holding doc shape:
      - categoryId
      - group_id
      - product_id
      - quantity
    """
    keys: Set[ProductKey] = set()
    user_docs = db.collection("users").stream()

    for user_doc in user_docs:
        holdings = (
            db.collection("users")
            .document(user_doc.id)
            .collection("holdings")
            .stream()
        )
        for hdoc in holdings:
            data = hdoc.to_dict() or {}
            key = _normalize_key_fields(data)
            if key:
                keys.add(key)

    return keys


def get_union_product_keys(db=None) -> Set[ProductKey]:
    """
    Return deduplicated product keys across all users.

    Strategy:
      1. Try active_products index (fast, scalable)
      2. Fallback to scanning users/*/holdings
    """
    if db is None:
        db = init_firestore_from_env()

    keys = _read_active_products_index(db)
    if keys:
        return keys

    return _scan_user_holdings(db)
