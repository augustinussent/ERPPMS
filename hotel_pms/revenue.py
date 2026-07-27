from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

import frappe
from frappe import _
from frappe.exceptions import DuplicateEntryError
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from hotel_pms.revenue_rules import (
    apply_adjustment,
    apply_derived_rate,
    money,
    stable_quote_hash,
    tax_breakdown,
    validate_stay_restrictions,
    voucher_discount,
)
from hotel_pms.sync import create_document_once, make_sync_key


def _require_revenue_read() -> None:
    frappe.only_for(["System Manager", "Hotel Manager", "Revenue Manager", "Front Desk", "Hotel Sales"])


def _require_revenue_write() -> None:
    frappe.only_for(["System Manager", "Hotel Manager", "Revenue Manager"])


def _as_dict(payload) -> dict:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            frappe.throw(_("Invalid JSON payload: {0}").format(exc))
    return payload or {}


def _plan_chain(rate_plan: str) -> list:
    chain = []
    seen = set()
    current = rate_plan
    while current:
        if current in seen or len(chain) >= 8:
            frappe.throw(_("Derived-rate plan chain is circular or too deep."))
        seen.add(current)
        doc = frappe.get_doc("Hotel Rate Plan", current)
        if not doc.enabled:
            frappe.throw(_("Rate plan {0} is disabled.").format(current))
        chain.append(doc)
        current = doc.base_rate_plan
    chain.reverse()
    return chain


def _base_plan_rate(chain: list) -> Decimal:
    if not chain:
        return Decimal("0")
    root = chain[0]
    rate = money(root.rate)
    for plan in chain[1:]:
        rate = apply_derived_rate(rate, plan.derived_adjustment_type, plan.derived_adjustment_value, plan.meal_plan_supplement)
    return money(rate)


def _season_for_date(property_name: str, room_type: str, rate_plan: str, stay_date) -> dict | None:
    rows = frappe.get_all(
        "Hotel Rate Season",
        filters={
            "property": property_name,
            "enabled": 1,
            "valid_from": ("<=", stay_date),
            "valid_to": (">=", stay_date),
        },
        fields=["name", "priority", "room_type", "rate_plan", "adjustment_type", "adjustment_value"],
        order_by="priority desc, modified desc",
    )
    weekday = getdate(stay_date).strftime("%A")
    for row in rows:
        if row.room_type and row.room_type != room_type:
            continue
        if row.rate_plan and row.rate_plan != rate_plan:
            continue
        days = frappe.get_all("Hotel Rate Season Day", filters={"parent": row.name}, pluck="day_of_week")
        if days and weekday not in days:
            continue
        return row
    return None


def _calendar_row(property_name: str, room_type: str, rate_plan: str, stay_date) -> dict:
    key = f"{property_name}|{room_type}|{rate_plan}|{getdate(stay_date)}"
    row = frappe.db.get_value(
        "Hotel Rate Calendar",
        key,
        [
            "rate_override", "floor_rate", "minimum_stay", "maximum_stay", "closed_to_arrival",
            "closed_to_departure", "stop_sell", "minimum_advance_days", "maximum_advance_days",
        ],
        as_dict=True,
    )
    return dict(row or {})


def _plan_defaults(plan) -> dict:
    return {
        "minimum_stay": cint(plan.min_stay or 1),
        "maximum_stay": cint(plan.max_stay or 0),
        "closed_to_arrival": cint(plan.closed_to_arrival or 0),
        "closed_to_departure": cint(plan.closed_to_departure or 0),
        "stop_sell": cint(plan.stop_sell or 0),
        "minimum_advance_days": cint(plan.minimum_advance_days or 0),
        "maximum_advance_days": cint(plan.maximum_advance_days or 0),
        "floor_rate": flt(plan.floor_rate or 0),
    }


def _merge_rules(defaults: dict, override: dict) -> dict:
    result = dict(defaults)
    for key, value in override.items():
        if value not in (None, ""):
            result[key] = value
    return result


