from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class HotelCleaningChecklistTemplate(Document):
    def validate(self):
        if self.enabled:
            filters = {"property": self.property, "task_type": self.task_type, "enabled": 1, "name": ("!=", self.name or "")}
            if self.room_type:
                filters["room_type"] = self.room_type
                duplicate = frappe.db.exists("Hotel Cleaning Checklist Template", filters)
            else:
                duplicate = frappe.db.sql(
                    "select name from `tabHotel Cleaning Checklist Template` where property=%s and task_type=%s and enabled=1 and (room_type is null or room_type='') and name!=%s limit 1",
                    (self.property, self.task_type, self.name or ""),
                )
            if duplicate:
                frappe.throw(_("Only one enabled checklist template is allowed for the same property, room type, and task type."))
        if not self.items:
            frappe.throw(_("Add at least one checklist item."))
        seen = set()
        for row in self.items:
            key = (row.area or "", row.item_label or "")
            if key in seen:
                frappe.throw(_("Duplicate checklist item: {0} / {1}").format(*key))
            seen.add(key)
            row.weight = row.weight or 1
        for idx, row in enumerate(sorted(self.items, key=lambda d: (d.sequence or 0, d.area or "", d.item_label or "")), 1):
            row.idx = idx
