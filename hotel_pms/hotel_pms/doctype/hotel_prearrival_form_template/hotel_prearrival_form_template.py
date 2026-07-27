from __future__ import annotations

import re
import frappe
from frappe import _
from frappe.model.document import Document


class HotelPrearrivalFormTemplate(Document):
    def validate(self):
        if not self.questions:
            frappe.throw(_("Add at least one pre-arrival question."))
        seen = set()
        for row in self.questions:
            key = (row.field_key or "").strip().lower()
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,49}", key):
                frappe.throw(_("Question key {0} must use lowercase letters, numbers and underscores.").format(row.field_key))
            if key in seen:
                frappe.throw(_("Question key {0} is duplicated.").format(key))
            seen.add(key)
            row.field_key = key
