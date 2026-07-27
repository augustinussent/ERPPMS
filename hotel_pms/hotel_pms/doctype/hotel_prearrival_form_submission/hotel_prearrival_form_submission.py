from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class HotelPrearrivalFormSubmission(Document):
    def validate(self):
        reservation_property = frappe.db.get_value("Hotel Reservation", self.reservation, "property")
        template_property = frappe.db.get_value("Hotel Prearrival Form Template", self.template, "property")
        if reservation_property != self.property or template_property != self.property:
            frappe.throw(_("Reservation, template and submission must belong to the same property."))
        old = self.get_doc_before_save() if not self.is_new() else None
        if old and old.status == "Submitted":
            protected = ("reservation", "template", "answers_json", "answers_hash", "submitted_at")
            if any(old.get(field) != self.get(field) for field in protected):
                frappe.throw(_("Submitted pre-arrival answers are immutable."))
