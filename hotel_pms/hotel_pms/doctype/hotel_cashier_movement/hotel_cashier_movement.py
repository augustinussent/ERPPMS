
from frappe.model.document import Document
from frappe.utils import now_datetime


class HotelCashierMovement(Document):
    def before_insert(self):
        if not self.movement_at:
            self.movement_at = now_datetime()
