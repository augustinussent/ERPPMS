from datetime import date
from decimal import Decimal
import unittest

from hotel_pms.front_desk_rules import calculate_fee, quote_cancellation, room_nights, stay_total


class FrontDeskRuleTests(unittest.TestCase):
    def test_room_nights(self):
        self.assertEqual(room_nights(date(2026, 8, 1), date(2026, 8, 4)), 3)

    def test_multi_room_stay_total(self):
        self.assertEqual(stay_total(date(2026, 8, 1), date(2026, 8, 3), [500000, 750000]), Decimal("2500000.00"))

    def test_percentage_fee(self):
        self.assertEqual(calculate_fee(1000000, "Percentage", 25), Decimal("250000.00"))

    def test_free_cancellation(self):
        quote = quote_cancellation(
            arrival=date(2026, 8, 10), departure=date(2026, 8, 12), nightly_rates=[500000],
            reference_date=date(2026, 8, 5), free_cancellation_days=3, fee_type="First Night", deposit_received=300000,
        )
        self.assertEqual(quote.fee_amount, Decimal("0.00"))
        self.assertEqual(quote.refundable_amount, Decimal("300000.00"))

    def test_late_first_night_fee(self):
        quote = quote_cancellation(
            arrival=date(2026, 8, 10), departure=date(2026, 8, 12), nightly_rates=[500000, 600000],
            reference_date=date(2026, 8, 9), free_cancellation_days=3, fee_type="First Night", deposit_received=1500000,
        )
        self.assertEqual(quote.fee_amount, Decimal("1100000.00"))
        self.assertEqual(quote.refundable_amount, Decimal("400000.00"))


if __name__ == "__main__":
    unittest.main()
