
from __future__ import annotations
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

MAP={"Warning":"Warning","Review":"Review","Block Online":"Blocked Online","Block All":"Blocked All"}
class HotelGuestBlacklist(Document):
    def validate(self):
        if self.valid_until and self.valid_from and getdate(self.valid_until) < getdate(self.valid_from):
            frappe.throw(_("Valid Until cannot be before Valid From."))
        old=self.get_doc_before_save() if not self.is_new() else None
        if self.status == "Active" and (not old or old.status != "Active"):
            frappe.only_for(["System Manager","Hotel Manager"])
            self.approved_by=frappe.session.user; self.approved_at=now_datetime()
        if self.status == "Revoked" and (not old or old.status != "Revoked"):
            frappe.only_for(["System Manager","Hotel Manager"])
            self.revoked_by=frappe.session.user; self.revoked_at=now_datetime()
    def on_update(self):
        if self.guest_profile:
            if self.status == "Active":
                frappe.db.set_value("Hotel Guest Profile",self.guest_profile,{"blacklist_status":MAP.get(self.restriction_level,"Review"),"blacklist_record":self.name,"status":"Restricted" if self.restriction_level in ("Block Online","Block All") else "Active"},update_modified=False)
            elif frappe.db.get_value("Hotel Guest Profile",self.guest_profile,"blacklist_record")==self.name:
                frappe.db.set_value("Hotel Guest Profile",self.guest_profile,{"blacklist_status":"Clear","blacklist_record":None,"status":"Active"},update_modified=False)
