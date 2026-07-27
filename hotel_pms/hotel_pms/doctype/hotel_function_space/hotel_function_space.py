from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class HotelFunctionSpace(Document):
    def validate(self):
        seen = set()
        for row in self.capacities:
            if row.setup_style in seen:
                frappe.throw(_("Setup style {0} is listed more than once.").format(row.setup_style))
            seen.add(row.setup_style)
            if cint(row.capacity) <= 0:
                frappe.throw(_("Capacity must be greater than zero."))
