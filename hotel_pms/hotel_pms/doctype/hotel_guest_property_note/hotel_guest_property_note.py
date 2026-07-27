import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
class HotelGuestPropertyNote(Document):
    def validate(self):
        self.unique_key=f"{self.guest_profile}::{self.property}"
        self.last_reviewed_by=frappe.session.user
        self.last_reviewed_at=now_datetime()
