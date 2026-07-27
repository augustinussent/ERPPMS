from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import socket
from datetime import timedelta
from decimal import Decimal
from html import escape

import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError, RateLimitExceededError
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate

from hotel_pms.channels import AdapterNotCertified, provider_for
from hotel_pms.distribution_rules import (
    canonical_date,
    dedupe_ical_events,
    echo_key,
    event_key,
    is_generic_ical_summary,
    json_hash,
    normalized_guest_label,
    parse_ical_events,
    recommend_room,
    room_rate_per_night,
    stable_hash,
    strict_overlap,
    turnover_window_minutes,
    validate_outbound_url,
)
from hotel_pms.platform import require_property
from hotel_pms.sync import make_sync_key

MAX_ICAL_BYTES = 2 * 1024 * 1024
ACTIVE_EVENT_STATUSES = ("Pending", "Processed", "Needs Review", "Echo")


def _require_distribution_role() -> None:
    frappe.only_for(["System Manager", "Hotel Manager", "Revenue Manager", "Front Desk"])


def _connection(name: str, *, write: bool = False):
    doc = frappe.get_doc("Hotel Distribution Connection", name)
    require_property(doc.property, write=write)
    return doc


def _mapping_for_external(connection: str, external_room_id: str):
    name = frappe.db.get_value(
        "Hotel Distribution Room Mapping",
        {"connection": connection, "external_room_id": external_room_id, "enabled": 1},
        "name",
    )
    return frappe.get_doc("Hotel Distribution Room Mapping", name) if name else None


def _mapping_rows(connection: str) -> list[dict]:
    return frappe.get_all(
        "Hotel Distribution Room Mapping",
        filters={"connection": connection, "enabled": 1},
        fields=[
            "name", "property", "mapping_mode", "room", "room_type", "rate_plan",
            "external_room_id", "external_rate_id", "incoming_price_basis",
        ],
        order_by="room_type asc, room asc",
    )


def _resolve_public_ips(hostname: str) -> list[str]:
    try:
        return sorted({row[4][0] for row in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)})
    except socket.gaierror as exc:
        raise ValueError("Calendar host could not be resolved.") from exc


