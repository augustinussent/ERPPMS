from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, get_time, getdate, nowdate

from hotel_pms.hotel_pms.doctype.hotel_group_booking.hotel_group_booking import (
    get_available_room_type_capacity,
    get_package_billable_units,
)


@frappe.whitelist()
def check_group_availability(group_booking: str) -> dict:
    doc = frappe.get_doc("Hotel Group Booking", group_booking)
    doc.check_permission("read")
    doc.validate()
    room_summary = []
    for row in doc.room_blocks:
        available = get_available_room_type_capacity(
            doc.property,
            row.room_type,
            row.arrival_date,
            row.departure_date,
            exclude_group_booking=doc.name,
        )
        room_summary.append(
            {
                "room_type": row.room_type,
                "requested": cint(row.rooms_blocked),
                "available": available,
                "arrival_date": str(row.arrival_date),
                "departure_date": str(row.departure_date),
            }
        )
    return {
        "group_booking": doc.name,
        "rooms": room_summary,
        "functions_checked": len(doc.event_functions),
        "message": _("Room blocks and function spaces are available."),
    }


@frappe.whitelist()
def get_package_rate(package_template: str, occupancy_type: str = "Any", pricing_basis: str | None = None, pax: int = 0) -> dict:
    template = frappe.get_doc("Hotel Package Template", package_template)
    template.check_permission("read")
    candidates = []
    for row in template.rates:
        if row.occupancy_type not in (occupancy_type, "Any"):
            continue
        if pricing_basis and row.pricing_basis != pricing_basis:
            continue
        if cint(pax) and cint(row.minimum_pax) > cint(pax):
            continue
        candidates.append(row)
    if not candidates:
        frappe.throw(_("No applicable rate is configured for package {0}.").format(package_template))
    if cint(pax):
        candidates.sort(key=lambda row: (row.occupancy_type == occupancy_type, cint(row.minimum_pax)), reverse=True)
    else:
        candidates.sort(key=lambda row: (row.occupancy_type != occupancy_type, cint(row.minimum_pax)))
    row = candidates[0]
    return {"rate": flt(row.rate), "pricing_basis": row.pricing_basis, "occupancy_type": row.occupancy_type}


@frappe.whitelist()
def create_group_quotation(group_booking: str) -> dict:
    booking = _get_booking(group_booking, "write")
    if booking.quotation:
        return {"quotation": booking.quotation, "already_created": True}
    if not booking.packages:
        frappe.throw(_("Add at least one package before creating a quotation."))

    quotation = frappe.new_doc("Quotation")
    quotation.quotation_to = "Customer"
    quotation.party_name = booking.customer
    quotation.company = booking.company
    quotation.transaction_date = nowdate()
    quotation.valid_till = booking.arrival_date
    quotation.currency = booking.currency
    quotation.selling_price_list = booking.price_list
    if quotation.meta.has_field("custom_hotel_group_booking"):
        quotation.custom_hotel_group_booking = booking.name
    _apply_property_taxes(quotation, booking.property)

    for package in booking.packages:
        template = frappe.get_doc("Hotel Package Template", package.package_template)
        units = get_package_billable_units(package)
        quotation.append(
            "items",
            {
                "item_code": template.sales_item,
                "qty": units,
                "rate": package.unit_rate,
                "description": _package_description(package, template.package_name),
            },
        )
    quotation.insert()
    booking.db_set("quotation", quotation.name)
    return {"quotation": quotation.name, "already_created": False}


@frappe.whitelist()
def create_group_sales_order(group_booking: str) -> dict:
    booking = _get_booking(group_booking, "write")
    if booking.docstatus != 1:
        frappe.throw(_("Submit the group booking before creating a Sales Order."))
    if booking.sales_order:
        return {"sales_order": booking.sales_order, "already_created": True}
    if not booking.packages:
        frappe.throw(_("Add at least one package before creating a Sales Order."))

    order = frappe.new_doc("Sales Order")
    order.customer = booking.customer
    order.company = booking.company
    order.transaction_date = nowdate()
    order.delivery_date = booking.arrival_date
    order.currency = booking.currency
    order.selling_price_list = booking.price_list
    order.project = booking.project
    if order.meta.has_field("custom_hotel_group_booking"):
        order.custom_hotel_group_booking = booking.name
    _apply_property_taxes(order, booking.property)

    for package in booking.packages:
        template = frappe.get_doc("Hotel Package Template", package.package_template)
        order.append(
            "items",
            {
                "item_code": template.sales_item,
                "qty": get_package_billable_units(package),
                "rate": package.unit_rate,
                "delivery_date": booking.arrival_date,
                "description": _package_description(package, template.package_name),
                "project": booking.project,
            },
        )
    order.insert()
    booking.db_set("sales_order", order.name)
    return {"sales_order": order.name, "already_created": False}


