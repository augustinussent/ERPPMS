import frappe
from frappe import _
from frappe.model.document import Document

class HotelUserPropertyAccess(Document):
    def validate(self):
        self.unique_key = f"{self.user}::{self.property}"
        if self.is_default:
            frappe.db.sql("""update `tabHotel User Property Access` set is_default=0
                where user=%s and name<>%s""", (self.user, self.name or ""))
        if self.user == "Administrator":
            self.can_view_consolidated = 1
