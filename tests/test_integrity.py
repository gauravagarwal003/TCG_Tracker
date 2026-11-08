import unittest
from datetime import timedelta
from engine import (
    load_transactions,
    validate_inventory,
    validate_price_coverage,
    today_pst,
)


class TestDataIntegrity(unittest.TestCase):
    def setUp(self):
        self.transactions = load_transactions()
        self.today = today_pst()
        self.yesterday = (self.today - timedelta(days=1)).strftime("%Y-%m-%d")

    def test_inventory_validation_current_data(self):
        """Current transactions should have no negative inventory."""
        is_valid, msg = validate_inventory(self.transactions)
        self.assertTrue(is_valid, f"Inventory validation failed: {msg}")
        self.assertEqual(msg, "")

    def test_inventory_validation_catches_negative(self):
        """Synthetic transaction selling 999 items should fail inventory validation."""
        bad_sale = {
            "id": "synthetic-bad-sale",
            "date_received": self.yesterday,
            "type": "SELL",
            "items": [
                {
                    "categoryId": "3",
                    "group_id": "23651",
                    "product_id": "565630",
                    "quantity": 999999,
                    "price_per_item": 10.0,
                }
            ],
        }
        is_valid, msg = validate_inventory(self.transactions, new_txn=bad_sale)
        self.assertFalse(is_valid)
        self.assertIn("goes to", msg)

    def test_price_coverage_through_yesterday(self):
        """Pre-flight check: All owned items and transactions up through yesterday must have complete prices."""
        is_valid, missing_owned, missing_tx = validate_price_coverage(
            self.transactions, as_of_date=self.yesterday
        )
        self.assertTrue(
            is_valid,
            f"Expected 100% price coverage through yesterday ({self.yesterday}), "
            f"got {len(missing_owned)} missing owned dates and {len(missing_tx)} missing tx dates.",
        )
        self.assertEqual(missing_owned, [])
        self.assertEqual(missing_tx, [])

    def test_price_coverage_bounds(self):
        """Check that future transactions are ignored when as_of_date is in the past."""
        synthetic_future_tx = {
            "id": "synthetic-future-txn",
            "date_received": (self.today + timedelta(days=30)).strftime("%Y-%m-%d"),
            "type": "BUY",
            "items": [
                {
                    "categoryId": "3",
                    "group_id": "23651",
                    "product_id": "565630",
                    "quantity": 1,
                    "price_per_item": 1.0,
                }
            ],
        }
        txns = list(self.transactions) + [synthetic_future_tx]
        # Should not flag future transaction when checking as_of_date = yesterday
        is_valid, missing_owned, missing_tx = validate_price_coverage(
            txns, as_of_date=self.yesterday
        )
        self.assertTrue(is_valid)

    def test_price_coverage_detects_missing_transaction_price(self):
        """A past transaction with an unpriced item must be detected."""
        synthetic_past_tx = {
            "id": "synthetic-unpriced-past-txn",
            "date_received": "2020-01-01",
            "type": "BUY",
            "items": [
                {
                    "categoryId": "3",
                    "group_id": "23651",
                    "product_id": "565630",
                    "quantity": 1,
                    "price_per_item": 1.0,
                }
            ],
        }
        txns = list(self.transactions) + [synthetic_past_tx]
        is_valid, missing_owned, missing_tx = validate_price_coverage(
            txns, as_of_date=self.yesterday
        )
        self.assertFalse(is_valid)
        self.assertTrue(any(item[0] == "synthetic-unpriced-past-txn" for item in missing_tx))

    def test_deduplicate_phrase(self):
        from transaction_manager import deduplicate_phrase
        self.assertEqual(
            deduplicate_phrase("Ascended Heroes Ascended Heroes Booster Bundle"),
            "Ascended Heroes Booster Bundle"
        )
        self.assertEqual(
            deduplicate_phrase("Phantasmal Flames Phantasmal Flames Booster Box"),
            "Phantasmal Flames Booster Box"
        )
        self.assertEqual(
            deduplicate_phrase("Surging Sparks Surging Sparks Elite Trainer Box"),
            "Surging Sparks Elite Trainer Box"
        )
        self.assertEqual(
            deduplicate_phrase("151 151 Booster Bundle"),
            "151 Booster Bundle"
        )
        self.assertEqual(
            deduplicate_phrase("Ascended Heroes Booster Bundle"),
            "Ascended Heroes Booster Bundle"
        )

    def test_pid_654160_price_coverage_on_2026_01_05(self):
        """PID 654160 (Phantasmal Flames Booster Bundle) on 2026-01-05 must succeed price coverage check."""
        pid_654160_txns = [
            t for t in self.transactions
            if any(str(it.get("product_id")) == "654160" for it in t.get("items", []))
        ]
        self.assertTrue(len(pid_654160_txns) > 0, "No transactions found with PID 654160")
        is_valid, missing_owned, missing_tx = validate_price_coverage(
            pid_654160_txns, as_of_date="2026-01-05"
        )
        self.assertTrue(
            is_valid,
            f"Price coverage check failed for PID 654160 on 2026-01-05. missing_owned: {missing_owned}, missing_tx: {missing_tx}"
        )

    def test_item_normalization_canonicalizes_group_id(self):
        """Items with missing or mismatched group_id must be canonicalized from mappings."""
        from engine import normalize_transactions_for_pricing
        txns_missing_gid = [{
            "id": "synthetic-missing-gid",
            "date_received": "2026-01-05",
            "type": "BUY",
            "items": [{"product_id": "654160", "categoryId": 3, "quantity": 1}],
        }]
        norm = normalize_transactions_for_pricing(txns_missing_gid)
        self.assertEqual(norm[0]["items"][0]["group_id"], "24448")
        is_valid, missing_owned, missing_tx = validate_price_coverage(norm, as_of_date="2026-01-05")
        self.assertTrue(is_valid)

        txns_mismatched_gid = [{
            "id": "synthetic-mismatched-gid",
            "date_received": "2026-01-05",
            "type": "BUY",
            "items": [{"product_id": "654160", "group_id": "2374", "categoryId": 3, "quantity": 1}],
        }]
        norm2 = normalize_transactions_for_pricing(txns_mismatched_gid)
        self.assertEqual(norm2[0]["items"][0]["group_id"], "24448")
        is_valid2, missing_owned2, missing_tx2 = validate_price_coverage(norm2, as_of_date="2026-01-05")
        self.assertTrue(is_valid2)


if __name__ == "__main__":
    unittest.main()

