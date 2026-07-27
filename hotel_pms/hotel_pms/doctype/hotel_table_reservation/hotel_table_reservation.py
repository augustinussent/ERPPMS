from frappe.model.document import Document


class HotelTableReservation(Document):
    def validate(self):
        import frappe
        from frappe.utils import get_datetime, add_to_date
        if self.duration_minutes <= 0 or self.pax <= 0:
            frappe.throw("Duration and pax must be greater than zero.")
        if not frappe.db.sql("select name from `tabHotel Restaurant Table` where name=%s for update", self.table):
            frappe.throw("Restaurant table was not found.")
        if frappe.db.get_value("Hotel Restaurant Table", self.table, "outlet") != self.outlet:
            frappe.throw("Table must belong to the selected outlet.")
        start = get_datetime(self.reservation_datetime)
        end = add_to_date(start, minutes=self.duration_minutes, as_datetime=True)
        rows = frappe.get_all("Hotel Table Reservation", filters={"table": self.table, "status": ["in", ["Tentative","Confirmed","Seated"]], "name": ["!=", self.name]}, fields=["name","reservation_datetime","duration_minutes"])
        for row in rows:
            other_start = get_datetime(row.reservation_datetime)
            other_end = add_to_date(other_start, minutes=row.duration_minutes, as_datetime=True)
            if start < other_end and end > other_start:
                frappe.throw(f"Table conflicts with reservation {row.name}.")
