from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any

import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate

from hotel_pms.front_desk_rules import calculate_fee, money, quote_cancellation, room_nights, stay_total
from hotel_pms.room_status import set_room_status
from hotel_pms.sync import create_document_once, make_sync_key

BLOCKING_STATUSES = ("Tentative", "Confirmed", "Checked In")
ACTIVE_CANCELLATION_STATUSES = ("Tentative", "Confirmed")


def get_locked_reservation(name: str):
    """Lock a reservation row for the current transaction before changing state."""
    if not frappe.db.sql("select name from `tabHotel Reservation` where name=%s for update", name):
        frappe.throw(_("Reservation {0} does not exist.").format(name))
    return frappe.get_doc("Hotel Reservation", name)


def _require_front_desk_access() -> None:
    frappe.only_for(["System Manager", "Hotel Manager", "Front Desk", "Night Auditor"])


def _json_payload(payload: str | dict) -> dict:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            frappe.throw(_("Invalid JSON payload: {0}").format(exc))
    return payload or {}


def _reservation_balance(reservation_name: str) -> float:
    """Operational amount due without double-counting allocated advances.

    Active invoice outstanding is authoritative for invoiced rows. Only uninvoiced
    folio rows are added separately. Unallocated advance is then deducted.
    """
    folio = frappe.db.get_value("Hotel Folio", {"reservation": reservation_name}, "name")
    if not folio:
        return 0.0
    uninvoiced = frappe.db.sql(
        """
        select coalesce(sum(case when is_void = 0 and coalesce(sales_invoice, '') = '' then amount else 0 end), 0)
        from `tabHotel Folio Charge`
        where parent=%s and parenttype='Hotel Folio'
        """,
        folio,
    )[0][0]
    invoices = set(
        frappe.get_all(
            "Hotel Folio Charge",
            filters={"parent": folio, "sales_invoice": ("is", "set")},
            pluck="sales_invoice",
        )
    )
    outstanding = 0.0
    for invoice in invoices:
        if not frappe.db.exists("Sales Invoice", invoice):
            continue
        row = frappe.db.get_value("Sales Invoice", invoice, ["docstatus", "outstanding_amount"], as_dict=True)
        if row and row.docstatus != 2:
            outstanding += flt(row.outstanding_amount)
    deposit = get_deposit_summary(reservation_name)
    return max(flt(uninvoiced) + outstanding - flt(deposit["available_credit"]), 0.0)


@frappe.whitelist()
def get_today_dashboard(property: str, business_date: str | None = None) -> dict:
    _require_front_desk_access()
    date = getdate(business_date or nowdate())
    reservations = frappe.get_all(
        "Hotel Reservation",
        filters={
            "property": property,
            "docstatus": 1,
            "status": ("in", ["Tentative", "Confirmed", "Checked In"]),
            "arrival_date": ("<=", date),
        },
        fields=[
            "name", "guest", "billing_customer", "status", "arrival_date", "departure_date",
            "arrival_time", "departure_time", "source", "folio", "registration",
        ],
        order_by="arrival_date asc, arrival_time asc",
    )
    room_rows = frappe.db.sql(
        """
        select rr.parent, rr.room, rr.room_type
        from `tabHotel Reservation Room` rr
        inner join `tabHotel Reservation` r on r.name=rr.parent
        where r.property=%s and r.docstatus=1 and r.status not in ('Cancelled', 'No Show')
          and r.arrival_date <= %s and r.departure_date >= %s
        """,
        (property, date, date),
        as_dict=True,
    )
    rooms_by_reservation: dict[str, list] = defaultdict(list)
    for row in room_rows:
        rooms_by_reservation[row.parent].append({"room": row.room, "room_type": row.room_type})

    result = {"arrivals": [], "departures": [], "in_house": [], "no_show_candidates": []}
    for row in reservations:
        row["rooms"] = rooms_by_reservation.get(row.name, [])
        row["balance"] = _reservation_balance(row.name)
        if getdate(row.arrival_date) == date and row.status in ("Tentative", "Confirmed"):
            result["arrivals"].append(row)
        if row.status in ("Tentative", "Confirmed") and _is_no_show_candidate(row, date):
            result["no_show_candidates"].append(row)
        if getdate(row.departure_date) == date and row.status == "Checked In":
            result["departures"].append(row)
        if row.status == "Checked In" and getdate(row.arrival_date) <= date < getdate(row.departure_date):
            result["in_house"].append(row)

    room_summary = frappe.db.sql(
        """
        select operational_status, housekeeping_status, count(*) as qty
        from `tabHotel Room`
        where property=%s and enabled=1
        group by operational_status, housekeeping_status
        """,
        property,
        as_dict=True,
    )
    summary = {
        "arrivals": len(result["arrivals"]),
        "departures": len(result["departures"]),
        "in_house": len(result["in_house"]),
        "no_show_candidates": len(result["no_show_candidates"]),
        "rooms": room_summary,
    }
    return {"property": property, "business_date": str(date), "summary": summary, **result}


