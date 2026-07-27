from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.exceptions import DuplicateEntryError
from frappe.utils import add_days, cint, date_diff, flt, get_datetime, getdate, now_datetime, nowdate

from hotel_pms.sync import create_document_once, make_sync_key

BLOCKING_GROUP_STATUSES = ("Tentative", "Confirmed", "Event Active")


class HotelGroupBooking(Document):
    def validate(self):
        self._set_defaults()
        self._validate_dates()
        self._update_billable_values()
        self._update_room_assignments()
        self._validate_room_blocks()
        self._validate_participants()
        self._validate_function_spaces()
        self._validate_packages()
        self._validate_billing_instructions()
        self._validate_deposit_schedule()
        self._set_letter_defaults()

    def before_submit(self):
        if self.status in ("Inquiry", "Tentative"):
            self.status = "Confirmed"
        if not self.confirmed_on:
            self.confirmed_on = now_datetime()

    def on_submit(self):
        self._ensure_project()
        self._ensure_group_folio()

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        self._cancel_unchecked_reservations()

    def _set_defaults(self):
        if not self.inquiry_date:
            self.inquiry_date = nowdate()
        if self.property:
            property_values = frappe.db.get_value(
                "Hotel Property",
                self.property,
                ["company", "default_cost_center", "selling_price_list"],
                as_dict=True,
            ) or {}
            self.company = property_values.get("company")
            self.cost_center = self.cost_center or property_values.get("default_cost_center")
            self.price_list = self.price_list or property_values.get("selling_price_list")
        if not self.currency and self.company:
            self.currency = frappe.db.get_value("Company", self.company, "default_currency")

    def _validate_dates(self):
        if getdate(self.departure_date) <= getdate(self.arrival_date):
            frappe.throw(_("Departure date must be after arrival date."))
        if bool(self.event_start) != bool(self.event_end):
            frappe.throw(_("Set both Event Start and Event End, or leave both empty."))
        if self.event_start and self.event_end and get_datetime(self.event_end) <= get_datetime(self.event_start):
            frappe.throw(_("Event end must be after event start."))
        for label, value in (("Estimated Pax", self.estimated_pax), ("Guaranteed Pax", self.guaranteed_pax), ("Actual Pax", self.actual_pax)):
            if cint(value) < 0:
                frappe.throw(_("{0} cannot be negative.").format(label))
        if self.hold_until and self.status == "Tentative" and get_datetime(self.hold_until) <= now_datetime():
            frappe.throw(_("Tentative hold expiry must be in the future."))

    def _update_billable_values(self):
        self.billable_pax = _billable_pax(self.estimated_pax, self.guaranteed_pax, self.actual_pax)
        total = 0
        for row in self.event_functions:
            for value in (row.estimated_pax, row.guaranteed_pax, row.actual_pax):
                if cint(value) < 0:
                    frappe.throw(_("Event-function pax cannot be negative."))
            row.billable_pax = _billable_pax(row.estimated_pax, row.guaranteed_pax, row.actual_pax)
        for row in self.packages:
            for value in (row.estimated_pax, row.guaranteed_pax, row.actual_pax, row.room_count):
                if cint(value) < 0:
                    frappe.throw(_("Package pax and room count cannot be negative."))
            row.billable_pax = _billable_pax(row.estimated_pax, row.guaranteed_pax, row.actual_pax)
            row.billable_units = get_package_billable_units(row)
            row.amount = flt(row.billable_units) * flt(row.unit_rate)
            total += flt(row.amount)
        self.total_package_amount = total

    def _update_room_assignments(self):
        for block in self.room_blocks:
            assigned_rooms = {
                participant.assigned_room
                for participant in self.participants
                if participant.assigned_room
                and participant.room_type == block.room_type
                and _dates_overlap(
                    participant.arrival_date or self.arrival_date,
                    participant.departure_date or self.departure_date,
                    block.arrival_date,
                    block.departure_date,
                )
            }
            block.rooms_assigned = len(assigned_rooms)
            if block.block_status == "Released":
                block.outstanding_rooms = 0
                continue
            block.outstanding_rooms = max(cint(block.rooms_blocked) - cint(block.rooms_assigned), 0)
            block.block_status = "Consumed" if block.outstanding_rooms == 0 else "Active"

    def _validate_room_blocks(self):
        for row in self.room_blocks:
            if getdate(row.departure_date) <= getdate(row.arrival_date):
                frappe.throw(_("Room block departure must be after arrival for {0}.").format(row.room_type))
            if cint(row.rooms_blocked) <= 0:
                frappe.throw(_("Rooms blocked must be greater than zero for {0}.").format(row.room_type))
            room_type_property = frappe.db.get_value("Hotel Room Type", row.room_type, "property")
            if room_type_property != self.property:
                frappe.throw(_("Room type {0} belongs to another property.").format(row.room_type))
            if row.release_date and getdate(row.release_date) > getdate(row.arrival_date):
                frappe.throw(_("Room block release date cannot be after arrival date."))

        checked = set()
        for row in self.room_blocks:
            key = (row.room_type, str(row.arrival_date), str(row.departure_date))
            if key in checked:
                continue
            checked.add(key)
            requested = sum(
                cint(other.rooms_blocked)
                for other in self.room_blocks
                if other.room_type == row.room_type
                and _dates_overlap(other.arrival_date, other.departure_date, row.arrival_date, row.departure_date)
                and other.block_status != "Released"
            )
            available = get_available_room_type_capacity(
                property_name=self.property,
                room_type=row.room_type,
                arrival_date=row.arrival_date,
                departure_date=row.departure_date,
                exclude_group_booking=self.name,
            )
            if requested > available:
                frappe.throw(
                    _("Only {0} room(s) of type {1} are available for {2} to {3}; this group requests {4}.").format(
                        available, row.room_type, row.arrival_date, row.departure_date, requested
                    )
                )

    def _validate_participants(self):
        room_periods: dict[str, list[tuple]] = defaultdict(list)
        occupancy_groups: dict[tuple, list] = defaultdict(list)
        for row in self.participants:
            arrival = row.arrival_date or self.arrival_date
            departure = row.departure_date or self.departure_date
            row.arrival_date = arrival
            row.departure_date = departure
            if row.participant_type == "Residential":
                if getdate(departure) <= getdate(arrival):
                    frappe.throw(_("Invalid stay dates for participant {0}.").format(row.participant_name))
                if row.assigned_room:
                    room = frappe.db.get_value(
                        "Hotel Room", row.assigned_room, ["property", "room_type", "enabled"], as_dict=True
                    )
                    if not room or not room.enabled or room.property != self.property:
                        frappe.throw(_("Assigned room for {0} is invalid.").format(row.participant_name))
                    if row.room_type and room.room_type != row.room_type:
                        frappe.throw(_("Assigned room type does not match participant {0}.").format(row.participant_name))
                    row.room_type = room.room_type
                    period = (getdate(arrival), getdate(departure))
                    for existing_start, existing_end in room_periods[row.assigned_room]:
                        if _dates_overlap(existing_start, existing_end, period[0], period[1]) and (existing_start, existing_end) != period:
                            frappe.throw(
                                _("Participants sharing room {0} must use the same overlapping stay dates.").format(row.assigned_room)
                            )
                    room_periods[row.assigned_room].append(period)
                    occupancy_groups[(row.assigned_room, period[0], period[1], row.room_type)].append(row)

                    conflict = frappe.db.sql(
                        """
                        select r.name
                        from `tabHotel Reservation` r
                        inner join `tabHotel Reservation Room` rr on rr.parent = r.name
                        where rr.room = %(room)s
                          and r.docstatus < 2
                          and r.status in ('Tentative', 'Confirmed', 'Checked In')
                          and r.arrival_date < %(departure)s
                          and r.departure_date > %(arrival)s
                          and (%(group_booking)s = '' or coalesce(r.group_booking, '') != %(group_booking)s)
                        limit 1
                        """,
                        {
                            "room": row.assigned_room,
                            "arrival": getdate(arrival),
                            "departure": getdate(departure),
                            "group_booking": self.name or "",
                        },
                        as_dict=True,
                    )
                    if conflict:
                        frappe.throw(
                            _("Assigned room {0} conflicts with reservation {1}.").format(
                                row.assigned_room, conflict[0].name
                            )
                        )
            elif row.assigned_room:
                frappe.throw(_("Non-residential participant {0} cannot have an assigned room.").format(row.participant_name))

        for (room_name, arrival, departure, room_type), occupants in occupancy_groups.items():
            max_adults = cint(frappe.db.get_value("Hotel Room Type", room_type, "max_adults"))
            if max_adults and len(occupants) > max_adults:
                frappe.throw(
                    _("Room {0} has {1} participant(s), above room-type capacity {2}.").format(
                        room_name, len(occupants), max_adults
                    )
                )

    def _validate_function_spaces(self):
        for index, row in enumerate(self.event_functions):
            start = get_datetime(row.start_datetime)
            end = get_datetime(row.end_datetime)
            if end <= start:
                frappe.throw(_("Function end must be after start for {0}.").format(row.function_name))
            if not row.function_space or row.status == "Cancelled":
                continue
            space = frappe.db.get_value(
                "Hotel Function Space",
                row.function_space,
                ["property", "enabled", "default_capacity", "setup_minutes", "breakdown_minutes"],
                as_dict=True,
            )
            if not space or not space.enabled or space.property != self.property:
                frappe.throw(_("Function space {0} is disabled or belongs to another property.").format(row.function_space))
            capacity = get_function_space_capacity(row.function_space, row.setup_style, space.default_capacity)
            if capacity and cint(row.billable_pax) > capacity:
                frappe.throw(
                    _("{0} has capacity {1} for setup {2}, below billable pax {3}.").format(
                        row.function_space, capacity, row.setup_style or "default", row.billable_pax
                    )
                )
            for other in self.event_functions[index + 1 :]:
                if (
                    other.function_space == row.function_space
                    and other.status != "Cancelled"
                    and _datetimes_overlap(row.start_datetime, row.end_datetime, other.start_datetime, other.end_datetime)
                ):
                    frappe.throw(_("Functions {0} and {1} overlap in {2}.").format(row.function_name, other.function_name, row.function_space))

            conflict = frappe.db.sql(
                """
                select gb.name, ef.function_name
                from `tabHotel Group Event Function` ef
                inner join `tabHotel Group Booking` gb on gb.name = ef.parent
                where ef.function_space = %(space)s
                  and ef.status != 'Cancelled'
                  and gb.docstatus < 2
                  and gb.status in ('Tentative', 'Confirmed', 'Event Active')
                  and gb.name != %(booking)s
                  and ef.start_datetime < %(end)s
                  and ef.end_datetime > %(start)s
                limit 1
                """,
                {
                    "space": row.function_space,
                    "booking": self.name or "",
                    "start": start - timedelta(minutes=cint(space.setup_minutes)),
                    "end": end + timedelta(minutes=cint(space.breakdown_minutes)),
                },
                as_dict=True,
            )
            if conflict:
                frappe.throw(
                    _("Function space {0} conflicts with {1} in group booking {2}.").format(
                        row.function_space, conflict[0].function_name, conflict[0].name
                    )
                )

    def _validate_packages(self):
        for row in self.packages:
            if getdate(row.date_to) < getdate(row.date_from):
                frappe.throw(_("Package end date cannot be before start date."))
            template = frappe.db.get_value(
                "Hotel Package Template",
                row.package_template,
                ["property", "enabled", "minimum_pax"],
                as_dict=True,
            )
            if not template or not template.enabled or template.property != self.property:
                frappe.throw(_("Package template {0} is unavailable for this property.").format(row.package_template))
            if cint(row.billable_pax) and cint(row.billable_pax) < cint(template.minimum_pax):
                frappe.throw(
                    _("Package {0} requires at least {1} pax.").format(row.package_template, template.minimum_pax)
                )

    def _validate_billing_instructions(self):
        totals: dict[str, float] = defaultdict(float)
        for row in self.billing_instructions:
            percentage = flt(row.percentage)
            if percentage <= 0 or percentage > 100:
                frappe.throw(_("Billing percentage for {0} must be greater than 0 and no more than 100.").format(row.charge_category))
            totals[row.charge_category] += percentage
            if row.destination == "Individual Folio" and not row.participant_name and not row.customer:
                frappe.throw(_("Individual Folio routing for {0} requires a participant name or billing customer.").format(row.charge_category))
        for category, total in totals.items():
            if abs(total - 100) > 0.01:
                frappe.throw(_("Billing instructions for {0} must total 100%; current total is {1}%.").format(category, total))

    def _validate_deposit_schedule(self):
        total = 0
        percent_total = 0
        for row in self.deposit_schedules:
            if row.calculation_type == "Percent":
                if flt(row.percentage) <= 0 or flt(row.percentage) > 100:
                    frappe.throw(_("Deposit percentage for {0} must be greater than 0 and no more than 100.").format(row.milestone))
                row.amount = flt(self.total_package_amount) * flt(row.percentage) / 100
                percent_total += flt(row.percentage)
            elif flt(row.amount) <= 0:
                frappe.throw(_("Fixed deposit amount for {0} must be greater than zero.").format(row.milestone))
            total += flt(row.amount)
        if percent_total > 100.01:
            frappe.throw(_("Deposit schedule percentages cannot exceed 100%."))
        if self.deposit_schedules:
            self.deposit_amount = total

    def _set_letter_defaults(self):
        self.confirmation_letter_date = self.confirmation_letter_date or nowdate()
        self.confirmation_letter_contact_name = self.confirmation_letter_contact_name or self.contact_name
        self.confirmation_letter_subject = self.confirmation_letter_subject or _("Booking Confirmation - {0}").format(self.booking_name)
        self.confirmation_letter_intro = self.confirmation_letter_intro or _(
            "Thank you for choosing our hotel. We are pleased to confirm the following group booking arrangements."
        )

    def _ensure_project(self):
        if self.project and frappe.db.exists("Project", self.project):
            return self.project

        base_key = make_sync_key("PROJECT", "GROUP", self.name)

        def build():
            return frappe.get_doc(
                {
                    "doctype": "Project",
                    "project_name": f"{self.name} - {self.booking_name}",
                    "customer": self.customer,
                    "company": self.company,
                    "expected_start_date": self.arrival_date,
                    "expected_end_date": self.departure_date,
                    "status": "Open",
                }
            )

        project, _already_created = create_document_once(
            base_key=base_key,
            operation="Create Group Project",
            source_doctype=self.doctype,
            source_name=self.name,
            target_doctype="Project",
            build_document=build,
            payload={"booking_name": self.booking_name, "customer": self.customer},
            ignore_permissions=True,
        )
        if self.project != project.name:
            self.db_set("project", project.name)
        return project.name

    def _ensure_group_folio(self):
        existing = frappe.db.get_value("Hotel Group Folio", {"group_booking": self.name}, "name")
        if existing:
            if self.group_folio != existing:
                self.db_set("group_folio", existing)
            return existing
        try:
            folio = frappe.get_doc(
                {
                    "doctype": "Hotel Group Folio",
                    "group_booking": self.name,
                    "property": self.property,
                    "billing_customer": self.customer,
                    "status": "Open",
                }
            ).insert(ignore_permissions=True)
            existing = folio.name
        except DuplicateEntryError:
            existing = frappe.db.get_value("Hotel Group Folio", {"group_booking": self.name}, "name")
            if not existing:
                raise
        if self.group_folio != existing:
            self.db_set("group_folio", existing)
        return existing

    def _cancel_unchecked_reservations(self):
        reservations = frappe.get_all(
            "Hotel Reservation",
            filters={"group_booking": self.name, "docstatus": 1},
            fields=["name", "status"],
        )
        for reservation in reservations:
            if reservation.status == "Checked In":
                frappe.throw(_("Cannot cancel group booking while reservation {0} is checked in.").format(reservation.name))
            frappe.get_doc("Hotel Reservation", reservation.name).cancel()


