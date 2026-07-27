from frappe.model.document import Document


class HotelKitchenTicket(Document):
    def validate(self):
        import frappe
        allowed = {"New", "Accepted", "Cooking", "Partially Ready", "Ready", "Served", "Recalled", "Cancelled"}
        if self.status not in allowed:
            frappe.throw("Invalid kitchen-ticket status.")
        if self.stock_entry and self.stock_sync_key:
            other = frappe.db.exists("Hotel Kitchen Ticket", {"stock_sync_key": self.stock_sync_key, "name": ["!=", self.name]})
            if other:
                frappe.throw("The stock sync key is already assigned to another KOT.")
