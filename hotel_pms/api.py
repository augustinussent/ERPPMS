from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime


def has_app_permission() -> bool:
    return bool(frappe.has_permission("Hotel Property", "read"))


@frappe.whitelist()
def check_in(reservation: str) -> dict:
    doc = frappe.get_doc("Hotel Reservation", reservation)
    doc.check_permission("write")
    doc.check_in()
    return {"reservation": doc.name, "status": doc.status}


@frappe.whitelist()
def check_out(reservation: str) -> dict:
    doc = frappe.get_doc("Hotel Reservation", reservation)
    doc.check_permission("write")
    doc.check_out()
    return {"reservation": doc.name, "status": doc.status}


@frappe.whitelist()
def run_night_audit(property: str, business_date: str | None = None) -> dict:
    """Post one room charge per occupied room for the business date.

    The idempotency key prevents duplicate posting when a human presses the
    button twice, a surprisingly popular operational tradition.
    """
    frappe.only_for(["System Manager", "Hotel Manager", "Night Auditor"])
    audit_date = getdate(business_date) if business_date else getdate()

    reservations = frappe.get_all(
        "Hotel Reservation",
        filters={
            "property": property,
            "status": "Checked In",
            "arrival_date": ("<=", audit_date),
            "departure_date": (">", audit_date),
            "docstatus": 1,
        },
        pluck="name",
    )

    posted = 0
    skipped = 0
    for reservation_name in reservations:
        reservation = frappe.get_doc("Hotel Reservation", reservation_name)
        folio = _get_or_create_folio(reservation)

        for row in reservation.rooms:
            key = f"ROOM:{reservation.name}:{row.room}:{audit_date.isoformat()}"
            exists = frappe.db.exists(
                "Hotel Folio Charge",
                {"parent": folio.name, "idempotency_key": key},
            )
            if exists:
                skipped += 1
                continue

            room_item = frappe.db.get_value("Hotel Room Type", row.room_type, "room_revenue_item")
            if not room_item:
                frappe.throw(_("Room revenue item is not configured for room type {0}").format(row.room_type))

            folio.append(
                "charges",
                {
                    "posting_date": audit_date,
                    "charge_type": "Room",
                    "item_code": room_item,
                    "description": f"Room {row.room} - {audit_date.isoformat()}",
                    "qty": 1,
                    "rate": row.nightly_rate,
                    "room": row.room,
                    "source_doctype": "Hotel Reservation",
                    "source_name": reservation.name,
                    "idempotency_key": key,
                },
            )
            posted += 1

        folio.last_activity_at = now_datetime()
        folio.save(ignore_permissions=True)

    from hotel_pms.group_booking import post_due_package_schedule_internal

    group_posted = 0
    group_skipped = 0
    group_bookings = frappe.get_all(
        "Hotel Group Booking",
        filters={
            "property": property,
            "docstatus": 1,
            "status": ("in", ["Confirmed", "Event Active"]),
        },
        pluck="name",
    )
    for group_booking in group_bookings:
        result = post_due_package_schedule_internal(group_booking, audit_date.isoformat())
        group_posted += result.get("posted", 0)
        group_skipped += result.get("skipped", 0)

    return {
        "property": property,
        "business_date": audit_date.isoformat(),
        "reservations": len(reservations),
        "posted": posted,
        "skipped": skipped,
        "group_bookings": len(group_bookings),
        "group_package_posted": group_posted,
        "group_package_skipped": group_skipped,
    }


@frappe.whitelist()
def create_sales_invoice(folio: str) -> dict:
    folio_doc = frappe.get_doc("Hotel Folio", folio)
    folio_doc.check_permission("write")

    if folio_doc.sales_invoice:
        return {"sales_invoice": folio_doc.sales_invoice, "already_created": True}
    if not folio_doc.charges:
        frappe.throw(_("Folio has no charges."))

    reservation = frappe.get_doc("Hotel Reservation", folio_doc.reservation)
    invoice = frappe.new_doc("Sales Invoice")
    invoice.company = reservation.company
    invoice.customer = folio_doc.billing_customer or reservation.guest
    invoice.posting_date = getdate()
    invoice.due_date = getdate()
    if invoice.meta.has_field("custom_hotel_folio"):
        invoice.custom_hotel_folio = folio_doc.name
    if invoice.meta.has_field("custom_hotel_reservation"):
        invoice.custom_hotel_reservation = reservation.name

    property_doc = frappe.get_doc("Hotel Property", reservation.property)
    if property_doc.default_sales_taxes_template:
        invoice.taxes_and_charges = property_doc.default_sales_taxes_template
        invoice.set_taxes()

    for charge in folio_doc.charges:
        if charge.is_void or charge.is_already_invoiced:
            continue
        invoice.append(
            "items",
            {
                "item_code": charge.item_code,
                "item_name": charge.description,
                "description": charge.description,
                "qty": charge.qty,
                "rate": charge.rate,
                "cost_center": charge.cost_center or reservation.cost_center,
            },
        )

    if not invoice.items:
        frappe.throw(_("No uninvoiced folio charges are available."))

    invoice.insert()
    folio_doc.sales_invoice = invoice.name
    folio_doc.status = "Invoiced"
    folio_doc.save()
    return {"sales_invoice": invoice.name, "already_created": False}


def _get_or_create_folio(reservation) -> "frappe.model.document.Document":
    folio_name = frappe.db.get_value("Hotel Folio", {"reservation": reservation.name}, "name")
    if folio_name:
        return frappe.get_doc("Hotel Folio", folio_name)

    folio = frappe.get_doc(
        {
            "doctype": "Hotel Folio",
            "property": reservation.property,
            "reservation": reservation.name,
            "guest": reservation.guest,
            "billing_customer": reservation.billing_customer or reservation.guest,
            "status": "Open",
        }
    )
    folio.insert(ignore_permissions=True)
    return folio