def _is_no_show_candidate(row, business_date) -> bool:
    if row.status not in ("Tentative", "Confirmed") or getdate(row.arrival_date) > getdate(business_date):
        return False
    cutoff_hours = cint(frappe.db.get_single_value("Hotel PMS Settings", "no_show_cutoff_hours") or 4)
    expected_time = str(row.arrival_time or "18:00:00")
    expected = get_datetime(f"{getdate(row.arrival_date)} {expected_time}")
    return now_datetime() >= expected + timedelta(hours=cutoff_hours)


@frappe.whitelist()
def get_tape_chart(property: str, start_date: str | None = None, days: int = 14) -> dict:
    _require_front_desk_access()
    start = getdate(start_date or nowdate())
    days = max(1, min(cint(days or 14), 62))
    end = add_days(start, days)
    dates = [str(add_days(start, index)) for index in range(days)]
    rooms = frappe.get_all(
        "Hotel Room",
        filters={"property": property, "enabled": 1},
        fields=["name", "room_number", "room_type", "floor", "operational_status", "housekeeping_status"],
        order_by="floor asc, room_number asc",
    )
    reservations = frappe.db.sql(
        """
        select r.name, r.guest, r.status, r.arrival_date, r.departure_date,
               rr.room, rr.room_type, rr.nightly_rate
        from `tabHotel Reservation` r
        inner join `tabHotel Reservation Room` rr on rr.parent=r.name
        where r.property=%s and r.docstatus=1
          and r.status in ('Tentative','Confirmed','Checked In')
          and r.arrival_date < %s and r.departure_date > %s
        order by r.arrival_date, r.name
        """,
        (property, end, start),
        as_dict=True,
    )
    bars = []
    for row in reservations:
        visible_start = max(getdate(row.arrival_date), start)
        visible_end = min(getdate(row.departure_date), end)
        bars.append(
            {
                **row,
                "arrival_date": str(row.arrival_date),
                "departure_date": str(row.departure_date),
                "start_index": (visible_start - start).days,
                "span": max((visible_end - visible_start).days, 1),
            }
        )
    return {"property": property, "start_date": str(start), "end_date": str(end), "dates": dates, "rooms": rooms, "bars": bars}


@frappe.whitelist()
def get_available_rooms(
    property: str,
    arrival_date: str,
    departure_date: str,
    room_type: str | None = None,
    exclude_reservation: str | None = None,
) -> list[dict]:
    _require_front_desk_access()
    arrival = getdate(arrival_date)
    departure = getdate(departure_date)
    if departure <= arrival:
        frappe.throw(_("Departure date must be after arrival date."))
    filters: dict[str, Any] = {"property": property, "enabled": 1, "operational_status": ("not in", ["Out of Order", "Out of Service"])}
    if room_type:
        filters["room_type"] = room_type
    rooms = frappe.get_all("Hotel Room", filters=filters, fields=["name", "room_number", "room_type", "floor", "housekeeping_status"])
    conflicts = set(
        frappe.db.sql_list(
            """
            select distinct rr.room
            from `tabHotel Reservation` r
            inner join `tabHotel Reservation Room` rr on rr.parent=r.name
            where r.property=%(property)s and r.docstatus < 2
              and r.status in ('Tentative','Confirmed','Checked In')
              and r.arrival_date < %(departure)s and r.departure_date > %(arrival)s
              and r.name != %(exclude)s
            """,
            {"property": property, "arrival": arrival, "departure": departure, "exclude": exclude_reservation or ""},
        )
    )
    return [room for room in rooms if room.name not in conflicts]


