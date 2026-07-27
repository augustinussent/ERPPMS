from __future__ import annotations

import frappe
from frappe.model.document import Document
from hotel_pms.media import validate_photo_fields
from hotel_pms.operations_rules import calculate_inspection_result


class HotelRoomInspection(Document):
    def validate(self):
        validate_photo_fields(self, {"inspection_photo"})
        calculated = calculate_inspection_result(
            [
                {
                    "result": row.result,
                    "weight": row.weight,
                    "is_critical": row.is_critical,
                }
                for row in self.items
            ],
            self.pass_score or 90,
        )
        self.score = calculated.score
        if self.result == "Pass" and not calculated.passed:
            frappe.throw(
                f"Inspection cannot pass: score {calculated.score}, critical failures {calculated.critical_failures}, "
                f"completed {calculated.completed_items}/{calculated.total_applicable_items}."
            )