def _fetch_ical(url: str) -> str:
    import requests
    from urllib.parse import urlparse

    parsed = urlparse(url)
    safe_url = validate_outbound_url(url, _resolve_public_ips(parsed.hostname or ""))
    response = requests.get(
        safe_url,
        headers={"Accept": "text/calendar, text/plain;q=0.9", "User-Agent": "HotelPMS-iCal/1.0"},
        timeout=(5, 15),
        allow_redirects=False,
        stream=True,
    )
    if 300 <= response.status_code < 400:
        raise ValueError("Calendar redirects are blocked; save the final HTTPS URL explicitly.")
    response.raise_for_status()
    content_type = (response.headers.get("Content-Type") or "").lower()
    if content_type and "calendar" not in content_type and "text/plain" not in content_type:
        raise ValueError("Calendar endpoint returned an unsupported content type.")
    chunks, total = [], 0
    for chunk in response.iter_content(65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_ICAL_BYTES:
            raise ValueError("Calendar feed exceeds the 2 MiB safety limit.")
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _set_connection_result(connection, kind: str, ok: bool, detail: str) -> None:
    now = now_datetime()
    updates = {
        f"last_{kind}_at": now,
        f"last_{kind}_status": ("OK: " if ok else "FAILED: ") + str(detail)[:130],
        "last_error": "" if ok else str(detail)[:1000],
        "failure_count": 0 if ok else cint(connection.failure_count) + 1,
    }
    if kind == "test":
        updates["status"] = connection.status if ok and connection.status in ("Ready", "Live") else ("Tested" if ok else "Failed")
    frappe.db.set_value("Hotel Distribution Connection", connection.name, updates, update_modified=False)


@frappe.whitelist()
def rotate_feed_token(connection: str) -> dict:
    _require_distribution_role()
    doc = _connection(connection, write=True)
    raw = secrets.token_urlsafe(32)
    frappe.db.set_value(
        "Hotel Distribution Connection", doc.name,
        {"feed_token_hash": hashlib.sha256(raw.encode()).hexdigest()},
        update_modified=False,
    )
    return {"connection": doc.name, "feed_slug": doc.feed_slug, "raw_token": raw, "url": _feed_url(doc, raw)}


def _feed_url(connection, raw_token: str | None = None) -> str:
    base = frappe.utils.get_url(f"/api/method/hotel_pms.distribution.public_ical_feed?slug={connection.feed_slug}")
    return f"{base}&token={raw_token}" if raw_token else base


@frappe.whitelist()
def test_connection(connection: str) -> dict:
    _require_distribution_role()
    doc = _connection(connection, write=True)
    try:
        if doc.provider == "Generic iCal":
            text = _fetch_ical(doc.get_password("endpoint"))
            count = len(dedupe_ical_events(parse_ical_events(text)))
            detail = f"valid iCal feed; {count} event(s)"
            result = {"ok": True, "detail": detail, "events": count}
        else:
            if doc.provider == "Generic JSON":
                if not doc.get_password("webhook_secret", raise_exception=False):
                    raise ValueError("A webhook HMAC secret is required.")
                if not _mapping_rows(doc.name):
                    raise ValueError("At least one enabled room mapping is required.")
            result = provider_for(doc.provider).test_connection(doc)
            if not result.get("ok"):
                raise ValueError(result.get("detail") or "Provider test failed.")
            detail = result.get("detail") or "connection passed"
        _set_connection_result(doc, "test", True, detail)
        return result
    except Exception as exc:
        _set_connection_result(doc, "test", False, str(exc))
        raise


def _upsert_calendar_event(connection, mapping, event: dict) -> tuple[str, bool]:
    key = event_key(connection.name, event["uid"], event["start_date"], event["end_date"])
    echo = echo_key(connection.property, mapping.room or mapping.room_type, event["start_date"], event["end_date"])
    existing = frappe.db.get_value("Hotel Distribution Event", {"idempotency_key": key}, "name")
    values = {
        "property": connection.property,
        "connection": connection.name,
        "direction": "Inbound",
        "event_type": "Calendar Block",
        "status": "Processed",
        "external_reference": event["uid"],
        "idempotency_key": key,
        "echo_key": echo,
        "room": mapping.room,
        "room_type": mapping.room_type,
        "arrival_date": event["start_date"],
        "departure_date": event["end_date"],
        "summary": normalized_guest_label(event.get("summary"), connection.external_property_id or connection.provider),
        "payload_hash": json_hash(event),
        "payload_json": json.dumps(event, sort_keys=True),
        "received_at": now_datetime(),
        "processed_at": now_datetime(),
        "error": "",
    }
    if existing:
        frappe.db.set_value("Hotel Distribution Event", existing, values, update_modified=False)
        return existing, True
    try:
        doc = frappe.get_doc({"doctype": "Hotel Distribution Event", "naming_series": "HDE-.YYYY.-.#####", **values})
        doc.insert(ignore_permissions=True)
        return doc.name, False
    except DuplicateEntryError:
        return frappe.db.get_value("Hotel Distribution Event", {"idempotency_key": key}, "name"), True


@frappe.whitelist()
def sync_ical_connection(connection: str) -> dict:
    _require_distribution_role()
    return _sync_ical_connection(connection)


def _sync_ical_connection(connection: str) -> dict:
    doc = frappe.get_doc("Hotel Distribution Connection", connection)
    if not doc.enabled or doc.provider != "Generic iCal":
        return {"connection": doc.name, "skipped": True, "reason": "not an enabled Generic iCal connection"}
    mappings = _mapping_rows(doc.name)
    if len(mappings) != 1 or mappings[0].mapping_mode != "Room" or not mappings[0].room:
        raise ValueError("Generic iCal requires exactly one enabled Exact Room mapping.")
    mapping = frappe._dict(mappings[0])
    try:
        events = dedupe_ical_events(parse_ical_events(_fetch_ical(doc.get_password("endpoint"))))
        cutoff = getdate(add_days(nowdate(), max(cint(doc.sync_days or 365), 1)))
        today = getdate()
        events = [e for e in events if getdate(e["end_date"]) >= today and getdate(e["start_date"]) < cutoff]
        seen = set()
        created = updated = 0
        for event in events:
            name, existed = _upsert_calendar_event(doc, mapping, event)
            seen.add(name)
            updated += int(existed); created += int(not existed)
        active = frappe.get_all(
            "Hotel Distribution Event",
            filters={"connection": doc.name, "event_type": "Calendar Block", "status": ("in", ACTIVE_EVENT_STATUSES)},
            pluck="name",
        )
        for name in active:
            if name not in seen:
                frappe.db.set_value("Hotel Distribution Event", name, {"status": "Cancelled", "processed_at": now_datetime()}, update_modified=False)
        detail = f"{len(events)} active event(s), {created} created, {updated} updated"
        _set_connection_result(doc, "sync", True, detail)
        return {"connection": doc.name, "events": len(events), "created": created, "updated": updated, "cancelled": len(set(active) - seen)}
    except Exception as exc:
        _set_connection_result(doc, "sync", False, str(exc))
        raise


def sync_all_ical_connections() -> None:
    now = now_datetime()
    rows = frappe.get_all(
        "Hotel Distribution Connection",
        filters={"enabled": 1, "provider": "Generic iCal"},
        fields=["name", "last_sync_at", "sync_interval_minutes"],
    )
    for row in rows:
        interval = max(cint(row.sync_interval_minutes or 15), 5)
        if row.last_sync_at:
            elapsed = (now - get_datetime(row.last_sync_at)).total_seconds()
            if elapsed < interval * 60:
                continue
        try:
            _sync_ical_connection(row.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"iCal distribution sync failed: {row.name}")


def _external_room_conflicts(property_name: str, arrival, departure, *, exclude_connection: str | None = None) -> set[str]:
    filters = {
        "property": property_name,
        "event_type": "Calendar Block",
        "status": ("in", ACTIVE_EVENT_STATUSES),
        "arrival_date": ("<", getdate(departure)),
        "departure_date": (">", getdate(arrival)),
        "room": ("is", "set"),
    }
    rows = frappe.get_all("Hotel Distribution Event", filters=filters, fields=["room", "connection"])
    return {row.room for row in rows if not exclude_connection or row.connection != exclude_connection}


def available_rooms_with_distribution(property_name: str, room_type: str, arrival, departure, *, exclude_reservation: str | None = None) -> list[dict]:
    # Internal availability path: no session-role gate, because authenticated
    # provider webhooks must use the same inventory engine as the Front Desk.
    rooms = frappe.get_all(
        "Hotel Room",
        filters={"property": property_name, "room_type": room_type, "enabled": 1, "operational_status": ("not in", ["Out of Order", "Out of Service"])},
        fields=["name", "room_number", "room_type", "floor", "operational_status", "housekeeping_status"],
        order_by="room_number asc",
    )
    conflicts = set(frappe.db.sql_list(
        """select distinct rr.room from `tabHotel Reservation` r
        inner join `tabHotel Reservation Room` rr on rr.parent=r.name
        where r.property=%(property)s and rr.room_type=%(room_type)s and r.docstatus < 2
          and r.status in ('Tentative','Confirmed','Checked In')
          and r.arrival_date < %(departure)s and r.departure_date > %(arrival)s
          and r.name != %(exclude)s""",
        {"property": property_name, "room_type": room_type, "arrival": getdate(arrival), "departure": getdate(departure), "exclude": exclude_reservation or ""},
    ))
    conflicts.update(_external_room_conflicts(property_name, arrival, departure))
    physically_free = [row for row in rooms if row.name not in conflicts]
    from hotel_pms.hotel_pms.doctype.hotel_group_booking.hotel_group_booking import get_available_room_type_capacity
    capacity = max(cint(get_available_room_type_capacity(property_name, room_type, arrival, departure, exclude_reservation=exclude_reservation)), 0)
    return physically_free[:capacity]


def distribution_room_type_hold(property_name: str, room_type: str, arrival, departure) -> int:
    rows = frappe.db.sql(
        """
        select count(distinct echo_key)
        from `tabHotel Distribution Event`
        where property=%(property)s and room_type=%(room_type)s
          and coalesce(room,'')='' and event_type='Calendar Block'
          and status in ('Pending','Processed','Needs Review','Echo')
          and arrival_date < %(departure)s and departure_date > %(arrival)s
        """,
        {"property": property_name, "room_type": room_type, "arrival": getdate(arrival), "departure": getdate(departure)},
    )
    return cint(rows[0][0] if rows else 0)


def _ari_snapshot(connection) -> list[dict]:
    from hotel_pms.guest_portal import _available_rooms
    from hotel_pms.revenue import _quote_stay_core

    output = []
    for mapping in _mapping_rows(connection.name):
        if mapping.mapping_mode != "Room Type":
            continue
        days = []
        for offset in range(max(cint(connection.sync_days or 90), 1)):
            start = getdate(add_days(nowdate(), offset)); end = getdate(add_days(start, 1))
            available = len(_available_rooms(connection.property, mapping.room_type, start, end))
            rate = None
            if mapping.rate_plan:
                try:
                    quote = _quote_stay_core(
                        property=connection.property, room_type=mapping.room_type, rate_plan=mapping.rate_plan,
                        arrival_date=str(start), departure_date=str(end), adults=2, children=0, voucher_code=None,
                    )
                    rate = flt(quote.get("advertised_total"))
                except Exception:
                    rate = None
            days.append({"date": str(start), "available": max(available, 0), "rate": rate})
        output.append({
            "room_type": mapping.room_type,
            "external_room_id": mapping.external_room_id,
            "external_rate_id": mapping.external_rate_id,
            "days": days,
        })
    return output


@frappe.whitelist()
def ari_snapshot(connection: str) -> list[dict]:
    _require_distribution_role()
    doc = _connection(connection)
    return _ari_snapshot(doc)


@frappe.whitelist()
def push_ari(connection: str) -> dict:
    _require_distribution_role()
    doc = _connection(connection, write=True)
    if not doc.enabled or not doc.outbound_ari_enabled:
        frappe.throw(_("Enable this connection and Outbound ARI before pushing."))
    try:
        snapshot = _ari_snapshot(doc)
        if not snapshot:
            frappe.throw(_("No enabled Room Type mappings are configured."))
        result = provider_for(doc.provider).push_ari(doc, snapshot)
        if not result.get("ok"):
            raise ValueError(result.get("detail") or "ARI push failed.")
        _set_connection_result(doc, "push", True, result.get("detail") or "ARI pushed")
        _record_event(doc, "Outbound", "ARI Push", stable_hash("ARI", doc.name, now_datetime()), "Processed", result)
        return result
    except Exception as exc:
        _set_connection_result(doc, "push", False, str(exc))
        raise


def push_all_ari() -> None:
    for name in frappe.get_all(
        "Hotel Distribution Connection",
        filters={"enabled": 1, "outbound_ari_enabled": 1, "status": ("in", ["Ready", "Live"])},
        pluck="name",
    ):
        try:
            push_ari(name)
        except AdapterNotCertified:
            pass
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Distribution ARI push failed: {name}")


def _record_event(connection, direction: str, event_type: str, external_reference: str, status: str, payload: dict, **extra):
    key = make_sync_key("DIST", connection.name, direction, event_type, external_reference)
    existing = frappe.db.get_value("Hotel Distribution Event", {"idempotency_key": key}, "name")
    values = {
        "property": connection.property, "connection": connection.name, "direction": direction,
        "event_type": event_type, "status": status, "external_reference": external_reference,
        "idempotency_key": key, "payload_hash": json_hash(payload),
        "payload_json": json.dumps(payload, sort_keys=True, default=str), "received_at": now_datetime(), **extra,
    }
    if existing:
        return frappe.get_doc("Hotel Distribution Event", existing), True
    doc = frappe.get_doc({"doctype": "Hotel Distribution Event", "naming_series": "HDE-.YYYY.-.#####", **values})
    doc.insert(ignore_permissions=True)
    return doc, False


def _normalize_booking_event(raw: dict) -> dict:
    event_type = str(raw.get("event") or raw.get("event_type") or "book").lower().strip()
    aliases = {"created": "book", "new": "book", "modified": "modify", "updated": "modify", "cancelled": "cancel", "canceled": "cancel"}
    event_type = aliases.get(event_type, event_type)
    if event_type not in ("book", "modify", "cancel"):
        raise ValueError("Unsupported distribution event type.")
    reference = str(raw.get("external_reference") or raw.get("ota_ref") or raw.get("booking_id") or "").strip()
    if not reference:
        raise ValueError("External booking reference is required.")
    output = {
        "event": event_type,
        "external_reference": reference[:140],
        "external_room_id": str(raw.get("external_room_id") or raw.get("room_type_external_id") or "").strip(),
        "arrival_date": canonical_date(raw.get("arrival_date") or raw.get("check_in")) if event_type != "cancel" else None,
        "departure_date": canonical_date(raw.get("departure_date") or raw.get("check_out")) if event_type != "cancel" else None,
        "guest_name": str(raw.get("guest_name") or "OTA Guest").strip()[:140],
        "email": str(raw.get("email") or "").strip()[:180],
        "phone": str(raw.get("phone") or "").strip()[:50],
        "adults": max(cint(raw.get("adults") or 1), 1),
        "children": max(cint(raw.get("children") or 0), 0),
        "room_rate_total": raw.get("room_rate_total"),
        "gross_total": raw.get("gross_total") or raw.get("total"),
        "currency": str(raw.get("currency") or "").strip()[:10],
        "channel": str(raw.get("channel") or raw.get("source") or "OTA").strip()[:80],
        "notes": str(raw.get("notes") or raw.get("special_requests") or "").strip()[:1000],
    }
    if event_type != "cancel" and (not output["external_room_id"] or output["departure_date"] <= output["arrival_date"]):
        raise ValueError("Valid external room and stay dates are required.")
    return output


def _verify_webhook_signature(connection, supplied: str | None, body: bytes) -> None:
    secret = connection.get_password("webhook_secret", raise_exception=False) or ""
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest() if secret else ""
    if not expected or not supplied or not hmac.compare_digest(expected, str(supplied)):
        frappe.throw(_("Distribution webhook HMAC signature failed."), frappe.PermissionError)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def distribution_webhook(connection: str):
    doc = frappe.get_doc("Hotel Distribution Connection", connection)
    if not doc.enabled or not doc.inbound_enabled:
        return {"ok": False, "reason": "connection_inactive"}
    raw_body = getattr(frappe.request, "data", b"{}") if getattr(frappe, "request", None) else b"{}"
    supplied = frappe.get_request_header("X-Hotel-Distribution-Signature") if getattr(frappe, "request", None) else None
    _verify_webhook_signature(doc, supplied, raw_body)
    if len(raw_body) > 512 * 1024:
        frappe.throw(_("Distribution payload exceeds the 512 KiB limit."))
    payload = json.loads(raw_body or b"{}")
    results = []
    for raw in provider_for(doc.provider).parse_webhook(doc, payload):
        results.append(_apply_booking_event(doc, _normalize_booking_event(raw), raw))
    return {"ok": True, "results": results}


def _apply_booking_event(connection, event: dict, raw_payload: dict) -> dict:
    event_doc, existed = _record_event(
        connection, "Inbound", {"book": "Booking", "modify": "Modification", "cancel": "Cancellation"}[event["event"]],
        event["external_reference"], "Pending", raw_payload,
    )
    if existed and event_doc.status in ("Processed", "Ignored Duplicate", "Cancelled"):
        return {"external_reference": event["external_reference"], "result": "duplicate_ignored", "reservation": event_doc.reservation}
    reservation_name = frappe.db.get_value(
        "Hotel Reservation",
        {"property": connection.property, "distribution_connection": connection.name, "external_reference": event["external_reference"], "docstatus": ("<", 2)},
        "name",
    )
    try:
        if event["event"] == "cancel":
            if not reservation_name:
                event_doc.db_set({"status": "Needs Review", "error": "Cancellation did not match an active reservation", "processed_at": now_datetime()})
                return {"external_reference": event["external_reference"], "result": "cancel_unmatched"}
            from hotel_pms.front_desk import process_cancellation_internal
            result = process_cancellation_internal(
                reservation_name,
                f"Cancelled by {event.get('channel') or connection.provider} ({event['external_reference']})",
                f"distribution-cancel:{connection.name}:{event['external_reference']}",
                transaction_type="Cancellation", waive_fee=0, guest_authorized=False, authorized_source="Distribution",
            )
            event_doc.db_set({"status": "Cancelled", "reservation": reservation_name, "processed_at": now_datetime(), "error": ""})
            return {"external_reference": event["external_reference"], "result": "cancelled", "reservation": reservation_name, "cancellation": result.get("cancellation")}
        if event["event"] == "modify":
            event_doc.db_set({"status": "Needs Review", "reservation": reservation_name, "processed_at": now_datetime(), "error": "OTA modification requires Front Desk review before inventory/rate amendment."})
            return {"external_reference": event["external_reference"], "result": "modification_needs_review", "reservation": reservation_name}
        if reservation_name:
            event_doc.db_set({"status": "Ignored Duplicate", "reservation": reservation_name, "processed_at": now_datetime(), "error": ""})
            return {"external_reference": event["external_reference"], "result": "duplicate_ignored", "reservation": reservation_name}
        mapping = _mapping_for_external(connection.name, event["external_room_id"])
        if not mapping:
            event_doc.db_set({"status": "Needs Review", "processed_at": now_datetime(), "error": "External room is not mapped."})
            return {"external_reference": event["external_reference"], "result": "unmapped_room"}
        if mapping.incoming_price_basis != "Room Rate Total" or event.get("room_rate_total") in (None, ""):
            event_doc.db_set({"status": "Needs Review", "processed_at": now_datetime(), "error": "Room-rate total is required and mapping price basis must be Room Rate Total."})
            return {"external_reference": event["external_reference"], "result": "price_needs_review"}
        available = available_rooms_with_distribution(connection.property, mapping.room_type, event["arrival_date"], event["departure_date"])
        if mapping.mapping_mode == "Room":
            available = [row for row in available if row.name == mapping.room]
        if not available:
            event_doc.db_set({"status": "Needs Review", "processed_at": now_datetime(), "error": "No sellable room is available for the inbound stay."})
            return {"external_reference": event["external_reference"], "result": "no_availability"}
        company = frappe.db.get_value("Hotel Property", connection.property, "company")
        company_currency = frappe.db.get_value("Company", company, "default_currency") if company else None
        external_currency = (event.get("currency") or company_currency or "").upper()
        if company_currency and external_currency and external_currency != str(company_currency).upper():
            event_doc.db_set({
                "status": "Needs Review",
                "processed_at": now_datetime(),
                "error": f"External currency {external_currency} differs from property currency {company_currency}; conversion/repricing requires Finance review.",
            })
            return {
                "external_reference": event["external_reference"],
                "result": "currency_needs_review",
                "external_currency": external_currency,
                "property_currency": company_currency,
            }
        from hotel_pms.guest_portal import resolve_or_create_guest
        guest = resolve_or_create_guest(event["guest_name"], event.get("email"), event.get("phone"))
        nightly = room_rate_per_night(event["room_rate_total"], event["arrival_date"], event["departure_date"])
        room = available[0]
        reservation = frappe.get_doc({
            "doctype": "Hotel Reservation",
            "property": connection.property,
            "status": "Confirmed",
            "guest": guest["customer"],
            "guest_contact": guest["contact"],
            "communication_contact": guest["contact"],
            "billing_customer": guest["customer"],
            "guest_profile": guest["profile"],
            "source": "OTA",
            "source_reference": event["external_reference"],
            "idempotency_key": make_sync_key("RES", "DIST", connection.name, event["external_reference"]),
            "arrival_date": event["arrival_date"],
            "departure_date": event["departure_date"],
            "adults": event["adults"],
            "children": event["children"],
            "distribution_connection": connection.name,
            "external_reference": event["external_reference"],
            "external_event": event_doc.name,
            "external_sell_price_locked": 1,
            "external_room_rate_total": float(Decimal(str(event["room_rate_total"]))),
            "external_gross_total": flt(event.get("gross_total")),
            "external_currency": external_currency,
            "distribution_price_status": "Approved",
            "quoted_room_total": float(Decimal(str(event["room_rate_total"]))),
            "quoted_grand_total": flt(event.get("gross_total") or event["room_rate_total"]),
            "notes": escape(event.get("notes") or ""),
            "rooms": [{
                "room": room.name, "room_type": mapping.room_type, "rate_plan": mapping.rate_plan,
                "nightly_rate": float(nightly), "quoted_stay_total": float(Decimal(str(event["room_rate_total"]))),
                "adults": event["adults"], "children": event["children"],
            }],
        })
        reservation.insert(ignore_permissions=True)
        reservation.submit()
        event_doc.db_set({"status": "Processed", "reservation": reservation.name, "room": room.name, "room_type": mapping.room_type, "arrival_date": event["arrival_date"], "departure_date": event["departure_date"], "processed_at": now_datetime(), "error": ""})
        try:
            provider_for(connection.provider).acknowledge_booking(connection, event, reservation.name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Distribution acknowledgement failed: {event_doc.name}")
        frappe.enqueue("hotel_pms.distribution.push_all_ari", queue="long", enqueue_after_commit=True)
        return {"external_reference": event["external_reference"], "result": "booked", "reservation": reservation.name}
    except Exception as exc:
        event_doc.db_set({"status": "Failed", "processed_at": now_datetime(), "error": str(exc)[:1000]})
        raise


@frappe.whitelist()
def get_checkin_context(reservation: str) -> dict:
    _require_distribution_role()
    doc = frappe.get_doc("Hotel Reservation", reservation)
    require_property(doc.property)
    registration = frappe.db.get_value(
        "Hotel Guest Registration", doc.registration,
        ["name", "status", "primary_id_number", "id_file", "address_proof_file"], as_dict=True,
    ) if doc.registration else None
    profile = frappe.db.get_value(
        "Hotel Guest Profile", doc.guest_profile,
        ["preferred_floor", "preferred_room_type", "allergies", "accessibility_notes"], as_dict=True,
    ) if doc.guest_profile else None
    rooms = []
    for row in doc.rooms:
        details = frappe.db.get_value(
            "Hotel Room", row.room,
            ["name", "room_number", "room_type", "floor", "operational_status", "housekeeping_status"], as_dict=True,
        )
        if details:
            rooms.append(details)
    alternatives = []
    room_type = doc.rooms[0].room_type if doc.rooms else None
    if room_type:
        alternatives = available_rooms_with_distribution(doc.property, room_type, doc.arrival_date, doc.departure_date, exclude_reservation=doc.name)
    suggestion = recommend_room(alternatives, (profile or {}).get("preferred_floor"))
    return {
        "reservation": {"name": doc.name, "guest": doc.guest, "status": doc.status, "arrival_date": str(doc.arrival_date), "departure_date": str(doc.departure_date)},
        "readiness": {
            "registration_status": (registration or {}).get("status") or "Not Started",
            "id_on_file": bool((registration or {}).get("id_file") or (registration or {}).get("primary_id_number")),
            "address_on_file": bool((registration or {}).get("address_proof_file")),
            "prearrival_status": frappe.db.get_value("Hotel Prearrival Form Submission", {"reservation": doc.name}, "status") or "Not Issued",
            "allergies": (profile or {}).get("allergies") or "",
            "accessibility_notes": (profile or {}).get("accessibility_notes") or "",
        },
        "assigned_rooms": rooms,
        "suggestion": suggestion,
        "available_rooms": alternatives,
        "blocking_rules": {
            "verified_registration_required": bool(cint(frappe.db.get_single_value("Hotel PMS Settings", "require_verified_registration_before_check_in"))),
            "room_must_be_clean_or_inspected": True,
        },
    }


@frappe.whitelist()
def get_distribution_dashboard(property: str) -> dict:
    _require_distribution_role(); require_property(property)
    connections = frappe.get_all(
        "Hotel Distribution Connection", filters={"property": property},
        fields=["name", "provider", "maturity_status", "enabled", "status", "last_test_status", "last_sync_status", "last_push_status", "failure_count"],
        order_by="modified desc",
    )
    review_events = frappe.get_all(
        "Hotel Distribution Event", filters={"property": property, "status": ("in", ["Needs Review", "Failed"])},
        fields=["name", "connection", "event_type", "external_reference", "summary", "arrival_date", "departure_date", "status", "error"],
        order_by="modified desc", limit=50,
    )
    conflicts = detect_distribution_conflicts(property)
    return {"connections": connections, "review_events": review_events, "conflicts": conflicts}


@frappe.whitelist()
def detect_distribution_conflicts(property: str) -> list[dict]:
    require_property(property)
    rows = frappe.get_all(
        "Hotel Distribution Event",
        filters={"property": property, "event_type": "Calendar Block", "status": ("in", ACTIVE_EVENT_STATUSES), "departure_date": (">=", nowdate())},
        fields=["name", "connection", "room", "room_type", "arrival_date", "departure_date", "summary", "external_reference", "echo_key"],
        order_by="room asc, room_type asc, arrival_date asc",
    )
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if (a.room or a.room_type) != (b.room or b.room_type):
                continue
            if not strict_overlap(a.arrival_date, a.departure_date, b.arrival_date, b.departure_date):
                continue
            exact = a.arrival_date == b.arrival_date and a.departure_date == b.departure_date
            generic_echo = exact and is_generic_ical_summary(a.summary) and is_generic_ical_summary(b.summary)
            out.append({
                "a": a.name, "b": b.name, "room": a.room, "room_type": a.room_type,
                "arrival_date": str(max(getdate(a.arrival_date), getdate(b.arrival_date))),
                "departure_date": str(min(getdate(a.departure_date), getdate(b.departure_date))),
                "classification": "Likely Echo" if generic_echo else "Possible Double Booking",
            })
    return out


def _ical_escape(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ical_date(value) -> str:
    return getdate(value).strftime("%Y%m%d")


def _feed_events(connection, mapping) -> list[dict]:
    events = []
    reservations = frappe.db.sql(
        """
        select distinct r.name, r.arrival_date, r.departure_date
        from `tabHotel Reservation` r
        inner join `tabHotel Reservation Room` rr on rr.parent=r.name
        where r.property=%(property)s and rr.room=%(room)s and r.docstatus < 2
          and r.status in ('Tentative','Confirmed','Checked In') and r.departure_date >= %(today)s
        """,
        {"property": connection.property, "room": mapping.room, "today": nowdate()}, as_dict=True,
    )
    for row in reservations:
        events.append({"uid": f"hotel-reservation-{row.name}@hotel-pms", "start_date": str(row.arrival_date), "end_date": str(row.departure_date), "summary": "Blocked"})
    external = frappe.get_all(
        "Hotel Distribution Event",
        filters={"property": connection.property, "room": mapping.room, "connection": ("!=", connection.name), "event_type": "Calendar Block", "status": ("in", ACTIVE_EVENT_STATUSES), "departure_date": (">=", nowdate())},
        fields=["name", "arrival_date", "departure_date"],
    )
    for row in external:
        events.append({"uid": f"hotel-distribution-{row.name}@hotel-pms", "start_date": str(row.arrival_date), "end_date": str(row.departure_date), "summary": "Blocked"})
    buffered = []
    for event in events:
        start = add_days(event["start_date"], -max(cint(connection.buffer_before), 0))
        end = add_days(event["end_date"], max(cint(connection.buffer_after), 0))
        buffered.append({**event, "start_date": str(start), "end_date": str(end)})
    unique = {}
    for event in buffered:
        unique[(event["start_date"], event["end_date"])] = event
    return sorted(unique.values(), key=lambda e: (e["start_date"], e["end_date"]))



def _enforce_public_feed_rate_limit(slug: str, *, limit: int = 120, window_seconds: int = 60) -> None:
    request_ip = getattr(frappe.local, "request_ip", None) or "unknown"
    bucket = int(now_datetime().timestamp()) // window_seconds
    key = f"hotel-pms:ical-feed:{request_ip}:{bucket}"
    cache = frappe.cache()
    try:
        count = cint(cache.incr(key))
        if count == 1:
            cache.expire(key, window_seconds + 5)
    except Exception:
        # A cache outage must not publish private data or crash a feed already
        # protected by a high-entropy token. It is logged for operations review.
        frappe.log_error(frappe.get_traceback(), "Public iCal rate-limit cache failure")
        return
    if count > limit:
        frappe.throw(_("Calendar feed rate limit exceeded. Retry shortly."), RateLimitExceededError)

@frappe.whitelist(allow_guest=True)
def public_ical_feed(slug: str, token: str | None = None):
    _enforce_public_feed_rate_limit(slug)
    name = frappe.db.get_value("Hotel Distribution Connection", {"feed_slug": slug, "enabled": 1}, "name")
    if not name:
        frappe.throw(_("Feed not found."), frappe.DoesNotExistError)
    connection = frappe.get_doc("Hotel Distribution Connection", name)
    expected = connection.feed_token_hash or ""
    supplied = hashlib.sha256((token or "").encode()).hexdigest()
    if not expected or not hmac.compare_digest(expected, supplied):
        frappe.throw(_("Feed token is invalid."), frappe.PermissionError)
    mappings = _mapping_rows(connection.name)
    if len(mappings) != 1 or mappings[0].mapping_mode != "Room" or not mappings[0].room:
        frappe.throw(_("Feed requires exactly one Exact Room mapping."))
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Hotel PMS//Distribution Feed//EN", f"X-WR-CALNAME:{_ical_escape(connection.property)}"]
    stamp = now_datetime().strftime("%Y%m%dT%H%M%SZ")
    for event in _feed_events(connection, frappe._dict(mappings[0])):
        lines.extend([
            "BEGIN:VEVENT", f"UID:{_ical_escape(event['uid'])}", f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{_ical_date(event['start_date'])}", f"DTEND;VALUE=DATE:{_ical_date(event['end_date'])}",
            "SUMMARY:Blocked", "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    body = "\r\n".join(lines) + "\r\n"
    frappe.local.response["filename"] = f"hotel-{slug}.ics"
    frappe.local.response["filecontent"] = body
    frappe.local.response["type"] = "download"
    frappe.local.response["display_content_as"] = "inline"
    frappe.local.response["content_type"] = "text/calendar; charset=utf-8"
    frappe.local.response["headers"] = {"Cache-Control": "no-store, no-cache, must-revalidate"}
    return body


def on_reservation_change(doc, method=None) -> None:
    if not doc.property:
        return
    if frappe.get_all("Hotel Distribution Connection", filters={"property": doc.property, "enabled": 1, "outbound_ari_enabled": 1}, limit=1):
        frappe.enqueue("hotel_pms.distribution.push_all_ari", queue="long", enqueue_after_commit=True, job_id=f"distribution-ari-{doc.property}")

@frappe.whitelist()
def confirm_checkin(reservation: str, room: str | None = None) -> dict:
    _require_distribution_role()
    from hotel_pms.front_desk import get_locked_reservation
    doc = get_locked_reservation(reservation)
    require_property(doc.property, write=True)
    doc.check_permission("write")
    if room and len(doc.rooms) != 1:
        frappe.throw(_("Room selection in the check-in flow is available only for single-room reservations."))
    if room and doc.rooms and doc.rooms[0].room != room:
        target = frappe.db.get_value(
            "Hotel Room", room,
            ["property", "room_type", "operational_status", "housekeeping_status"], as_dict=True,
        )
        row = doc.rooms[0]
        if not target or target.property != doc.property or target.room_type != row.room_type:
            frappe.throw(_("Selected room does not match the reservation property and room type."))
        if target.operational_status != "Available" or target.housekeeping_status not in ("Clean", "Inspected"):
            frappe.throw(_("Selected room is not ready for check-in."))
        allowed = {x.name for x in available_rooms_with_distribution(doc.property, row.room_type, doc.arrival_date, doc.departure_date, exclude_reservation=doc.name)}
        if room not in allowed:
            frappe.throw(_("Selected room conflicts with another reservation or distribution block."))
        frappe.db.set_value("Hotel Reservation Room", row.name, "room", room)
        doc.reload()
    doc.check_in()
    return {"reservation": doc.name, "status": "Checked In", "rooms": [row.room for row in doc.rooms]}