@frappe.whitelist()
def create_participant_reservations(group_booking: str) -> dict:
    booking = _get_booking(group_booking, "write")
    if booking.docstatus != 1:
        frappe.throw(_("Submit the group booking before creating participant reservations."))

    grouped: dict[tuple, list] = defaultdict(list)
    for participant in booking.participants:
        if participant.participant_type != "Residential" or participant.reservation:
            continue
        if not participant.assigned_room:
            continue
        key = (
            participant.assigned_room,
            str(participant.arrival_date or booking.arrival_date),
            str(participant.departure_date or booking.departure_date),
        )
        grouped[key].append(participant)

    created = []
    skipped = 0
    missing_customers = []
    for (room, arrival, departure), participants in grouped.items():
        lead = participants[0]
        if not lead.customer:
            missing_customers.append(lead.participant_name)
            continue
        room_type = lead.room_type or frappe.db.get_value("Hotel Room", room, "room_type")
        nightly_rate = _find_room_block_rate(booking, room_type, arrival, departure)
        billing_customer = lead.customer if any(p.billing_route == "Individual Folio" for p in participants) else booking.customer
        reservation = frappe.get_doc(
            {
                "doctype": "Hotel Reservation",
                "property": booking.property,
                "status": "Confirmed",
                "guest": lead.customer,
                "billing_customer": billing_customer,
                "source": "Corporate",
                "source_reference": booking.name,
                "arrival_date": arrival,
                "departure_date": departure,
                "adults": len(participants),
                "children": 0,
                "group_booking": booking.name,
                "group_participant": lead.name,
                "billing_route": lead.billing_route,
                "rooms": [
                    {
                        "room_type": room_type,
                        "room": room,
                        "nightly_rate": nightly_rate,
                    }
                ],
            }
        )
        reservation.insert(ignore_permissions=True)
        reservation.submit()
        for participant in participants:
            frappe.db.set_value("Hotel Group Participant", participant.name, "reservation", reservation.name)
        created.append(reservation.name)

    if missing_customers:
        frappe.msgprint(
            _("Reservations were not created for these room leads because Guest Customer is missing: {0}").format(
                ", ".join(missing_customers)
            ),
            alert=True,
        )
    skipped = len([p for p in booking.participants if p.reservation])
    return {"created": created, "created_count": len(created), "already_linked": skipped, "missing_customers": missing_customers}


@frappe.whitelist()
def create_beo(group_booking: str) -> dict:
    booking = _get_booking(group_booking, "write")
    if not booking.event_functions:
        frappe.throw(_("Add at least one event function before creating a BEO."))
    latest_revision = frappe.db.sql(
        "select coalesce(max(revision_no), -1) from `tabHotel Banquet Event Order` where group_booking=%s",
        booking.name,
    )[0][0]
    beo = frappe.get_doc(
        {
            "doctype": "Hotel Banquet Event Order",
            "group_booking": booking.name,
            "revision_no": cint(latest_revision) + 1,
            "status": "Draft",
            "issue_date": nowdate(),
            "property": booking.property,
            "customer": booking.customer,
            "contact_person": booking.contact_person,
            "event_name": booking.booking_name,
            "event_start": booking.event_start,
            "event_end": booking.event_end,
            "guaranteed_pax": booking.guaranteed_pax,
            "special_requirements": booking.special_requirements,
            "billing_instruction": _billing_instruction_html(booking),
        }
    )
    for function in booking.event_functions:
        if function.status == "Cancelled":
            continue
        beo.append(
            "functions",
            {
                "function_name": function.function_name,
                "function_type": function.function_type,
                "start_datetime": function.start_datetime,
                "end_datetime": function.end_datetime,
                "function_space": function.function_space,
                "setup_style": function.setup_style,
                "guaranteed_pax": function.guaranteed_pax or function.billable_pax,
                "menu": function.menu,
                "equipment": function.equipment,
                "notes": function.notes,
            },
        )
    beo.insert()
    booking.db_set("current_beo", beo.name)
    return {"beo": beo.name, "revision": beo.revision_no}


