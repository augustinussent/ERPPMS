import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class HotelRestaurantAlert(Document):
    def before_insert(self):
        self.first_seen_at = self.first_seen_at or now_datetime()
        self.last_seen_at = self.last_seen_at or now_datetime()

    def validate(self):
        if self.status == "Acknowledged" and not self.acknowledged_at:
            self.acknowledged_at = now_datetime()
            self.acknowledged_by = frappe.session.user
        if self.status in ("Resolved", "False Positive") and not self.resolved_at:
            self.resolved_at = now_datetime()
