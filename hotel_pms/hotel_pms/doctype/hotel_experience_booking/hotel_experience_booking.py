from frappe.model.document import Document


class HotelExperienceBooking(Document):
    def validate(self):
        import frappe
        from frappe.utils import get_datetime, now_datetime, flt
        if not frappe.db.sql("select name from `tabHotel Guest Experience` where name=%s for update", self.experience):
            frappe.throw("Guest experience was not found.")
        experience = frappe.get_doc("Hotel Guest Experience", self.experience)
        self.property = experience.property
        if self.participants <= 0:
            frappe.throw("Participants must be greater than zero.")
        if get_datetime(self.scheduled_at) <= now_datetime() and self.status in ("Requested", "Confirmed"):
            frappe.throw("Experience schedule must be in the future.")
        booked = frappe.db.sql("""select coalesce(sum(participants),0) from `tabHotel Experience Booking` where experience=%s and scheduled_at=%s and status in ('Requested','Confirmed') and name!=%s""", (self.experience, self.scheduled_at, self.name or ''))[0][0]
        if flt(booked) + flt(self.participants) > flt(experience.capacity):
            frappe.throw("Experience capacity is not available for the selected session.")
        self.amount = flt(self.participants) * flt(experience.price)
        if self.reservation:
            reservation = frappe.get_doc("Hotel Reservation", self.reservation)
            self.customer = self.customer or reservation.guest
            self.folio = self.folio or frappe.db.get_value("Hotel Folio", {"reservation": reservation.name}, "name")
