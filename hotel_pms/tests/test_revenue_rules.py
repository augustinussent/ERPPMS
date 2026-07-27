from datetime import date
from decimal import Decimal
import unittest

from hotel_pms.revenue_rules import (
    apply_adjustment,
    apply_derived_rate,
    conserve_split,
    tax_breakdown,
    validate_stay_restrictions,
    voucher_discount,
)


class TestRevenueRules(unittest.TestCase):
    def test_adjustments(self):
        self.assertEqual(apply_adjustment(1000, "Percentage", 10), Decimal("1100.00"))
        self.assertEqual(apply_adjustment(1000, "Fixed Amount", 250), Decimal("1250.00"))
        self.assertEqual(apply_adjustment(1000, "Fixed Rate", 777), Decimal("777.00"))

    def test_derived_rate(self):
        self.assertEqual(apply_derived_rate(1000, "Percentage", -10, 100), Decimal("1000.00"))

    def test_voucher_conserved(self):
        self.assertEqual(voucher_discount(1000, "Percentage", 20, 150), Decimal("150.00"))
        self.assertEqual(voucher_discount(100, "Fixed Amount", 500), Decimal("100.00"))

    def test_exclusive_tax(self):
        row = tax_breakdown(100000, 10, 10, "Net Amount plus Service Charge", False, False, "No Rounding")
        self.assertEqual(row["net"], Decimal("100000.00"))
        self.assertEqual(row["service_charge"], Decimal("10000.00"))
        self.assertEqual(row["tax"], Decimal("11000.00"))
        self.assertEqual(row["gross"], Decimal("121000.00"))

    def test_inclusive_tax(self):
        row = tax_breakdown(121000, 10, 10, "Net Amount plus Service Charge", True, True, "No Rounding")
        self.assertEqual(row["net"], Decimal("100000.00"))
        self.assertEqual(row["gross"], Decimal("121000.00"))

    def test_restrictions(self):
        rules = [{"minimum_stay": 2, "maximum_stay": 5, "stop_sell": 0, "minimum_advance_days": 1}]
        errors = validate_stay_restrictions(
            arrival_date=date(2026, 8, 1), departure_date=date(2026, 8, 2), booking_date=date(2026, 7, 31),
            arrival_rules={}, departure_rules={}, daily_rules=rules,
        )
        self.assertTrue(any("Minimum stay" in x for x in errors))

    def test_split_conservation(self):
        self.assertTrue(conserve_split(100, 30, 70))
        self.assertFalse(conserve_split(100, 30, 69.99))


if __name__ == "__main__":
    unittest.main()