def _validate_voucher(voucher_code: str | None, *, property_name: str, room_type: str, rate_plan: str, customer: str | None, arrival, departure, reservation: str | None = None) -> dict | None:
    if not voucher_code:
        return None
    code = voucher_code.strip().upper()
    if not frappe.db.exists("Hotel Voucher", code):
        frappe.throw(_("Voucher code {0} does not exist.").format(code))
    doc = frappe.get_doc("Hotel Voucher", code)
    if not doc.enabled or doc.property != property_name:
        frappe.throw(_("Voucher code is disabled or belongs to another property."))
    today = getdate(nowdate())
    if doc.booking_from and today < getdate(doc.booking_from):
        frappe.throw(_("Voucher is not active yet."))
    if doc.booking_to and today > getdate(doc.booking_to):
        frappe.throw(_("Voucher booking period has ended."))
    if doc.stay_from and getdate(arrival) < getdate(doc.stay_from):
        frappe.throw(_("Voucher does not apply to the selected stay dates."))
    if doc.stay_to and getdate(departure) > add_days(getdate(doc.stay_to), 1):
        frappe.throw(_("Voucher does not apply to the selected stay dates."))
    nights = (getdate(departure) - getdate(arrival)).days
    if doc.minimum_stay and nights < cint(doc.minimum_stay):
        frappe.throw(_("Voucher requires at least {0} night(s).").format(doc.minimum_stay))
    if doc.room_type and doc.room_type != room_type:
        frappe.throw(_("Voucher does not apply to this room type."))
    if doc.rate_plan and doc.rate_plan != rate_plan:
        frappe.throw(_("Voucher does not apply to this rate plan."))
    if doc.customer and doc.customer != customer:
        frappe.throw(_("Voucher is assigned to another customer."))
    redemption_filters = {"voucher": doc.name, "docstatus": ("<", 2), "status": ("in", ["Reserved", "Applied"])}
    redemptions = frappe.get_all("Hotel Voucher Redemption", filters=redemption_filters, fields=["name", "reservation", "customer"])
    redemptions = [row for row in redemptions if not reservation or row.reservation != reservation]
    used = len(redemptions)
    if doc.usage_limit and used >= cint(doc.usage_limit):
        frappe.throw(_("Voucher usage limit has been reached."))
    if customer and doc.usage_per_customer:
        per_customer = len([row for row in redemptions if row.customer == customer])
        if per_customer >= cint(doc.usage_per_customer):
            frappe.throw(_("Voucher usage limit for this customer has been reached."))
    return doc.as_dict()


def _validate_agent_contract(contract_name: str | None, property_name: str, arrival, departure) -> dict | None:
    if not contract_name:
        return None
    doc = frappe.get_doc("Hotel Travel Agent Contract", contract_name)
    if not doc.enabled or doc.property != property_name:
        frappe.throw(_("Travel-agent contract is disabled or belongs to another property."))
    if getdate(arrival) < getdate(doc.valid_from) or getdate(departure) > add_days(getdate(doc.valid_to), 1):
        frappe.throw(_("Travel-agent contract is not valid for the complete stay."))
    return doc.as_dict()


def _tax_profile(property_name: str, tax_profile: str | None = None) -> dict:
    profile_name = tax_profile or frappe.db.get_value("Hotel Property", property_name, "default_hotel_tax_profile")
    if not profile_name:
        profile_name = frappe.db.get_single_value("Hotel PMS Settings", "default_hotel_tax_profile")
    if not profile_name:
        return frappe._dict({
            "name": None, "service_charge_rate": 0, "tax_rate": 0,
            "tax_basis": "Net Amount plus Service Charge", "prices_include_service_charge": 0,
            "prices_include_tax": 0, "rounding_method": "No Rounding",
        })
    doc = frappe.get_doc("Hotel Tax Profile", profile_name)
    if not doc.enabled or doc.property != property_name:
        frappe.throw(_("Hotel tax profile is disabled or belongs to another property."))
    return doc.as_dict()