@frappe.whitelist()
def quick_multi_room_booking(payload: str | dict) -> dict:
    _require_front_desk_access()
    data = _json_payload(payload)
    required = ["property", "guest", "arrival_date", "departure_date", "room_requests", "idempotency_key"]
    for field in required:
        if not data.get(field):
            frappe.throw(_("Missing required field: {0}").format(field))
    key = make_sync_key("RES", "QUICK", data["idempotency_key"])
    existing = frappe.db.get_value("Hotel Reservation", {"idempotency_key": key}, "name")
    if existing:
        return {"reservation": existing, "already_created": True}

    booking_quote = None
    if all(request.get("rate_plan") for request in data["room_requests"]):
        from hotel_pms.revenue import quote_booking
        booking_quote = quote_booking({
            "property": data["property"], "arrival_date": data["arrival_date"], "departure_date": data["departure_date"],
            "customer": data["guest"], "voucher_code": data.get("voucher_code"),
            "travel_agent_contract": data.get("travel_agent_contract"), "room_requests": data["room_requests"],
        })

    selected_rooms: list[dict] = []
    already_selected: set[str] = set()
    nights = max((getdate(data["departure_date"]) - getdate(data["arrival_date"])).days, 1)
    for request_index, request in enumerate(data["room_requests"]):
        quantity = max(cint(request.get("quantity") or 1), 1)
        available = get_available_rooms(
            data["property"], data["arrival_date"], data["departure_date"], request.get("room_type")
        )
        available = [room for room in available if room.name not in already_selected]
        if len(available) < quantity:
            frappe.throw(
                _("Only {0} room(s) are available for room type {1}; {2} requested.").format(
                    len(available), request.get("room_type"), quantity
                )
            )
        rate = flt(request.get("nightly_rate"))
        quote_row = booking_quote["rooms"][request_index] if booking_quote else None
        if quote_row:
            rate = flt(quote_row["advertised_total"]) / nights
        if not rate:
            rate = flt(frappe.db.get_value("Hotel Room Type", request.get("room_type"), "base_rate"))
        for room in available[:quantity]:
            selected_rooms.append(
                {
                    "room_type": room.room_type,
                    "room": room.name,
                    "rate_plan": request.get("rate_plan"),
                    "nightly_rate": rate,
                    "adults": cint(request.get("adults") or 2),
                    "children": cint(request.get("children") or 0),
                }
            )
            already_selected.add(room.name)

    requested_status = data.get("status") or "Confirmed"
    if requested_status not in ("Tentative", "Confirmed"):
        frappe.throw(_("Quick booking status must be Tentative or Confirmed."))
    reservation = frappe.get_doc(
        {
            "doctype": "Hotel Reservation",
            "property": data["property"],
            "status": requested_status,
            "guest": data["guest"],
            "guest_contact": data.get("guest_contact"),
            "booked_by_contact": data.get("booked_by_contact"),
            "communication_contact": data.get("communication_contact"),
            "billing_customer": data.get("billing_customer") or data["guest"],
            "source": data.get("source") or "Direct",
            "source_reference": data.get("source_reference"),
            "idempotency_key": key,
            "arrival_date": data["arrival_date"],
            "departure_date": data["departure_date"],
            "arrival_time": data.get("arrival_time"),
            "departure_time": data.get("departure_time"),
            "adults": sum(cint(row.get("adults") or 0) * cint(row.get("quantity") or 1) for row in data["room_requests"]),
            "children": sum(cint(row.get("children") or 0) * cint(row.get("quantity") or 1) for row in data["room_requests"]),
            "cancellation_policy": data.get("cancellation_policy"),
            "required_deposit": flt(data.get("required_deposit")),
            "voucher_code": data.get("voucher_code"),
            "travel_agent_contract": data.get("travel_agent_contract"),
            "voucher_discount": booking_quote.get("voucher_discount") if booking_quote else 0,
            "quoted_room_total": booking_quote.get("advertised_total") if booking_quote else 0,
            "quoted_service_charge": booking_quote.get("service_charge") if booking_quote else 0,
            "quoted_tax": booking_quote.get("tax") if booking_quote else 0,
            "quoted_grand_total": booking_quote.get("grand_total") if booking_quote else 0,
            "travel_agent_commission": booking_quote.get("agent_commission") if booking_quote else 0,
            "rate_quote_hash": booking_quote.get("quote_hash") if booking_quote else None,
            "rooms": selected_rooms,
            "notes": data.get("notes"),
        }
    )
    try:
        reservation.insert()
        reservation.submit()
    except DuplicateEntryError:
        existing = frappe.db.get_value("Hotel Reservation", {"idempotency_key": key}, "name")
        if not existing:
            raise
        return {"reservation": existing, "already_created": True}
    return {"reservation": reservation.name, "already_created": False, "rooms": [row["room"] for row in selected_rooms]}


