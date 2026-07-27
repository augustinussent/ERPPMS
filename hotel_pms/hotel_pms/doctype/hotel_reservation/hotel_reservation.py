from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


BLOCKING_STATUSES = ("Tentative", "Confirmed", "Checked In")


class HotelReservation(Document):
    def validate(self):
        self._validate_dates()
        self._set_defaults()
        self._validate_room_rows()
        self._validate_room_availability()

    def before_submit(self):
        if self.status == "Tentative":
            self.status = "Confirmed"

    def on_submit(self):
        if frappe.db.get_single_value("Hotel PMS Settings", "auto_create_folio"):
            self._ensure_folio()

    def on_cancel(self):
        was_checked_in = self.status == "Checked In"
        self.db_set("status", "Cancelled")
        if was_checked_in:
            self._release_rooms(dirty=True)

    def check_in(self):
        if self.docstatus != 1:
            frappe.throw(_("Submit the reservation before check-in."))
        if self.status not in ("Confirmed", "Tentative"):
            frappe.throw(_("Reservation status {0} cannot be checked in.").format(self.status))
        today = getdate()
        if today < getdate(self.arrival_date):
            frappe.throw(_("Arrival date has not been reached."))
        if today >= getdate(self.departure_date):
            frappe.throw(_("Reservation has already reached its departure date."))
        self._validate_room_availability(exclude_self=True)
        self.db_set("status", "Checked In")
        for row in self.rooms:
            frappe.db.set_value("Hotel Room", row.room, {"operational_status": "Occupied", "housekeeping_status": "Clean"})
        self._ensure_folio()

    def check_out(self):
        if self.status != "Checked In":
            frappe.throw(_("Only checked-in reservations can be checked out."))
        self.db_set("status", "Checked Out")
        self._release_rooms(dirty=True)

    def _validate_dates(self):
        if getdate(self.departure_date) <= getdate(self.arrival_date):
            frappe.throw(_("Departure date must be after arrival date."))

    def _set_defaults(self):
        if not self.billing_customer:
            self.billing_customer = self.guest
        if not self.cost_center and self.property:
            self.cost_center = frappe.db.get_value("Hotel Property", self.property, "default_cost_center")

    def _validate_room_rows(self):
        if not self.rooms:
            frappe.throw(_("Add at least one room."))
        seen = set()
        for row in self.rooms:
            if row.room in seen:
                frappe.throw(_("Room {0} is listed more than once.").format(row.room))
            seen.add(row.room)
            room = frappe.db.get_value("Hotel Room", row.room, ["property", "room_type", "enabled", "operational_status"], as_dict=True)
            if not room or not room.enabled:
                frappe.throw(_("Room {0} is disabled or missing.").format(row.room))
            if room.property != self.property:
                frappe.throw(_("Room {0} belongs to another property.").format(row.room))
            if room.room_type != row.room_type:
                frappe.throw(_("Room type does not match room {0}.").format(row.room))
            if room.operational_status in ("Out of Order", "Out of Service"):
                frappe.throw(_("Room {0} is not operational.").format(row.room))

    def _validate_room_availability(self, exclude_self=False):
        if frappe.db.get_single_value("Hotel PMS Settings", "allow_overbooking"):
            return
        for row in self.rooms:
            params = {
                "room": row.room,
                "arrival": getdate(self.arrival_date),
                "departure": getdate(self.departure_date),
                "name": self.name or "",
            }
            conflicts = frappe.db.sql(
                """
                select distinct r.name
                from `tabHotel Reservation` r
                inner join `tabHotel Reservation Room` rr on rr.parent = r.name
                where rr.room = %(room)s
                  and r.docstatus < 2
                  and r.status in ('Tentative', 'Confirmed', 'Checked In')
                  and r.arrival_date < %(departure)s
                  and r.departure_date > %(arrival)s
                  and r.name != %(name)s
                limit 1
                """,
                params,
                as_dict=True,
            )
            if conflicts:
                frappe.throw(_("Room {0} conflicts with reservation {1}.").format(row.room, conflicts[0].name))

            # Room-type blocks protect group inventory even before exact room assignment.
            from hotel_pms.hotel_pms.doctype.hotel_group_booking.hotel_group_booking import get_available_room_type_capacity

            available_capacity = get_available_room_type_capacity(
                property_name=self.property,
                room_type=row.room_type,
                arrival_date=self.arrival_date,
                departure_date=self.departure_date,
                exclude_group_booking=self.group_booking,
                exclude_reservation=self.name,
            )
            if available_capacity <= 0:
                frappe.throw(
                    _("No unheld room-type capacity remains for {0} during these dates.").format(row.room_type)
                )

    def _ensure_folio(self):
        from hotel_pms.api import _get_or_create_folio
        folio = _get_or_create_folio(self)
        if self.folio != folio.name:
            self.db_set("folio", folio.name)

    def _release_rooms(self, dirty=False):
        for row in self.rooms:
            frappe.db.set_value(
                "Hotel Room",
                row.room,
                {
                    "operational_status": "Available",
                    "housekeeping_status": "Dirty" if dirty else "Clean",
                },
            )