@frappe.whitelist()
def quote_stay(
    property: str,
    room_type: str,
    rate_plan: str,
    arrival_date: str,
    departure_date: str,
    adults: int = 1,
    children: int = 0,
    customer: str | None = None,
    voucher_code: str | None = None,
    travel_agent_contract: str | None = None,
    requested_rate: float | None = None,
    rate_approval: str | None = None,
    tax_profile: str | None = None,
    reservation: str | None = None,
) -> dict:
    _require_revenue_read()
    arrival = getdate(arrival_date)
    departure = getdate(departure_date)
    if departure <= arrival:
        frappe.throw(_("Departure date must be after arrival date."))
    chain = _plan_chain(rate_plan)
    leaf = chain[-1]
    if leaf.property != property or leaf.room_type != room_type:
        frappe.throw(_("Rate plan does not belong to the selected property and room type."))
    if leaf.valid_from and arrival < getdate(leaf.valid_from):
        frappe.throw(_("Rate plan is not valid on the arrival date."))
    if leaf.valid_to and departure > add_days(getdate(leaf.valid_to), 1):
        frappe.throw(_("Rate plan is not valid for the complete stay."))

    base = _base_plan_rate(chain)
    daily = []
    rules = []
    approved_name = None
    for index in range((departure - arrival).days):
        stay_date = add_days(arrival, index)
        rate = base
        season = _season_for_date(property, room_type, rate_plan, stay_date)
        if season:
            rate = apply_adjustment(rate, season.adjustment_type, season.adjustment_value)
        calendar = _calendar_row(property, room_type, rate_plan, stay_date)
        if flt(calendar.get("rate_override")):
            rate = money(calendar["rate_override"])
        merged = _merge_rules(_plan_defaults(leaf), calendar)
        floor = money(merged.get("floor_rate") or 0)
        effective = money(requested_rate) if requested_rate is not None else money(rate)
        if floor and effective < floor:
            if not rate_approval:
                frappe.throw(_("Requested rate for {0} is below the floor rate. Approval is required.").format(stay_date))
            approval = frappe.get_doc("Hotel Rate Approval", rate_approval)
            if approval.status != "Approved" or approval.property != property or approval.room_type != room_type or approval.rate_plan != rate_plan:
                frappe.throw(_("Rate approval is invalid for this quote."))
            if approval.stay_date and getdate(approval.stay_date) != getdate(stay_date):
                frappe.throw(_("Rate approval does not cover {0}.").format(stay_date))
            if money(approval.requested_rate) != effective:
                frappe.throw(_("Approved rate does not match the requested rate."))
            approved_name = approval.name
        rules.append(merged)
        daily.append({
            "date": str(stay_date), "base_rate": float(base), "season": season.name if season else None,
            "calendar_override": bool(calendar), "rate": float(effective), "floor_rate": float(floor),
            "rules": merged,
        })

    departure_rules = _merge_rules(_plan_defaults(leaf), _calendar_row(property, room_type, rate_plan, departure))
    errors = validate_stay_restrictions(
        arrival_date=arrival, departure_date=departure, booking_date=getdate(nowdate()),
        arrival_rules=rules[0], departure_rules=departure_rules, daily_rules=rules,
    )
    if errors:
        frappe.throw("<br>".join(_(message) for message in errors), title=_("Rate Restriction"))

    subtotal = money(sum(Decimal(str(row["rate"])) for row in daily))
    agent = _validate_agent_contract(travel_agent_contract, property, arrival, departure)
    agent_discount = Decimal("0.00")
    if agent and agent.pricing_basis == "Net Rate":
        agent_discount = money(subtotal * Decimal(str(agent.net_rate_discount or 0)) / Decimal("100"))
    after_agent = money(subtotal - agent_discount)
    voucher = _validate_voucher(
        voucher_code, property_name=property, room_type=room_type, rate_plan=rate_plan,
        customer=customer, arrival=arrival, departure=departure, reservation=reservation,
    )
    discount = voucher_discount(
        after_agent,
        voucher.discount_type if voucher else None,
        voucher.discount_value if voucher else 0,
        voucher.maximum_discount if voucher else 0,
    )
    advertised_total = money(after_agent - discount)
    profile = _tax_profile(property, tax_profile)
    breakdown = tax_breakdown(
        advertised_total,
        profile.service_charge_rate,
        profile.tax_rate,
        profile.tax_basis,
        bool(profile.prices_include_service_charge),
        bool(profile.prices_include_tax),
        profile.rounding_method,
    )
    commission = Decimal("0.00")
    if agent and agent.pricing_basis == "Gross Rate with Commission":
        commission = money(advertised_total * Decimal(str(agent.commission_rate or 0)) / Decimal("100"))

    payload = {
        "property": property, "room_type": room_type, "rate_plan": rate_plan,
        "arrival_date": str(arrival), "departure_date": str(departure), "adults": cint(adults), "children": cint(children),
        "daily_rates": daily, "subtotal": float(subtotal), "agent_discount": float(agent_discount),
        "voucher": voucher.name if voucher else None, "voucher_discount": float(discount),
        "advertised_total": float(advertised_total), "tax_profile": profile.name,
        "net": float(breakdown["net"]), "service_charge": float(breakdown["service_charge"]),
        "tax": float(breakdown["tax"]), "rounding_adjustment": float(breakdown["rounding_adjustment"]),
        "grand_total": float(breakdown["gross"]), "travel_agent_contract": agent.name if agent else None,
        "agent_commission": float(commission), "rate_approval": approved_name,
    }
    payload["quote_hash"] = stable_quote_hash(payload)
    return payload


