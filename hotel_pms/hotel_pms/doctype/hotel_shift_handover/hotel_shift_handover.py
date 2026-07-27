from frappe.model.document import Document


class HotelShiftHandover(Document):
    def before_insert(self):
        import frappe
        from frappe.utils import nowdate
        self.outgoing_user = self.outgoing_user or frappe.session.user
        self.shift_date = self.shift_date or nowdate()
