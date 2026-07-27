from datetime import datetime, timedelta
import unittest

from hotel_pms.operations_rules import (
    calculate_inspection_result,
    calculate_sla_status,
    elapsed_minutes,
    housekeeping_priority_score,
    should_create_sop_candidate,
)


class OperationsRuleTests(unittest.TestCase):
    def test_waiting_guest_beats_normal_departure(self):
        urgent = housekeeping_priority_score(guest_waiting=True, minutes_to_next_arrival=30)
        normal = housekeeping_priority_score(guest_waiting=False, minutes_to_next_arrival=240)
        self.assertGreater(urgent, normal)

    def test_elapsed_excludes_pause(self):
        start = datetime(2026, 7, 20, 10, 0)
        end = datetime(2026, 7, 20, 10, 45)
        self.assertEqual(elapsed_minutes(start, end, 10), 35)

    def test_inspection_critical_failure_blocks_pass(self):
        result = calculate_inspection_result([
            {"result": "OK", "weight": 1, "is_critical": 0},
            {"result": "Not OK", "weight": 1, "is_critical": 1},
        ], pass_score=40)
        self.assertFalse(result.passed)
        self.assertEqual(result.critical_failures, 1)

    def test_inspection_pending_blocks_pass(self):
        result = calculate_inspection_result([
            {"result": "OK", "weight": 1},
            {"result": "Pending", "weight": 1},
        ], pass_score=40)
        self.assertFalse(result.passed)

    def test_sla_breach(self):
        now = datetime(2026, 7, 20, 12, 0)
        status = calculate_sla_status(
            now=now,
            response_due_at=now - timedelta(minutes=1),
            resolution_due_at=now + timedelta(hours=1),
            acknowledged_at=None,
            resolved_at=None,
        )
        self.assertEqual(status, "Response Breached")

    def test_sop_candidate_threshold(self):
        self.assertTrue(should_create_sop_candidate(repeat_count=3, threshold=3, has_learning=True))
        self.assertFalse(should_create_sop_candidate(repeat_count=2, threshold=3, has_learning=True))


if __name__ == "__main__":
    unittest.main()
