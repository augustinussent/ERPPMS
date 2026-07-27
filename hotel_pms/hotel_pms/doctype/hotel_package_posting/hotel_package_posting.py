from __future__ import annotations

from frappe.model.document import Document
from frappe.utils import flt


class HotelPackagePosting(Document):
    def validate(self):
        self.amount = flt(self.qty) * flt(self.rate)
