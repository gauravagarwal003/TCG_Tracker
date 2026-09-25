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


if __name__ == "__main__":
    unittest.main()

