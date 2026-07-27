from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class HotelPackageTemplate(Document):
    def validate(self):
        if self.valid_from and self.valid_to and getdate(self.valid_to) < getdate(self.valid_from):
            frappe.throw(_("Valid To cannot be before Valid From."))
        if not self.components:
            frappe.throw(_("Add at least one package component."))
        if not self.rates:
            frappe.throw(_("Add at least one package rate."))
        total_allocation = sum(flt(row.allocation_percent) for row in self.components if row.included)
        if total_allocation and abs(total_allocation - 100) > 0.01:
            frappe.throw(_("Included component revenue allocation must total 100%; current total is {0}%.").format(total_allocation))
        seen_rates = set()
        for row in self.rates:
            key = (row.occupancy_type, row.pricing_basis, row.minimum_pax)
            if key in seen_rates:
                frappe.throw(_("Duplicate package rate for {0} / {1}.").format(row.occupancy_type, row.pricing_basis))
            seen_rates.add(key)