@frappe.whitelist()
def get_rate_calendar(property: str, room_type: str, rate_plan: str, start_date: str | None = None, days: int = 31) -> dict:
    _require_revenue_read()
    start = getdate(start_date or nowdate())
    days = max(1, min(cint(days or 31), 366))
    chain = _plan_chain(rate_plan)
    base = _base_plan_rate(chain)
    result = []
    for index in range(days):
        stay_date = add_days(start, index)
        row = _calendar_row(property, room_type, rate_plan, stay_date)
        rate = base
        season = _season_for_date(property, room_type, rate_plan, stay_date)
        if season:
            rate = apply_adjustment(rate, season.adjustment_type, season.adjustment_value)
        if flt(row.get("rate_override")):
            rate = money(row["rate_override"])
        warning = None
        if cint(row.get("stop_sell")):
            warning = _("Stop Sell")
        result.append({
            "date": str(stay_date), **row, "effective_rate": float(money(rate)),
            "season": season.name if season else None, "error": warning,
        })
    return {"property": property, "room_type": room_type, "rate_plan": rate_plan, "start_date": str(start), "days": result}


@frappe.whitelist()
def bulk_upsert_rate_calendar(payload) -> dict:
    _require_revenue_write()
    data = _as_dict(payload)
    for field in ("property", "room_type", "rate_plan", "rows"):
        if not data.get(field):
            frappe.throw(_("Missing required field: {0}").format(field))
    saved = 0
    for row in data["rows"]:
        stay_date = getdate(row.get("date"))
        key = f"{data['property']}|{data['room_type']}|{data['rate_plan']}|{stay_date}"
        doc = frappe.get_doc("Hotel Rate Calendar", key) if frappe.db.exists("Hotel Rate Calendar", key) else frappe.new_doc("Hotel Rate Calendar")
        doc.update({
            "calendar_key": key, "property": data["property"], "room_type": data["room_type"], "rate_plan": data["rate_plan"],
            "rate_date": stay_date, "rate_override": row.get("rate_override"), "floor_rate": row.get("floor_rate"),
            "minimum_stay": row.get("minimum_stay"), "maximum_stay": row.get("maximum_stay"),
            "closed_to_arrival": cint(row.get("closed_to_arrival")), "closed_to_departure": cint(row.get("closed_to_departure")),
            "stop_sell": cint(row.get("stop_sell")), "minimum_advance_days": row.get("minimum_advance_days"),
            "maximum_advance_days": row.get("maximum_advance_days"), "notes": row.get("notes"),
        })
        doc.save(ignore_permissions=True)
        saved += 1
    return {"saved": saved}


@frappe.whitelist()
def request_rate_approval(payload) -> dict:
    _require_revenue_read()
    data = _as_dict(payload)
    key = make_sync_key("RATEAPP", data.get("property"), data.get("room_type"), data.get("rate_plan"), data.get("stay_date"), data.get("requested_rate"), data.get("request_key"))
    existing = frappe.db.get_value("Hotel Rate Approval", {"idempotency_key": key}, "name")
    if existing:
        return {"rate_approval": existing, "already_created": True}
    doc = frappe.get_doc({"doctype": "Hotel Rate Approval", **data, "idempotency_key": key, "status": "Pending"})
    doc.insert()
    return {"rate_approval": doc.name, "already_created": False}


def reserve_voucher_for_reservation(reservation) -> str | None:
    if not reservation.voucher_code:
        return None
    key = make_sync_key("VOUCHER", reservation.name, reservation.voucher_code)
    existing = frappe.db.get_value("Hotel Voucher Redemption", {"idempotency_key": key}, "name")
    if existing:
        return existing
    doc = frappe.get_doc({
        "doctype": "Hotel Voucher Redemption", "voucher": reservation.voucher_code.strip().upper(),
        "reservation": reservation.name, "customer": reservation.guest,
        "discount_amount": reservation.voucher_discount, "status": "Reserved", "idempotency_key": key,
    })
    try:
        doc.insert(ignore_permissions=True)
        doc.submit()
    except DuplicateEntryError:
        return frappe.db.get_value("Hotel Voucher Redemption", {"reservation": reservation.name}, "name")
    return doc.name


