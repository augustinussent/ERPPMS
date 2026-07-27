from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


BLOCKING_STATUSES = ("Tentative", "Confirmed", "Checked In")


class HotelReservation(Document):
    def validate(self):
        self._validate_dates()
        self._prevent_direct_policy_bypass()
        self._set_defaults()
        self._validate_room_rows()
        self._validate_room_availability()

    def before_submit(self):
        if self.status == "Tentative":
            self.status = "Confirmed"

    def before_cancel(self):
        frappe.throw(_("Reservation documents are not cancelled directly. Use the controlled cancellation action to preserve policy, fee, refund, and audit records."))

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
        if frappe.db.get_single_value("Hotel PMS Settings", "require_verified_registration_before_check_in"):
            if not self.registration or frappe.db.get_value("Hotel Guest Registration", self.registration, "status") != "Verified":
                frappe.throw(_("A verified Guest Registration Card is required before check-in."))
        for row in self.rooms:
            room_status = frappe.db.get_value(
                "Hotel Room", row.room, ["operational_status", "housekeeping_status"], as_dict=True
            )
            if room_status.operational_status != "Available":
                frappe.throw(_("Room {0} is not operationally available.").format(row.room))
            if room_status.housekeeping_status not in ("Clean", "Inspected"):
                frappe.throw(_("Room {0} is not ready for check-in; housekeeping status is {1}.").format(
                    row.room, room_status.housekeeping_status
                ))
        self.db_set({"status": "Checked In", "actual_check_in_at": frappe.utils.now_datetime()})
        for row in self.rooms:
            frappe.db.set_value("Hotel Room", row.room, {"operational_status": "Occupied"})
        self._ensure_folio()

    def check_out(self):
        if self.status != "Checked In":
            frappe.throw(_("Only checked-in reservations can be checked out."))
        if getdate() < getdate(self.departure_date):
            frappe.throw(_("This is an early departure. Amend the departure date first so inventory, audit history, and charges remain consistent."))
        self.db_set({"status": "Checked Out", "actual_check_out_at": frappe.utils.now_datetime()})
        self._release_rooms(dirty=True)

        from hotel_pms.tasks import ensure_housekeeping_task

        for row in self.rooms:
            ensure_housekeeping_task(
                property_name=self.property,
                room=row.room,
                task_date=getdate(),
                task_type="Checkout Clean",
                reservation=self.name,
            )

    def _validate_dates(self):
        if getdate(self.departure_date) <= getdate(self.arrival_date):
            frappe.throw(_("Departure date must be after arrival date."))

    def _prevent_direct_policy_bypass(self):
        old = self.get_doc_before_save() if not self.is_new() else None
        if old and old.status != self.status and self.status in ("Checked In", "Checked Out", "Cancelled", "No Show"):
            frappe.throw(_("Use the controlled Front Desk action for check-in, check-out, cancellation, or no-show processing."))

    def _set_defaults(self):
        if not self.billing_customer:
            self.billing_customer = self.guest
        if not self.communication_contact:
            self.communication_contact = self.guest_contact or self.booked_by_contact
        if not self.cost_center and self.property:
            self.cost_center = frappe.db.get_value("Hotel Property", self.property, "default_cost_center")
        if not self.cancellation_policy and self.property:
            self.cancellation_policy = frappe.db.get_value("Hotel Property", self.property, "default_cancellation_policy")
        if not self.cancellation_policy:
            self.cancellation_policy = frappe.db.get_single_value("Hotel PMS Settings", "default_cancellation_policy")
        if not self.required_deposit and self.deposit_amount:
            self.required_deposit = self.deposit_amount

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
            capacity = frappe.db.get_value(
                "Hotel Room Type", row.room_type, ["max_adults", "max_children"], as_dict=True
            )
            if capacity and row.adults > capacity.max_adults:
                frappe.throw(_("Adults in room {0} exceed the room-type capacity of {1}.").format(row.room, capacity.max_adults))
            if capacity and row.children > capacity.max_children:
                frappe.throw(_("Children in room {0} exceed the room-type capacity of {1}.").format(row.room, capacity.max_children))

    def _validate_room_availability(self, exclude_self=False):
        if frappe.db.get_single_value("Hotel PMS Settings", "allow_overbooking"):
            return
        room_names = sorted({row.room for row in self.rooms if row.room})
        if room_names:
            placeholders = ", ".join(["%s"] * len(room_names))
            frappe.db.sql(
                f"select name from `tabHotel Room` where name in ({placeholders}) order by name for update",
                tuple(room_names),
            )
        requested_by_type = {}
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
            requested_by_type[row.room_type] = requested_by_type.get(row.room_type, 0) + 1

        # Room-type blocks protect group inventory even before exact room assignment.
        # Validate the aggregate request, not each row independently; otherwise two
        # rows can both consume the last remaining room, a tiny arithmetic tragedy.
        from hotel_pms.hotel_pms.doctype.hotel_group_booking.hotel_group_booking import get_available_room_type_capacity

        for room_type, requested in requested_by_type.items():
            available_capacity = get_available_room_type_capacity(
                property_name=self.property,
                room_type=room_type,
                arrival_date=self.arrival_date,
                departure_date=self.departure_date,
                exclude_group_booking=self.group_booking,
                exclude_reservation=self.name,
            )
            if available_capacity < requested:
                frappe.throw(
                    _("Only {0} unheld room(s) remain for {1}; this reservation requests {2}.").format(
                        available_capacity, room_type, requested
                    )
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