def _insert_change_log(
    *, reservation,
    change_type: str,
    idempotency_key: str,
    old_room: str | None = None,
    new_room: str | None = None,
    old_arrival=None,
    new_arrival=None,
    old_departure=None,
    new_departure=None,
    reason: str | None = None,
) -> str:
    existing = frappe.db.get_value("Hotel Stay Change Log", {"idempotency_key": idempotency_key}, "name")
    if existing:
        return existing
    log = frappe.get_doc(
        {
            "doctype": "Hotel Stay Change Log",
            "reservation": reservation.name,
            "property": reservation.property,
            "change_type": change_type,
            "changed_at": now_datetime(),
            "changed_by": frappe.session.user,
            "old_room": old_room,
            "new_room": new_room,
            "old_arrival_date": old_arrival,
            "new_arrival_date": new_arrival,
            "old_departure_date": old_departure,
            "new_departure_date": new_departure,
            "reason": reason,
            "idempotency_key": idempotency_key,
        }
    )
    try:
        log.insert(ignore_permissions=True)
    except DuplicateEntryError:
        return frappe.db.get_value("Hotel Stay Change Log", {"idempotency_key": idempotency_key}, "name")
    return log.name


@frappe.whitelist()
def move_room(reservation: str, old_room: str, new_room: str, reason: str, idempotency_key: str) -> dict:
    _require_front_desk_access()
    if not reason:
        frappe.throw(_("Reason is required for a room move."))
    doc = get_locked_reservation(reservation)
    doc.check_permission("write")
    if doc.status != "Checked In":
        frappe.throw(_("Only checked-in reservations can be moved."))
    key = make_sync_key("MOVE", reservation, idempotency_key)
    existing_log = frappe.db.get_value("Hotel Stay Change Log", {"idempotency_key": key}, "name")
    if existing_log:
        return {"reservation": reservation, "change_log": existing_log, "already_processed": True}
    target_rows = frappe.db.sql(
        "select property, room_type, operational_status, housekeeping_status from `tabHotel Room` where name=%s for update",
        new_room,
        as_dict=True,
    )
    target = target_rows[0] if target_rows else None
    if not target or target.property != doc.property:
        frappe.throw(_("Target room does not belong to this property."))
    if target.operational_status in ("Out of Order", "Out of Service", "Occupied"):
        frappe.throw(_("Target room is not available."))
    if target.housekeeping_status not in ("Clean", "Inspected"):
        frappe.throw(_("Target room is not ready; housekeeping status is {0}.").format(target.housekeeping_status))
    row = next((item for item in doc.rooms if item.room == old_room), None)
    if not row:
        frappe.throw(_("Room {0} is not part of this reservation.").format(old_room))
    if target.room_type != row.room_type:
        frappe.throw(_("Target room type differs from the existing room type. Use an upgrade workflow with rate approval."))
    available = {item.name for item in get_available_rooms(doc.property, nowdate(), doc.departure_date, row.room_type, doc.name)}
    if new_room not in available:
        frappe.throw(_("Target room conflicts with another stay."))

    frappe.db.set_value("Hotel Reservation Room", row.name, "room", new_room)
    set_room_status(
        old_room, operational_status="Available", housekeeping_status="Dirty",
        event_type="Room Move - Old Room Released", source_doctype="Hotel Reservation", source_name=doc.name,
        notes=reason, idempotency_key=f"move-old:{key}",
    )
    set_room_status(
        new_room, operational_status="Occupied", housekeeping_status="Inspected",
        event_type="Room Move - New Room Occupied", source_doctype="Hotel Reservation", source_name=doc.name,
        notes=reason, idempotency_key=f"move-new:{key}",
    )
    from hotel_pms.tasks import ensure_housekeeping_task
    ensure_housekeeping_task(property_name=doc.property, room=old_room, task_date=getdate(), task_type="Checkout Clean", reservation=doc.name, source="Front Office")
    log = _insert_change_log(
        reservation=doc, change_type="Room Move", idempotency_key=key, old_room=old_room, new_room=new_room, reason=reason
    )
    return {"reservation": reservation, "change_log": log, "already_processed": False}