def release_voucher_for_reservation(reservation_name: str) -> None:
    name = frappe.db.get_value("Hotel Voucher Redemption", {"reservation": reservation_name, "docstatus": 1}, "name")
    if name:
        frappe.db.set_value("Hotel Voucher Redemption", name, "status", "Released")


@frappe.whitelist()
def build_travel_agent_settlement(contract: str, period_from: str, period_to: str, request_key: str) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Revenue Manager", "Accounts Manager"])
    contract_doc = frappe.get_doc("Hotel Travel Agent Contract", contract)
    key = make_sync_key("TASET", contract, period_from, period_to, request_key)
    existing = frappe.db.get_value("Hotel Travel Agent Settlement", {"idempotency_key": key}, "name")
    if existing:
        return {"settlement": existing, "already_created": True}
    reservations = frappe.get_all(
        "Hotel Reservation",
        filters={
            "property": contract_doc.property, "travel_agent_contract": contract,
            "status": "Checked Out", "departure_date": ("between", [period_from, period_to]),
            "travel_agent_commission_status": ("in", ["Pending", ""]),
        },
        fields=["name", "departure_date", "quoted_room_total", "travel_agent_commission"],
    )
    doc = frappe.get_doc({
        "doctype": "Hotel Travel Agent Settlement", "property": contract_doc.property, "contract": contract,
        "supplier": contract_doc.travel_agent, "period_from": period_from, "period_to": period_to,
        "idempotency_key": key,
    })
    for row in reservations:
        if flt(row.travel_agent_commission) <= 0:
            continue
        doc.append("lines", {
            "reservation": row.name, "departure_date": row.departure_date,
            "gross_revenue": row.quoted_room_total, "commission_rate": contract_doc.commission_rate,
            "commission_amount": row.travel_agent_commission,
        })
    if not doc.lines:
        frappe.throw(_("No unsettled travel-agent commission was found for the selected period."))
    doc.insert()
    return {"settlement": doc.name, "already_created": False}


@frappe.whitelist()
def create_travel_agent_purchase_invoice(settlement: str) -> dict:
    frappe.only_for(["System Manager", "Hotel Manager", "Accounts Manager"])
    doc = frappe.get_doc("Hotel Travel Agent Settlement", settlement)
    doc.check_permission("write")
    contract = frappe.get_doc("Hotel Travel Agent Contract", doc.contract)
    if doc.purchase_invoice and frappe.db.exists("Purchase Invoice", doc.purchase_invoice):
        return {"purchase_invoice": doc.purchase_invoice, "already_created": True}
    if not contract.commission_item:
        frappe.throw(_("Commission Item must be configured on the travel-agent contract."))
    property_doc = frappe.get_doc("Hotel Property", doc.property)
    key = make_sync_key("PI", "TRAVELAGENT", doc.name)

    def build():
        invoice = frappe.new_doc("Purchase Invoice")
        invoice.company = property_doc.company
        invoice.supplier = doc.supplier
        invoice.posting_date = getdate()
        invoice.due_date = add_days(getdate(), cint(contract.settlement_days or 30))
        if invoice.meta.has_field("custom_hotel_travel_agent_settlement"):
            invoice.custom_hotel_travel_agent_settlement = doc.name
        invoice.append("items", {
            "item_code": contract.commission_item, "description": f"Travel-agent commission settlement {doc.name}",
            "qty": 1, "rate": doc.total_commission, "expense_account": contract.expense_account,
            "cost_center": contract.cost_center or property_doc.default_cost_center,
        })
        return invoice

    invoice, already = create_document_once(
        base_key=key, operation="Create Travel Agent Purchase Invoice",
        source_doctype=doc.doctype, source_name=doc.name, target_doctype="Purchase Invoice",
        build_document=build, payload={"settlement": doc.name, "total": doc.total_commission},
    )
    doc.db_set({"purchase_invoice": invoice.name, "status": "Invoiced"})
    for row in doc.lines:
        frappe.db.set_value("Hotel Reservation", row.reservation, "travel_agent_commission_status", "Invoiced")
    return {"purchase_invoice": invoice.name, "already_created": already}

