
from frappe.model.document import Document
from frappe.utils import now_datetime


class HotelVoucherRedemption(Document):
    def before_insert(self):
        if not self.redeemed_at:
            self.redeemed_at = now_datetime()
