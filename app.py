"""
app.py - Flask app for local development and testing.

Provides:
  - Dashboard with portfolio graph
  - Transaction list with add/edit/delete
  - API endpoints for the GitHub Pages frontend
"""

import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime

from engine import (
    load_transactions, load_daily_summary, load_mappings,
    get_current_holdings, today_pst, save_daily_summary,
    derive_daily_summary, DAILY_SUMMARY_FILE
)
from transaction_manager import add_transaction, edit_transaction, delete_transaction

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    return {"active_page": "", "is_static": False}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Dashboard page."""
    holdings = get_current_holdings()
    summary = load_daily_summary()
    
    total_value = sum(h["total_value"] for h in holdings)
    total_cost_basis = 0
    
    # Get latest summary entry
    if summary:
        latest_date = max(summary.keys())
        total_cost_basis = summary[latest_date]["cost_basis"]
    
    return render_template(
        "index.html",
        holdings=holdings,
        total_value=total_value,
        total_cost_basis=total_cost_basis,
        summary=summary,
        active_page="index"
    )


@app.route("/transactions")
def transactions_page():
    """Transactions page."""
    txns = load_transactions()
    mappings = load_mappings()
    
    return render_template(
        "transactions.html",
        transactions=txns,
        mappings=mappings,
        active_page="transactions"
    )


@app.route("/transactions/add", methods=["GET", "POST"])
def add_transaction_page():
    if request.method == "POST":
        try:
            txn_type = request.form.get("transaction_type", "BUY").upper()
            
            txn_data = {
                "date_purchased": request.form.get("date_purchased", ""),
                "date_received": request.form.get("date_received", ""),
                "type": txn_type,
                "method": request.form.get("method", ""),
                "place": request.form.get("place", ""),
                "notes": request.form.get("notes", ""),
            }
            
            if txn_type == "TRADE":
                txn_data["items_out"] = json.loads(request.form.get("items_out", "[]"))
                txn_data["items_in"] = json.loads(request.form.get("items_in", "[]"))
                txn_data["cost_basis_out"] = float(request.form.get("cost_basis_out", 0))
                txn_data["cost_basis_in"] = float(request.form.get("cost_basis_in", 0))
            else:
                items = json.loads(request.form.get("items", "[]"))
                txn_data["items"] = items
                txn_data["amount"] = float(request.form.get("amount", 0))
            
            success, message, txn = add_transaction(txn_data)
            
            if success:
                flash(message, "success")
                return redirect(url_for("transactions_page"))
            else:
                flash(message, "error")
        
        except Exception as e:
            flash(f"Error: {e}", "error")
    
    mappings = load_mappings()
    return render_template(
        "transaction_form.html",
        transaction=None,
        mappings=mappings,
        is_edit=False
    )


@app.route("/transactions/edit/<txn_id>", methods=["GET", "POST"])
def edit_transaction_page(txn_id):
    txns = load_transactions()
    old_txn = next((t for t in txns if t["id"] == txn_id), None)
    
    if not old_txn:
        flash("Transaction not found", "error")
        return redirect(url_for("transactions_page"))
    
    if request.method == "POST":
        try:
            txn_type = request.form.get("transaction_type", "BUY").upper()
            
            new_data = {
                "date_purchased": request.form.get("date_purchased", ""),
                "date_received": request.form.get("date_received", ""),
                "type": txn_type,
                "method": request.form.get("method", ""),
                "place": request.form.get("place", ""),
                "notes": request.form.get("notes", ""),
            }
            
            if txn_type == "TRADE":
                new_data["items_out"] = json.loads(request.form.get("items_out", "[]"))
                new_data["items_in"] = json.loads(request.form.get("items_in", "[]"))
                new_data["cost_basis_out"] = float(request.form.get("cost_basis_out", 0))
                new_data["cost_basis_in"] = float(request.form.get("cost_basis_in", 0))
            else:
                items = json.loads(request.form.get("items", "[]"))
                new_data["items"] = items
                new_data["amount"] = float(request.form.get("amount", 0))
            
            success, message, txn = edit_transaction(txn_id, new_data)
            
            if success:
                flash(message, "success")
                return redirect(url_for("transactions_page"))
            else:
                flash(message, "error")
        
        except Exception as e:
            flash(f"Error: {e}", "error")
    
    mappings = load_mappings()
    return render_template(
        "transaction_form.html",
        transaction=old_txn,
        mappings=mappings,
        is_edit=True
    )


@app.route("/transactions/delete/<txn_id>", methods=["POST"])
def delete_transaction_page(txn_id):
    success, message = delete_transaction(txn_id)
    flash(message, "success" if success else "error")
    return redirect(url_for("transactions_page"))


# ---------------------------------------------------------------------------
# API endpoints (used by GitHub Pages frontend)
# ---------------------------------------------------------------------------
@app.route("/api/transactions")
def api_transactions():
    return jsonify(load_transactions())


@app.route("/api/transactions", methods=["POST"])
def api_add_transaction():
    data = request.get_json()
    success, message, txn = add_transaction(data)
    return jsonify({"success": success, "message": message, "transaction": txn})


@app.route("/api/transactions/<txn_id>", methods=["PUT"])
def api_edit_transaction(txn_id):
    data = request.get_json()
    success, message, txn = edit_transaction(txn_id, data)
    return jsonify({"success": success, "message": message, "transaction": txn})


@app.route("/api/transactions/<txn_id>", methods=["DELETE"])
def api_delete_transaction(txn_id):
    success, message = delete_transaction(txn_id)
    return jsonify({"success": success, "message": message})


@app.route("/api/summary")
def api_summary():
    return jsonify(load_daily_summary())


@app.route("/api/holdings")
def api_holdings():
    return jsonify(get_current_holdings())


@app.route("/api/mappings")
def api_mappings():
    return jsonify(load_mappings())


@app.route("/api/search_products")
def search_products():
    query = request.args.get("q", "").lower()
    mappings = load_mappings()
    results = [
        {
            "name": m["name"],
            "product_id": m["product_id"],
            "group_id": m["group_id"],
            "categoryId": m.get("categoryId", 3),
            "imageUrl": m.get("imageUrl", ""),
        }
        for m in mappings
        if query in m["name"].lower()
    ]
    return jsonify(results[:20])


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """Manually trigger re-derive of daily summary."""
    summary = derive_daily_summary()
    save_daily_summary(summary)
    return jsonify({"success": True, "message": "Summary re-derived.", "days": len(summary)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="127.0.0.1", port=port)