@frappe.whitelist()
def ensure_group_folio(group_booking: str) -> dict:
    booking = _get_booking(group_booking, "write")
    name = booking._ensure_group_folio()
    return {"group_folio": name}


@frappe.whitelist()
def generate_package_schedule(group_booking: str) -> dict:
    booking = _get_booking(group_booking, "write")
    if booking.docstatus != 1:
        frappe.throw(_("Submit the group booking before generating the package schedule."))

    stale = frappe.get_all(
        "Hotel Package Posting",
        filters={
            "group_booking": booking.name,
            "status": ("in", ["Scheduled", "Prepared", "Served"]),
        },
        pluck="name",
    )
    for name in stale:
        frappe.delete_doc("Hotel Package Posting", name, ignore_permissions=True)

    created = 0
    skipped = 0
    for package_row in booking.packages:
        template = frappe.get_doc("Hotel Package Template", package_row.package_template)
        included_components = [component for component in template.components if component.included]
        if not included_components:
            continue
        allocation_total = sum(flt(component.allocation_percent) for component in included_components)
        for component in included_components:
            percentage = flt(component.allocation_percent) if allocation_total else 100 / len(included_components)
            component_total = flt(package_row.amount) * percentage / 100
            service_datetimes = _component_service_datetimes(package_row, component)
            if not service_datetimes:
                continue
            amount_per_instance = component_total / len(service_datetimes)
            for scheduled_datetime in service_datetimes:
                qty = _component_qty(component, package_row)
                rate = amount_per_instance / qty if qty else 0
                key = f"PKG:{booking.name}:{package_row.name}:{component.name}:{scheduled_datetime.isoformat()}"
                if frappe.db.exists("Hotel Package Posting", {"idempotency_key": key}):
                    skipped += 1
                    continue
                posting = frappe.get_doc(
                    {
                        "doctype": "Hotel Package Posting",
                        "group_booking": booking.name,
                        "group_package_row": package_row.name,
                        "package_template": package_row.package_template,
                        "scheduled_datetime": scheduled_datetime,
                        "status": "Scheduled",
                        "charge_category": component.charge_category,
                        "item_code": component.item_code,
                        "description": f"{template.package_name} - {component.component_name}",
                        "qty": qty,
                        "rate": rate,
                        "idempotency_key": key,
                        "notes": component.notes,
                    }
                ).insert(ignore_permissions=True)
                created += 1
    return {"created": created, "skipped": skipped, "replaced": len(stale)}


@frappe.whitelist()
def post_package_schedule(group_booking: str, business_date: str | None = None) -> dict:
    booking = _get_booking(group_booking, "write")
    return _post_package_schedule(booking, business_date)


def post_due_package_schedule_internal(group_booking: str, business_date: str | None = None) -> dict:
    booking = frappe.get_doc("Hotel Group Booking", group_booking)
    return _post_package_schedule(booking, business_date)


