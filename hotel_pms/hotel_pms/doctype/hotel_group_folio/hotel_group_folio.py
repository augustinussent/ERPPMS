from __future__ import annotations

from frappe.model.document import Document
from frappe.utils import flt


class HotelGroupFolio(Document):
    def validate(self):
        total = 0
        for row in self.charges:
            row.amount = flt(row.qty) * flt(row.rate)
            if not row.is_void:
                total += flt(row.amount)
        self.total_charges = total