@frappe.whitelist()
def quote_booking(payload) -> dict:
    """Quote multiple room requests and apply one voucher to the booking total."""
    _require_revenue_read()
    data = _as_dict(payload)
    requests = data.get("room_requests") or []
    if not requests:
        frappe.throw(_("Add at least one room request."))
    room_quotes = []
    advertised_total = Decimal("0")
    subtotal = Decimal("0")
    for request in requests:
        quantity = max(cint(request.get("quantity") or 1), 1)
        quote = quote_stay(
            property=data["property"], room_type=request["room_type"], rate_plan=request["rate_plan"],
            arrival_date=data["arrival_date"], departure_date=data["departure_date"],
            adults=request.get("adults") or 1, children=request.get("children") or 0,
            customer=data.get("customer"), voucher_code=None,
            travel_agent_contract=data.get("travel_agent_contract"), requested_rate=request.get("requested_rate"),
            rate_approval=request.get("rate_approval"), tax_profile=data.get("tax_profile"), reservation=data.get("reservation"),
        )
        quote["quantity"] = quantity
        room_quotes.append(quote)
        subtotal += Decimal(str(quote["subtotal"])) * quantity
        advertised_total += Decimal(str(quote["advertised_total"])) * quantity

    voucher = None
    if data.get("voucher_code"):
        # A scoped voucher must match every room request. A hotel may instead create
        # an unrestricted booking-level voucher when mixed room types are intended.
        for request in requests:
            voucher = _validate_voucher(
                data["voucher_code"], property_name=data["property"], room_type=request["room_type"],
                rate_plan=request["rate_plan"], customer=data.get("customer"),
                arrival=data["arrival_date"], departure=data["departure_date"], reservation=data.get("reservation"),
            )
    discount = voucher_discount(
        advertised_total, voucher.discount_type if voucher else None,
        voucher.discount_value if voucher else 0, voucher.maximum_discount if voucher else 0,
    )
    after_discount = money(advertised_total - discount)
    profile = _tax_profile(data["property"], data.get("tax_profile"))
    breakdown = tax_breakdown(
        after_discount, profile.service_charge_rate, profile.tax_rate, profile.tax_basis,
        bool(profile.prices_include_service_charge), bool(profile.prices_include_tax), profile.rounding_method,
    )
    agent = _validate_agent_contract(data.get("travel_agent_contract"), data["property"], data["arrival_date"], data["departure_date"])
    commission = Decimal("0")
    if agent and agent.pricing_basis == "Gross Rate with Commission":
        commission = money(after_discount * Decimal(str(agent.commission_rate or 0)) / Decimal("100"))
    result = {
        "property": data["property"], "arrival_date": str(getdate(data["arrival_date"])),
        "departure_date": str(getdate(data["departure_date"])), "rooms": room_quotes,
        "subtotal": float(money(subtotal)), "advertised_total_before_voucher": float(money(advertised_total)),
        "voucher": voucher.name if voucher else None, "voucher_discount": float(discount),
        "advertised_total": float(after_discount), "tax_profile": profile.name,
        "net": float(breakdown["net"]), "service_charge": float(breakdown["service_charge"]),
        "tax": float(breakdown["tax"]), "rounding_adjustment": float(breakdown["rounding_adjustment"]),
        "grand_total": float(breakdown["gross"]), "travel_agent_contract": agent.name if agent else None,
        "agent_commission": float(commission),
    }
    result["quote_hash"] = stable_quote_hash(result)
    return result


def expire_rate_approvals() -> dict:
    rows = frappe.get_all("Hotel Rate Approval", filters={"status": "Approved", "expires_at": ("<", now_datetime())}, pluck="name")
    for name in rows:
        frappe.db.set_value("Hotel Rate Approval", name, "status", "Expired", update_modified=False)
    return {"expired": len(rows)}


def update_travel_agent_settlement_statuses() -> dict:
    updated = 0
    rows = frappe.get_all("Hotel Travel Agent Settlement", filters={"status": "Invoiced", "purchase_invoice": ("is", "set")}, fields=["name", "purchase_invoice"])
    for row in rows:
        if not frappe.db.exists("Purchase Invoice", row.purchase_invoice):
            continue
        invoice = frappe.db.get_value("Purchase Invoice", row.purchase_invoice, ["docstatus", "outstanding_amount"], as_dict=True)
        if invoice and invoice.docstatus == 1 and flt(invoice.outstanding_amount) == 0:
            frappe.db.set_value("Hotel Travel Agent Settlement", row.name, "status", "Paid", update_modified=False)
            for line in frappe.get_all("Hotel Travel Agent Settlement Line", filters={"parent": row.name}, pluck="reservation"):
                frappe.db.set_value("Hotel Reservation", line, "travel_agent_commission_status", "Paid", update_modified=False)
            updated += 1
    return {"updated": updated}