def _post_package_schedule(booking, business_date: str | None = None) -> dict:
    folio_name = booking._ensure_group_folio()
    folio = frappe.get_doc("Hotel Group Folio", folio_name)
    cutoff = getdate(business_date) if business_date else getdate()
    postings = frappe.get_all(
        "Hotel Package Posting",
        filters={
            "group_booking": booking.name,
            "status": ("in", ["Scheduled", "Prepared", "Served"]),
            "scheduled_datetime": ("<=", datetime.combine(cutoff, time.max)),
        },
        pluck="name",
        order_by="scheduled_datetime asc",
    )
    posted = 0
    skipped = 0
    for name in postings:
        posting = frappe.get_doc("Hotel Package Posting", name)
        # Compatibility with early v0.2 schedule rows that used the unsuffixed key.
        legacy = next((row for row in folio.charges if row.idempotency_key == posting.idempotency_key), None)
        if legacy:
            posting.db_set({"status": "Posted", "group_folio_charge": legacy.name})
            skipped += 1
            continue

        routes = _get_charge_routings(booking, posting.charge_category)
        charge_names = []
        added = False
        for index, routing in enumerate(routes, 1):
            route_key = f"{posting.idempotency_key}:ROUTE:{index}"
            existing = next((row for row in folio.charges if row.idempotency_key == route_key), None)
            if existing:
                charge_names.append(existing.name)
                continue
            percentage = flt(routing.get("percentage")) or 100
            charge = folio.append(
                "charges",
                {
                    "posting_date": getdate(posting.scheduled_datetime),
                    "charge_category": posting.charge_category,
                    "item_code": posting.item_code,
                    "description": posting.description,
                    "qty": posting.qty,
                    "rate": flt(posting.rate) * percentage / 100,
                    "cost_center": booking.cost_center,
                    "source_doctype": "Hotel Package Posting",
                    "source_name": posting.name,
                    "idempotency_key": route_key,
                    "billing_destination": routing["destination"],
                    "billing_customer": routing["customer"],
                    "participant_name": routing.get("participant_name"),
                },
            )
            charge_names.append(charge.name)
            added = True
        if added:
            folio.save(ignore_permissions=True)
            # Names are assigned during save; resolve them again from idempotency keys.
            charge_names = frappe.get_all(
                "Hotel Group Folio Charge",
                filters={"parent": folio.name, "source_doctype": "Hotel Package Posting", "source_name": posting.name},
                pluck="name",
                order_by="idx asc",
            )
            posted += 1
        else:
            skipped += 1
        posting.db_set({"status": "Posted", "group_folio_charge": ", ".join(charge_names)})
    return {"posted": posted, "skipped": skipped, "group_folio": folio.name}


@frappe.whitelist()
def create_group_sales_invoices(group_folio: str) -> dict:
    folio = frappe.get_doc("Hotel Group Folio", group_folio)
    folio.check_permission("write")
    booking = frappe.get_doc("Hotel Group Booking", folio.group_booking)
    uninvoiced = [row for row in folio.charges if not row.is_void and not row.is_already_invoiced and not row.sales_invoice]
    if not uninvoiced:
        frappe.throw(_("No uninvoiced group folio charges are available."))

    by_customer: dict[str, list] = defaultdict(list)
    for charge in uninvoiced:
        by_customer[charge.billing_customer or folio.billing_customer].append(charge)

    invoices = []
    for customer, charges in by_customer.items():
        invoice = frappe.new_doc("Sales Invoice")
        invoice.company = frappe.db.get_value("Hotel Property", folio.property, "company")
        invoice.customer = customer
        invoice.posting_date = nowdate()
        invoice.due_date = nowdate()
        invoice.project = booking.project
        if invoice.meta.has_field("custom_hotel_group_booking"):
            invoice.custom_hotel_group_booking = booking.name
        if invoice.meta.has_field("custom_hotel_group_folio"):
            invoice.custom_hotel_group_folio = folio.name
        if booking.sales_order and invoice.meta.has_field("custom_hotel_group_sales_order"):
            invoice.custom_hotel_group_sales_order = booking.sales_order
        _apply_property_taxes(invoice, booking.property)
        for charge in charges:
            invoice.append(
                "items",
                {
                    "item_code": charge.item_code,
                    "description": charge.description,
                    "qty": charge.qty,
                    "rate": charge.rate,
                    "cost_center": charge.cost_center or booking.cost_center,
                    "project": booking.project,
                },
            )
        invoice.insert()
        for charge in charges:
            charge.sales_invoice = invoice.name
        invoices.append(invoice.name)

    folio.sales_invoice = invoices[0] if len(invoices) == 1 else None
    folio.status = "Invoiced"
    folio.save()
    return {"sales_invoices": invoices, "count": len(invoices)}


