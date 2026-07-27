from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from hotel_pms.room_status import set_room_status


BLOCKING_STATUSES = ("Tentative", "Confirmed", "Checked In")


class HotelReservation(Document):
    def validate(self):
        self._validate_dates()
        self._prevent_direct_policy_bypass()
        self._set_defaults()
        from hotel_pms.guest_portal import validate_reservation_guest_status
        validate_reservation_guest_status(self)
        self._apply_revenue_quote()
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
        if self.voucher_code:
            from hotel_pms.revenue import reserve_voucher_for_reservation
            redemption = reserve_voucher_for_reservation(self)
            if redemption and self.voucher_redemption != redemption:
                self.db_set("voucher_redemption", redemption)
            self._post_voucher_discount()

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
            set_room_status(
                row.room,
                operational_status="Occupied",
                event_type="Guest Check-in",
                source_doctype=self.doctype,
                source_name=self.name,
                idempotency_key=f"checkin:{self.name}:{row.room}",
            )
        self._ensure_folio()

    def check_out(self):
        if self.status != "Checked In":
            frappe.throw(_("Only checked-in reservations can be checked out."))
        if getdate() < getdate(self.departure_date):
            frappe.throw(_("This is an early departure. Amend the departure date first so inventory, audit history, and charges remain consistent."))
        from hotel_pms.front_desk import _reservation_balance
        balance = flt(_reservation_balance(self.name), 2)
        if self.billing_route == "Direct Bill":
            if frappe.db.get_single_value("Hotel PMS Settings", "require_direct_bill_approval"):
                approval = (
                    frappe.db.get_value(
                        "Hotel Direct Bill Approval", self.direct_bill_approval,
                        ["status", "approved_amount"], as_dict=True
                    ) if self.direct_bill_approval else None
                )
                if not approval or approval.status != "Approved" or flt(approval.approved_amount) < balance:
                    frappe.throw(_("Approved direct-bill authorization covering the current balance is required before checkout."))
        elif balance > 0.01:
            frappe.throw(
                _("Outstanding guest balance {0} must be invoiced and settled before checkout. Use the Hotel Checkout screen.").format(balance)
            )
        self.db_set({"status": "Checked Out", "actual_check_out_at": frappe.utils.now_datetime(), "travel_agent_commission_status": "Pending" if self.travel_agent_commission else self.travel_agent_commission_status})
        self._release_rooms(dirty=True)

        from hotel_pms.tasks import ensure_housekeeping_task

        for row in self.rooms:
            ensure_housekeeping_task(
                property_name=self.property,
                room=row.room,
                task_date=getdate(),
                task_type="Checkout Clean",
                reservation=self.name,
                source="Checkout",
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


    def _apply_revenue_quote(self):
        rows_with_plan = [row for row in self.rooms if row.rate_plan]
        require_quote = frappe.db.get_single_value("Hotel PMS Settings", "require_rate_quote_on_reservation")
        allow_manual = frappe.db.get_single_value("Hotel PMS Settings", "allow_manual_rate_without_plan")
        if self.rooms and len(rows_with_plan) != len(self.rooms):
            if require_quote or not allow_manual:
                frappe.throw(_("Every room requires a rate plan before this reservation can be saved."))
            return
        if not rows_with_plan:
            return
        from hotel_pms.revenue import _quote_booking_core
        payload = {
            "property": self.property,
            "reservation": self.name if not self.is_new() else None,
            "arrival_date": self.arrival_date,
            "departure_date": self.departure_date,
            "customer": self.guest,
            "voucher_code": self.voucher_code,
            "travel_agent_contract": self.travel_agent_contract,
            "room_requests": [
                {
                    "room_type": row.room_type,
                    "rate_plan": row.rate_plan,
                    "quantity": 1,
                    "adults": row.adults,
                    "children": row.children,
                    "requested_rate": row.nightly_rate if row.nightly_rate else None,
                    "rate_approval": self.rate_approval,
                }
                for row in self.rooms
            ],
        }
        quote = _quote_booking_core(payload)
        nights = max((getdate(self.departure_date) - getdate(self.arrival_date)).days, 1)
        for row, room_quote in zip(self.rooms, quote["rooms"]):
            row.quoted_stay_total = room_quote["advertised_total"]
            row.nightly_rate = flt(room_quote["advertised_total"]) / nights
            row.rate_quote_hash = room_quote["quote_hash"]
        self.rate_quote_hash = quote["quote_hash"]
        self.voucher_discount = quote["voucher_discount"]
        self.quoted_room_total = quote["advertised_total"]
        self.quoted_service_charge = quote["service_charge"]
        self.quoted_tax = quote["tax"]
        self.quoted_grand_total = quote["grand_total"]
        self.travel_agent_commission = quote["agent_commission"]
        if self.travel_agent_commission and not self.travel_agent_commission_status:
            self.travel_agent_commission_status = "Pending"

    def _post_voucher_discount(self):
        if not self.voucher_discount or not self.folio:
            return
        item = frappe.db.get_single_value("Hotel PMS Settings", "default_voucher_discount_item")
        if not item:
            frappe.throw(_("Configure Voucher Discount Item in Hotel PMS Settings before submitting a voucher reservation."))
        folio = frappe.get_doc("Hotel Folio", self.folio)
        key = f"VOUCHER:{self.name}:{self.voucher_code}"
        if any(row.idempotency_key == key for row in folio.charges):
            return
        folio.append("charges", {
            "posting_date": getdate(self.arrival_date),
            "charge_type": "Other",
            "item_code": item,
            "description": f"Voucher {self.voucher_code}",
            "qty": 1,
            "rate": -abs(self.voucher_discount),
            "cost_center": self.cost_center,
            "source_doctype": self.doctype,
            "source_name": self.name,
            "idempotency_key": key,
        })
        folio.save(ignore_permissions=True)

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
            set_room_status(
                row.room,
                operational_status="Available",
                housekeeping_status="Dirty" if dirty else "Clean",
                event_type="Guest Check-out" if dirty else "Reservation Released",
                source_doctype=self.doctype,
                source_name=self.name,
                idempotency_key=f"release:{self.name}:{row.room}:{'dirty' if dirty else 'clean'}",
            )