@frappe.whitelist()
def amend_stay(
    reservation: str,
    new_arrival_date: str | None = None,
    new_departure_date: str | None = None,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    _require_front_desk_access()
    if not reason:
        frappe.throw(_("Reason is required for a stay-date amendment."))
    doc = get_locked_reservation(reservation)
    doc.check_permission("write")
    if doc.status not in ("Tentative", "Confirmed", "Checked In"):
        frappe.throw(_("This reservation cannot be amended in its current status."))
    old_arrival = getdate(doc.arrival_date)
    old_departure = getdate(doc.departure_date)
    new_arrival = getdate(new_arrival_date or old_arrival)
    new_departure = getdate(new_departure_date or old_departure)
    if new_departure <= new_arrival:
        frappe.throw(_("Departure date must be after arrival date."))
    if doc.status == "Checked In" and new_arrival != old_arrival:
        frappe.throw(_("Arrival date cannot be changed after check-in."))
    if new_arrival == old_arrival and new_departure == old_departure:
        return {"reservation": reservation, "already_processed": True}
    change_type = "Extend Stay" if new_departure > old_departure else "Early Departure"
    request_key = idempotency_key or f"{new_arrival}:{new_departure}"
    key = make_sync_key("STAY", reservation, request_key)
    existing_log = frappe.db.get_value("Hotel Stay Change Log", {"idempotency_key": key}, "name")
    if existing_log:
        return {"reservation": reservation, "change_log": existing_log, "already_processed": True}

    for row in doc.rooms:
        available = {item.name for item in get_available_rooms(doc.property, new_arrival, new_departure, row.room_type, doc.name)}
        if row.room not in available:
            frappe.throw(_("Room {0} is unavailable for the amended stay period.").format(row.room))
    frappe.db.set_value("Hotel Reservation", doc.name, {"arrival_date": new_arrival, "departure_date": new_departure})
    log = _insert_change_log(
        reservation=doc,
        change_type=change_type,
        idempotency_key=key,
        old_arrival=old_arrival,
        new_arrival=new_arrival,
        old_departure=old_departure,
        new_departure=new_departure,
        reason=reason,
    )
    return {"reservation": reservation, "change_log": log, "change_type": change_type, "already_processed": False}


def _policy_for_reservation(reservation):
    policy_name = reservation.cancellation_policy
    if not policy_name and reservation.property:
        policy_name = frappe.db.get_value("Hotel Property", reservation.property, "default_cancellation_policy")
    if not policy_name:
        policy_name = frappe.db.get_single_value("Hotel PMS Settings", "default_cancellation_policy")
    if not policy_name:
        return None
    policy = frappe.get_doc("Hotel Cancellation Policy", policy_name)
    if not policy.enabled:
        frappe.throw(_("Cancellation policy {0} is disabled.").format(policy.name))
    if policy.property and policy.property != reservation.property:
        frappe.throw(_("Cancellation policy {0} belongs to another property.").format(policy.name))
    return policy


def get_deposit_summary(reservation: str) -> dict:
    rows = frappe.get_all(
        "Payment Entry",
        filters={"docstatus": 1, "custom_hotel_reservation": reservation},
        fields=["name", "custom_hotel_transaction_type", "paid_amount", "received_amount", "unallocated_amount"],
    ) if frappe.get_meta("Payment Entry").has_field("custom_hotel_reservation") else []
    deposits = [row for row in rows if row.custom_hotel_transaction_type == "Deposit"]
    refunds = [row for row in rows if row.custom_hotel_transaction_type == "Refund"]
    received = sum(flt(row.received_amount or row.paid_amount) for row in deposits)
    refunded = sum(flt(row.paid_amount or row.received_amount) for row in refunds)
    unallocated = sum(max(flt(row.unallocated_amount), 0) for row in deposits)
    available_credit = max(unallocated - refunded, 0)
    return {
        "received": received,
        "refunded": refunded,
        "net_deposit": received - refunded,
        "available_credit": available_credit,
        "payment_entries": [row.name for row in rows],
    }


@frappe.whitelist()
def preview_cancellation(reservation: str, transaction_type: str = "Cancellation") -> dict:
    _require_front_desk_access()
    return preview_cancellation_internal(reservation, transaction_type)


def preview_cancellation_internal(reservation: str, transaction_type: str = "Cancellation") -> dict:
    doc = frappe.get_doc("Hotel Reservation", reservation)
    policy = _policy_for_reservation(doc)
    rates = [row.nightly_rate for row in doc.rooms]
    deposit = get_deposit_summary(doc.name)
    if transaction_type == "No Show":
        fee_type = policy.no_show_fee_type if policy else "First Night"
        fee_value = policy.no_show_fee_value if policy else 0
        base = stay_total(getdate(doc.arrival_date), getdate(doc.departure_date), rates)
        first_night = sum((money(rate) for rate in rates), Decimal("0"))
        fee = calculate_fee(base, fee_type, fee_value, first_night)
        refundable = max(money(deposit["net_deposit"]) - fee, money(0))
        free = False
        days_before = 0
    else:
        quote = quote_cancellation(
            arrival=getdate(doc.arrival_date),
            departure=getdate(doc.departure_date),
            nightly_rates=rates,
            reference_date=getdate(),
            free_cancellation_days=policy.free_cancellation_days if policy else 0,
            fee_type=policy.fee_type if policy else "None",
            fee_value=policy.fee_value if policy else 0,
            deposit_received=deposit["net_deposit"],
        )
        base, fee, refundable, free, days_before = (
            quote.gross_stay_amount,
            quote.fee_amount,
            quote.refundable_amount,
            quote.free_cancellation_applies,
            quote.days_before_arrival,
        )
    return {
        "reservation": doc.name,
        "transaction_type": transaction_type,
        "policy": policy.name if policy else None,
        "gross_stay_amount": float(base),
        "fee_amount": float(fee),
        "deposit_received": deposit["net_deposit"],
        "refundable_amount": float(refundable),
        "free_cancellation_applies": free,
        "days_before_arrival": days_before,
        "requires_approval_for_waiver": bool(policy and policy.require_manager_approval_for_waiver),
    }


@frappe.whitelist()
def cancel_reservation(
    reservation: str,
    reason: str,
    idempotency_key: str,
    transaction_type: str = "Cancellation",
    waive_fee: int = 0,
    waiver_reason: str | None = None,
) -> dict:
    _require_front_desk_access()
    return process_cancellation_internal(reservation, reason, idempotency_key, transaction_type, waive_fee, waiver_reason, guest_authorized=False)


def process_cancellation_internal(
    reservation: str, reason: str, idempotency_key: str, transaction_type: str = "Cancellation",
    waive_fee: int = 0, waiver_reason: str | None = None, guest_authorized: bool = False,
) -> dict:
    if transaction_type not in ("Cancellation", "No Show"):
        frappe.throw(_("Transaction type must be Cancellation or No Show."))
    if not reason:
        frappe.throw(_("A cancellation or no-show reason is required."))
    doc = get_locked_reservation(reservation)
    if guest_authorized:
        if transaction_type != "Cancellation":
            frappe.throw(_("Guest links cannot process no-shows."), frappe.PermissionError)
        # The caller must first validate a reservation-scoped guest token.
        # This internal function is intentionally not whitelisted.
        doc.flags.ignore_permissions = True
    else:
        doc.check_permission("write")
    expected = ACTIVE_CANCELLATION_STATUSES if transaction_type == "Cancellation" else ("Tentative", "Confirmed")
    if doc.status not in expected:
        if doc.status in ("Cancelled", "No Show") and doc.cancellation_document:
            return {"reservation": doc.name, "cancellation": doc.cancellation_document, "already_processed": True}
        frappe.throw(_("Reservation status {0} cannot be processed as {1}.").format(doc.status, transaction_type))
    if transaction_type == "No Show" and not _is_no_show_candidate(doc, getdate()):
        if not ({"System Manager", "Hotel Manager"} & set(frappe.get_roles())):
            frappe.throw(_("The no-show cutoff has not been reached. A Hotel Manager is required to override."))
    if cint(waive_fee) and not waiver_reason:
        frappe.throw(_("Waiver reason is required when waiving a fee."))
    preview = preview_cancellation_internal(doc.name, transaction_type)
    policy = _policy_for_reservation(doc)
    waive = cint(waive_fee)
    if waive and policy and policy.require_manager_approval_for_waiver:
        frappe.only_for(["System Manager", "Hotel Manager"])
    fee = 0 if waive else flt(preview["fee_amount"])
    key = make_sync_key("CAN", transaction_type, reservation, idempotency_key)
    existing = frappe.db.get_value("Hotel Cancellation", {"idempotency_key": key}, "name")
    if existing:
        return {"reservation": reservation, "cancellation": existing, "already_processed": True}

    cancellation = frappe.get_doc(
        {
            "doctype": "Hotel Cancellation",
            "reservation": doc.name,
            "property": doc.property,
            "transaction_type": transaction_type,
            "transaction_date": getdate(),
            "reason": reason,
            "policy": policy.name if policy else None,
            "gross_stay_amount": preview["gross_stay_amount"],
            "calculated_fee": preview["fee_amount"],
            "waived_fee": flt(preview["fee_amount"]) if waive else 0,
            "final_fee": fee,
            "deposit_received": preview["deposit_received"],
            "refund_due": max(flt(preview["deposit_received"]) - fee, 0),
            "waiver_reason": waiver_reason if waive else None,
            "approved_by": frappe.session.user if waive else None,
            "idempotency_key": key,
            "status": "Completed",
        }
    )
    cancellation.insert(ignore_permissions=True)
    _post_cancellation_fee(doc, cancellation, policy)
    new_status = "No Show" if transaction_type == "No Show" else "Cancelled"
    frappe.db.set_value(
        "Hotel Reservation",
        doc.name,
        {
            "status": new_status,
            "cancellation_document": cancellation.name,
            "cancellation_number": cancellation.name,
            "cancellation_fee": fee,
            "cancelled_at": now_datetime(),
            "no_show_processed_at": now_datetime() if transaction_type == "No Show" else None,
        },
    )
    if doc.voucher_code:
        from hotel_pms.revenue import release_voucher_for_reservation
        release_voucher_for_reservation(doc.name)
    for row in doc.rooms:
        if frappe.db.get_value("Hotel Room", row.room, "operational_status") != "Occupied":
            set_room_status(
                row.room, operational_status="Available", event_type=f"Reservation {new_status}",
                source_doctype="Hotel Cancellation", source_name=cancellation.name,
                idempotency_key=f"cancel-release:{cancellation.name}:{row.room}",
            )
    return {"reservation": doc.name, "cancellation": cancellation.name, "status": new_status, "already_processed": False}


def _post_cancellation_fee(reservation, cancellation, policy) -> None:
    if not flt(cancellation.final_fee):
        return
    fee_item = policy.fee_item if policy else frappe.db.get_single_value("Hotel PMS Settings", "default_cancellation_fee_item")
    if not fee_item:
        frappe.throw(_("Configure a cancellation fee Item before charging a cancellation or no-show fee."))
    from hotel_pms.api import _get_or_create_folio
    folio = _get_or_create_folio(reservation)
    key = make_sync_key("CHARGE", cancellation.transaction_type, cancellation.name)
    if frappe.db.exists("Hotel Folio Charge", {"idempotency_key": key}):
        return
    folio.append(
        "charges",
        {
            "posting_date": cancellation.transaction_date,
            "charge_type": "Adjustment",
            "item_code": fee_item,
            "description": f"{cancellation.transaction_type} fee - {reservation.name}",
            "qty": 1,
            "rate": cancellation.final_fee,
            "source_doctype": "Hotel Cancellation",
            "source_name": cancellation.name,
            "idempotency_key": key,
        },
    )
    folio.save(ignore_permissions=True)


@frappe.whitelist()
def ensure_guest_registration(reservation: str) -> dict:
    _require_front_desk_access()
    doc = get_locked_reservation(reservation)
    doc.check_permission("read")
    existing = frappe.db.get_value("Hotel Guest Registration", {"reservation": doc.name}, "name")
    if existing:
        return {"registration": existing, "already_created": True}
    registration = frappe.get_doc(
        {
            "doctype": "Hotel Guest Registration",
            "reservation": doc.name,
            "property": doc.property,
            "guest": doc.guest,
            "guest_contact": doc.guest_contact,
            "arrival_date": doc.arrival_date,
            "departure_date": doc.departure_date,
            "status": "Draft",
            "id_retention_mode": frappe.db.get_single_value("Hotel PMS Settings", "default_id_retention_mode") or "Verify and Discard",
            "occupants": [{
                "full_name": frappe.db.get_value("Customer", doc.guest, "customer_name") or doc.guest,
                "is_primary_guest": 1,
            }],
        }
    )
    try:
        registration.insert(ignore_permissions=True)
    except DuplicateEntryError:
        existing = frappe.db.get_value("Hotel Guest Registration", {"reservation": doc.name}, "name")
        if not existing:
            raise
        return {"registration": existing, "already_created": True}
    frappe.db.set_value("Hotel Reservation", doc.name, "registration", registration.name)
    return {"registration": registration.name, "already_created": False}


@frappe.whitelist()
def create_deposit_payment_entry(
    reservation: str,
    amount: float,
    mode_of_payment: str,
    idempotency_key: str,
    reference_no: str | None = None,
    reference_date: str | None = None,
    cashier_shift: str | None = None,
) -> dict:
    _require_front_desk_access()
    doc = get_locked_reservation(reservation)
    doc.check_permission("write")
    amount = flt(amount)
    if amount <= 0:
        frappe.throw(_("Deposit amount must be greater than zero."))
    return _create_reservation_payment_entry(
        reservation=doc,
        transaction_type="Deposit",
        amount=amount,
        mode_of_payment=mode_of_payment,
        idempotency_key=idempotency_key,
        reference_no=reference_no,
        reference_date=reference_date,
        cashier_shift=cashier_shift,
    )


@frappe.whitelist()
def create_refund_payment_entry(
    reservation: str,
    amount: float,
    mode_of_payment: str,
    idempotency_key: str,
    reference_no: str | None = None,
    reference_date: str | None = None,
    cashier_shift: str | None = None,
) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Accounts User", "Accounts Manager"])
    doc = get_locked_reservation(reservation)
    amount = flt(amount)
    summary = get_deposit_summary(reservation)
    if amount <= 0 or amount > flt(summary["net_deposit"]):
        frappe.throw(_("Refund must be greater than zero and cannot exceed the net deposit balance."))
    return _create_reservation_payment_entry(
        reservation=doc,
        transaction_type="Refund",
        amount=amount,
        mode_of_payment=mode_of_payment,
        idempotency_key=idempotency_key,
        reference_no=reference_no,
        reference_date=reference_date,
        cashier_shift=cashier_shift,
    )


def _create_reservation_payment_entry(
    *, reservation, transaction_type: str, amount: float, mode_of_payment: str,
    idempotency_key: str, reference_no: str | None, reference_date: str | None, cashier_shift: str | None = None,
) -> dict:
    base_key = make_sync_key("PE", transaction_type, reservation.name, idempotency_key)
    payload = {"reservation": reservation.name, "type": transaction_type, "amount": amount, "mode": mode_of_payment, "cashier_shift": cashier_shift}

    def build():
        from erpnext.accounts.party import get_party_account
        party = reservation.billing_customer or reservation.guest
        party_account = get_party_account("Customer", party, reservation.company)
        bank_account = frappe.db.get_value(
            "Mode of Payment Account",
            {"parent": mode_of_payment, "company": reservation.company},
            "default_account",
        )
        if not bank_account:
            frappe.throw(_("Mode of Payment {0} has no default account for company {1}.").format(mode_of_payment, reservation.company))
        payment = frappe.new_doc("Payment Entry")
        payment.payment_type = "Receive" if transaction_type == "Deposit" else "Pay"
        payment.company = reservation.company
        payment.posting_date = getdate()
        payment.mode_of_payment = mode_of_payment
        payment.party_type = "Customer"
        payment.party = party
        payment.party_name = frappe.db.get_value("Customer", party, "customer_name")
        payment.paid_from = party_account if transaction_type == "Deposit" else bank_account
        payment.paid_to = bank_account if transaction_type == "Deposit" else party_account
        payment.paid_amount = amount
        payment.received_amount = amount
        payment.reference_no = reference_no
        payment.reference_date = getdate(reference_date) if reference_date else getdate()
        payment.remarks = f"Hotel {transaction_type.lower()} for reservation {reservation.name}"
        if payment.meta.has_field("custom_hotel_reservation"):
            payment.custom_hotel_reservation = reservation.name
        if payment.meta.has_field("custom_hotel_transaction_type"):
            payment.custom_hotel_transaction_type = transaction_type
        if payment.meta.has_field("custom_hotel_cashier_shift"):
            payment.custom_hotel_cashier_shift = cashier_shift or frappe.db.get_value("Hotel Cashier Shift", {"property": reservation.property, "cashier": frappe.session.user, "status": "Open"}, "name")
        return payment

    payment, already_created = create_document_once(
        base_key=base_key,
        operation=f"Create Hotel {transaction_type} Payment Entry",
        source_doctype=reservation.doctype,
        source_name=reservation.name,
        target_doctype="Payment Entry",
        build_document=build,
        payload=payload,
    )
    _refresh_deposit_totals(reservation.name)
    return {"payment_entry": payment.name, "already_created": already_created, "docstatus": payment.docstatus}


def _refresh_deposit_totals(reservation: str) -> None:
    summary = get_deposit_summary(reservation)
    frappe.db.set_value(
        "Hotel Reservation",
        reservation,
        {"deposit_received": summary["received"], "deposit_refunded": summary["refunded"]},
        update_modified=False,
    )


def on_payment_entry_change(doc, method=None) -> None:
    reservation = getattr(doc, "custom_hotel_reservation", None)
    if reservation:
        _refresh_deposit_totals(reservation)


def process_no_show_candidates() -> dict:
    if not cint(frappe.db.get_single_value("Hotel PMS Settings", "auto_process_no_shows") or 0):
        return {"processed": 0, "disabled": True}
    processed = 0
    errors = []
    properties = frappe.get_all("Hotel Property", filters={"enabled": 1}, pluck="name")
    for property_name in properties:
        dashboard = get_today_dashboard(property_name, nowdate())
        for row in dashboard["no_show_candidates"]:
            try:
                cancel_reservation(
                    reservation=row.name,
                    reason="Automatically processed after no-show cutoff",
                    idempotency_key=f"AUTO-{nowdate()}",
                    transaction_type="No Show",
                )
                processed += 1
            except Exception as exc:
                errors.append({"reservation": row.name, "error": str(exc)})
                frappe.log_error(frappe.get_traceback(), f"Hotel no-show processing failed: {row.name}")
    return {"processed": processed, "errors": errors}