def _billable_pax(estimated, guaranteed, actual) -> int:
    guaranteed_value = cint(guaranteed)
    actual_value = cint(actual)
    if guaranteed_value or actual_value:
        return max(guaranteed_value, actual_value)
    return cint(estimated)


def get_package_billable_units(row) -> float:
    pax = flt(row.billable_pax)
    days = max(date_diff(getdate(row.date_to), getdate(row.date_from)) + 1, 1)
    nights = max(date_diff(getdate(row.date_to), getdate(row.date_from)), 1)
    if row.pricing_basis == "Per Person Per Day":
        return pax * days
    if row.pricing_basis == "Per Person Per Night":
        return pax * nights
    if row.pricing_basis == "Per Person Package":
        return pax
    if row.pricing_basis == "Per Room Per Night":
        return flt(row.room_count) * nights
    return 1


def get_available_room_type_capacity(property_name, room_type, arrival_date, departure_date, exclude_group_booking=None, exclude_reservation=None) -> int:
    total_rooms = frappe.db.sql(
        """
        select count(*)
        from `tabHotel Room`
        where property = %(property)s
          and room_type = %(room_type)s
          and enabled = 1
          and operational_status not in ('Out of Order', 'Out of Service')
        """,
        {"property": property_name, "room_type": room_type},
    )[0][0]

    reservation_count = frappe.db.sql(
        """
        select count(rr.name)
        from `tabHotel Reservation Room` rr
        inner join `tabHotel Reservation` r on r.name = rr.parent
        where r.property = %(property)s
          and rr.room_type = %(room_type)s
          and r.docstatus < 2
          and r.status in ('Tentative', 'Confirmed', 'Checked In')
          and r.arrival_date < %(departure)s
          and r.departure_date > %(arrival)s
          and r.name != %(exclude_reservation)s
          and (%(exclude_group)s = '' or coalesce(r.group_booking, '') != %(exclude_group)s)
        """,
        {
            "property": property_name,
            "room_type": room_type,
            "arrival": getdate(arrival_date),
            "departure": getdate(departure_date),
            "exclude_group": exclude_group_booking or "",
            "exclude_reservation": exclude_reservation or "",
        },
    )[0][0]

    held_count = frappe.db.sql(
        """
        select coalesce(sum(greatest(rb.rooms_blocked - rb.rooms_assigned, 0)), 0)
        from `tabHotel Group Room Block` rb
        inner join `tabHotel Group Booking` gb on gb.name = rb.parent
        where gb.property = %(property)s
          and rb.room_type = %(room_type)s
          and rb.block_status = 'Active'
          and gb.docstatus < 2
          and gb.status in ('Tentative', 'Confirmed', 'Event Active')
          and gb.name != %(exclude_group)s
          and rb.arrival_date < %(departure)s
          and rb.departure_date > %(arrival)s
        """,
        {
            "property": property_name,
            "room_type": room_type,
            "arrival": getdate(arrival_date),
            "departure": getdate(departure_date),
            "exclude_group": exclude_group_booking or "",
        },
    )[0][0]
    distribution_count = 0
    if frappe.db.exists("DocType", "Hotel Distribution Event"):
        rows = frappe.db.sql(
            """select count(distinct echo_key) from `tabHotel Distribution Event`
            where property=%(property)s and room_type=%(room_type)s
              and event_type='Calendar Block' and status in ('Pending','Processed','Needs Review','Echo')
              and arrival_date < %(departure)s and departure_date > %(arrival)s""",
            {"property": property_name, "room_type": room_type, "arrival": getdate(arrival_date), "departure": getdate(departure_date)},
        )
        distribution_count = cint(rows[0][0] if rows else 0)
    return max(cint(total_rooms) - cint(reservation_count) - cint(held_count) - distribution_count, 0)


def get_function_space_capacity(function_space: str, setup_style: str | None, fallback: int = 0) -> int:
    if setup_style:
        capacity = frappe.db.get_value(
            "Hotel Function Space Capacity",
            {"parent": function_space, "setup_style": setup_style},
            "capacity",
        )
        if capacity is not None:
            return cint(capacity)
    return cint(fallback)


def _dates_overlap(start_a, end_a, start_b, end_b) -> bool:
    return getdate(start_a) < getdate(end_b) and getdate(end_a) > getdate(start_b)


def _datetimes_overlap(start_a, end_a, start_b, end_b) -> bool:
    return get_datetime(start_a) < get_datetime(end_b) and get_datetime(end_a) > get_datetime(start_b)