@frappe.whitelist()
def confirmation_letter_url(group_booking: str, pdf: int = 0) -> dict:
    booking = _get_booking(group_booking, "read")
    format_name = "Hotel Group Confirmation Letter"
    if cint(pdf):
        url = (
            f"/api/method/frappe.utils.print_format.download_pdf?doctype={quote(booking.doctype)}"
            f"&name={quote(booking.name)}&format={quote(format_name)}&no_letterhead=0"
        )
    else:
        url = (
            f"/printview?doctype={quote(booking.doctype)}&name={quote(booking.name)}"
            f"&format={quote(format_name)}&no_letterhead=0"
        )
    return {"url": url, "print_format": format_name}


def _apply_property_taxes(document, property_name: str) -> None:
    taxes_template = frappe.db.get_value("Hotel Property", property_name, "default_sales_taxes_template")
    if taxes_template and document.meta.has_field("taxes_and_charges"):
        document.taxes_and_charges = taxes_template
        if hasattr(document, "set_taxes"):
            document.set_taxes()


def _get_booking(name: str, permission: str):
    doc = frappe.get_doc("Hotel Group Booking", name)
    doc.check_permission(permission)
    return doc


def _package_description(package, package_name: str) -> str:
    return _("{0}; {1} to {2}; {3}; billable pax {4}").format(
        package_name, package.date_from, package.date_to, package.occupancy_type, package.billable_pax
    )


def _find_room_block_rate(booking, room_type: str, arrival, departure) -> float:
    for block in booking.room_blocks:
        if block.room_type == room_type and getdate(block.arrival_date) <= getdate(arrival) and getdate(block.departure_date) >= getdate(departure):
            return flt(block.nightly_rate)
    return 0


def _billing_instruction_html(booking) -> str:
    if not booking.billing_instructions:
        return _("All contracted charges are billed to the master account; personal extras are paid individually.")
    items = [
        f"<li>{row.charge_category}: {row.destination}"
        + (f" - {row.customer}" if row.customer else "")
        + "</li>"
        for row in booking.billing_instructions
    ]
    return "<ul>" + "".join(items) + "</ul>"


def _component_service_datetimes(package_row, component) -> list[datetime]:
    start = getdate(package_row.date_from)
    end = getdate(package_row.date_to)
    service_time = get_time(component.service_time) if component.service_time else time(0, 0)
    offset = timedelta(days=cint(component.relative_day))
    base_dates = []
    if component.frequency == "Once":
        base_dates = [start]
    elif component.frequency == "Per Day":
        current = start
        while current <= end:
            base_dates.append(current)
            current += timedelta(days=1)
    elif component.frequency == "Per Night":
        current = start
        while current < end:
            base_dates.append(current)
            current += timedelta(days=1)
    return [datetime.combine(day + offset, service_time) for day in base_dates]


def _component_qty(component, package_row) -> float:
    multiplier = flt(component.qty_multiplier) or 1
    if component.calculation_basis == "Per Pax":
        return max(flt(package_row.billable_pax) * multiplier, multiplier)
    if component.calculation_basis == "Per Room":
        return max(flt(package_row.room_count) * multiplier, multiplier)
    return multiplier


def _get_charge_routings(booking, charge_category: str) -> list[dict]:
    exact_rows = [row for row in booking.billing_instructions if row.charge_category == charge_category]
    rows = exact_rows or [
        row
        for row in booking.billing_instructions
        if row.charge_category == "Package"
        and charge_category in ("Room", "Meeting Room", "Food", "Beverage", "Equipment", "Transport", "Other")
    ]
    matched = []
    for row in rows:
        customer = row.customer
        if row.destination == "Individual Folio" and row.participant_name and not customer:
            participant = next((p for p in booking.participants if p.participant_name == row.participant_name), None)
            customer = participant.customer if participant else None
        matched.append(
            {
                "destination": row.destination,
                "customer": customer or booking.customer,
                "participant_name": row.participant_name,
                "percentage": flt(row.percentage) or 100,
            }
        )
    return matched or [
        {
            "destination": "Master Folio",
            "customer": booking.customer,
            "participant_name": None,
            "percentage": 100,
        }
    ]

