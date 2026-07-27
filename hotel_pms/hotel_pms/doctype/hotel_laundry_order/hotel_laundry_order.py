from frappe.model.document import Document


class HotelLaundryOrder(Document):
    def before_insert(self):
        from frappe.utils import now_datetime
        self.requested_at = self.requested_at or now_datetime()

    def validate(self):
        import frappe
        from frappe.utils import flt, add_to_date, get_datetime
        if self.reservation:
            reservation = frappe.get_doc("Hotel Reservation", self.reservation)
            if reservation.status != "Checked In" and self.order_type == "Guest":
                frappe.throw("Guest laundry requires a checked-in reservation.")
            self.property = reservation.property
            self.customer = self.customer or reservation.guest
            self.folio = self.folio or frappe.db.get_value("Hotel Folio", {"reservation": reservation.name}, "name")
            if not self.room and reservation.rooms:
                self.room = reservation.rooms[0].room
        total = 0
        max_hours = 24
        for row in self.items:
            if row.laundry_rate:
                rate_doc = frappe.get_doc("Hotel Laundry Rate", row.laundry_rate)
                if rate_doc.property != self.property or not rate_doc.active:
                    frappe.throw("Laundry rate is not active for this property.")
                row.item_code = rate_doc.item_code
                row.description = rate_doc.service_name
                row.rate = rate_doc.rate
            if row.qty_sent < 0 or row.qty_returned < 0 or row.qty_returned > row.qty_sent:
                frappe.throw("Laundry quantities are invalid.")
            row.amount = flt(row.qty_sent) * flt(row.rate)
            total += row.amount
            if row.laundry_rate:
                max_hours = max(max_hours, int(frappe.db.get_value("Hotel Laundry Rate", row.laundry_rate, "turnaround_hours") or 24))
        self.total_amount = total if self.order_type == "Guest" else 0
        if not self.promised_ready_at and self.requested_at:
            self.promised_ready_at = add_to_date(get_datetime(self.requested_at), hours=max_hours, as_datetime=True)
