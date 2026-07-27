
from frappe.model.document import Document
from frappe.utils import now_datetime
class HotelGuestConsent(Document):
    def before_insert(self):
        if not self.captured_at: self.captured_at = now_datetime()
    def validate(self):
        if self.status == "Revoked" and not self.revoked_at: self.revoked_at = now_datetime()
