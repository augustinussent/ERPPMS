from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class HotelRoom(Document):
    def after_insert(self):
        self._log_manual_status_change(None)

    def on_update(self):
        old = self.get_doc_before_save()
        if old and (
            old.operational_status != self.operational_status
            or old.housekeeping_status != self.housekeeping_status
        ):
            self._log_manual_status_change(old)

    def _log_manual_status_change(self, old):
        if not frappe.db.exists("DocType", "Hotel Room Status Log"):
            return
        frappe.get_doc(
            {
                "doctype": "Hotel Room Status Log",
                "property": self.property,
                "room": self.name,
                "event_at": now_datetime(),
                "event_type": "Manual Room Status Change" if old else "Room Created",
                "old_operational_status": old.operational_status if old else None,
                "new_operational_status": self.operational_status,
                "old_housekeeping_status": old.housekeeping_status if old else None,
                "new_housekeeping_status": self.housekeeping_status,
                "source_doctype": self.doctype,
                "source_name": self.name,
                "changed_by": frappe.session.user,
                "notes": "Room status changed through the Hotel Room form.",
            }
        ).insert(ignore_permissions=True)
