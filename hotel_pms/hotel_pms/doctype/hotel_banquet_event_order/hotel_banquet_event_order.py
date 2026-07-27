from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


class HotelBanquetEventOrder(Document):
    def validate(self):
        if not self.functions:
            frappe.throw(_("Add at least one event function."))
        for row in self.functions:
            if get_datetime(row.end_datetime) <= get_datetime(row.start_datetime):
                frappe.throw(_("Function end must be after start for {0}.").format(row.function_name))

    def before_submit(self):
        self.status = "Issued"

    def on_submit(self):
        older = frappe.get_all(
            "Hotel Banquet Event Order",
            filters={"group_booking": self.group_booking, "name": ("!=", self.name), "docstatus": 1},
            pluck="name",
        )
        for name in older:
            frappe.db.set_value("Hotel Banquet Event Order", name, "status", "Superseded")
        frappe.db.set_value("Hotel Group Booking", self.group_booking, "current_beo", self.name)

    def on_cancel(self):
        self.db_set("status", "Cancelled")
