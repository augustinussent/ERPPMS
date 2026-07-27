from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, flt, get_datetime, now_datetime, nowdate, time_diff_in_seconds

from hotel_pms.restaurant_controls_rules import (
    RestaurantAlertCandidate,
    build_kitchen_snapshot,
    diff_kitchen_snapshots,
    discount_decision,
    session_gate,
    stable_hash,
    table_cluster_decision,
    ticket_type_for_actions,
    validate_fractional_quantity,
)
from hotel_pms.sync import make_sync_key

SESSION_ROLES = {"Restaurant Cashier", "Restaurant Captain", "Hotel Manager", "Accounts Manager", "System Manager"}
MANAGER_ROLES = {"Hotel Manager", "Accounts Manager", "System Manager"}


def _require(roles: set[str]) -> None:
    if not (set(frappe.get_roles()) & roles):
        frappe.throw(_("You do not have permission for this restaurant operation."), frappe.PermissionError)


def _lock(doctype: str, name: str):
    rows = frappe.db.sql(f"select name from `tab{doctype}` where name=%s for update", name)
    if not rows:
        frappe.throw(_("{0} {1} was not found.").format(doctype, name))
    return frappe.get_doc(doctype, name)


def _outlet_requires_opening(outlet_doc) -> bool:
    return bool(cint(outlet_doc.get("require_pos_opening_entry") or 0))


def active_restaurant_session(outlet: str, user: str | None = None) -> dict:
    user = user or frappe.session.user
    outlet_doc = frappe.get_doc("Hotel Outlet", outlet)
    shifts = frappe.get_all(
        "Hotel Cashier Shift",
        filters={
            "property": outlet_doc.property,
            "outlet": outlet_doc.name,
            "cashier": user,
            "status": ["in", ["Open", "Closing Review"]],
        },
        pluck="name",
        order_by="opened_at desc",
        limit=1,
    )
    shift_name = shifts[0] if shifts else None
    shift = frappe.get_doc("Hotel Cashier Shift", shift_name) if shift_name else None
    opening_name = shift.get("pos_opening_entry") if shift else None
    opening_ok = False
    opening_status = "Not Linked"
    if opening_name and frappe.db.exists("POS Opening Entry", opening_name):
        values = frappe.db.get_value(
            "POS Opening Entry",
            opening_name,
            ["docstatus", "status", "pos_profile", "user", "company"],
            as_dict=True,
        )
        opening_status = values.status or ""
        opening_ok = bool(
            cint(values.docstatus) == 1
            and values.status == "Open"
            and values.pos_profile == outlet_doc.pos_profile
            and values.user == user
            and values.company == outlet_doc.company
        )
    decision = session_gate(
        outlet_requires_opening=_outlet_requires_opening(outlet_doc),
        shift_open=bool(shift and shift.status == "Open"),
        pos_opening_submitted=opening_ok,
    )
    return {
        "allowed": decision["allowed"],
        "reason": decision["reason"],
        "outlet": outlet_doc.name,
        "pos_profile": outlet_doc.pos_profile,
        "cashier_shift": shift.name if shift else None,
        "shift_status": shift.status if shift else None,
        "pos_opening_entry": opening_name,
        "pos_opening_status": opening_status,
    }


def require_restaurant_session(outlet: str, user: str | None = None) -> dict:
    context = active_restaurant_session(outlet, user)
    if not context["allowed"]:
        frappe.throw(_(context["reason"]))
    return context


@frappe.whitelist()
def get_restaurant_session_context(outlet: str) -> dict:
    _require(SESSION_ROLES)
    return active_restaurant_session(outlet)


@frappe.whitelist()
def link_pos_opening_entry(shift: str, pos_opening_entry: str) -> dict:
    _require(SESSION_ROLES)
    shift_doc = _lock("Hotel Cashier Shift", shift)
    shift_doc.check_permission("write")
    opening = frappe.get_doc("POS Opening Entry", pos_opening_entry)
    if opening.docstatus != 1 or opening.status != "Open":
        frappe.throw(_("ERPNext POS Opening Entry must be submitted and Open."))
    outlet = frappe.get_doc("Hotel Outlet", shift_doc.outlet)
    if opening.pos_profile != outlet.pos_profile:
        frappe.throw(_("POS Opening Entry must use the outlet POS Profile."))
    if opening.user != shift_doc.cashier:
        frappe.throw(_("POS Opening Entry user must match the Hotel Cashier Shift cashier."))
    if opening.company != shift_doc.company:
        frappe.throw(_("POS Opening Entry company must match the cashier shift company."))
    existing = frappe.db.get_value(
        "Hotel Cashier Shift",
        {"pos_opening_entry": opening.name, "name": ["!=", shift_doc.name]},
        "name",
    )
    if existing:
        frappe.throw(_("This POS Opening Entry is already linked to cashier shift {0}.").format(existing))
    shift_doc.pos_profile = outlet.pos_profile
    shift_doc.pos_opening_entry = opening.name
    shift_doc.erpnext_session_status = "Open"
    shift_doc.save(ignore_permissions=True)
    if frappe.get_meta("POS Opening Entry").has_field("custom_hotel_cashier_shift"):
        frappe.db.set_value(
            "POS Opening Entry",
            opening.name,
            {
                "custom_hotel_cashier_shift": shift_doc.name,
                "custom_hotel_property": shift_doc.property,
                "custom_hotel_outlet": shift_doc.outlet,
            },
            update_modified=False,
        )
    return {"cashier_shift": shift_doc.name, "pos_opening_entry": opening.name, "status": "Open"}


@frappe.whitelist()
def link_pos_closing_entry(shift: str, pos_closing_entry: str) -> dict:
    _require(MANAGER_ROLES | {"Restaurant Cashier"})
    shift_doc = _lock("Hotel Cashier Shift", shift)
    closing = frappe.get_doc("POS Closing Entry", pos_closing_entry)
    if closing.docstatus != 1 or closing.status != "Closed":
        frappe.throw(_("ERPNext POS Closing Entry must be submitted and Closed."))
    if closing.pos_profile != shift_doc.pos_profile:
        frappe.throw(_("POS Closing Entry must use the cashier shift POS Profile."))
    if closing.user != shift_doc.cashier:
        frappe.throw(_("POS Closing Entry user must match the cashier shift cashier."))
    shift_doc.pos_closing_entry = closing.name
    shift_doc.erpnext_session_status = "Closed"
    shift_doc.last_reconciled_at = now_datetime()
    shift_doc.save(ignore_permissions=True)
    if frappe.get_meta("POS Closing Entry").has_field("custom_hotel_cashier_shift"):
        frappe.db.set_value(
            "POS Closing Entry",
            closing.name,
            {
                "custom_hotel_cashier_shift": shift_doc.name,
                "custom_hotel_property": shift_doc.property,
                "custom_hotel_outlet": shift_doc.outlet,
            },
            update_modified=False,
        )
    return {"cashier_shift": shift_doc.name, "pos_closing_entry": closing.name, "status": "Closed"}


def validate_order_item_uom(item_code: str, qty: object) -> Decimal:
    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom")
    whole_only = bool(stock_uom and frappe.db.get_value("UOM", stock_uom, "must_be_whole_number"))
    decision = validate_fractional_quantity(qty, whole_only)
    if not decision["valid"]:
        frappe.throw(_(decision["reason"]))
    return decision["quantity"]


def validate_discount(split_doc, outlet_doc) -> None:
    percent = flt(split_doc.get("discount_percentage") or 0)
    threshold = flt(outlet_doc.get("cashier_discount_limit") or 0)
    authorized = bool(split_doc.get("discount_authorized_by"))
    decision = discount_decision(percent, threshold, authorized)
    if not decision["allowed"]:
        frappe.throw(_(decision["reason"]))
    if percent and not split_doc.get("discount_reason"):
        frappe.throw(_("Discount reason is required."))
    if decision["requires_approval"]:
        approver = split_doc.discount_authorized_by
        if not approver or not (set(frappe.get_roles(approver)) & MANAGER_ROLES):
            frappe.throw(_("Discount approver must have Hotel Manager, Accounts Manager, or System Manager role."))


@frappe.whitelist()
def merge_restaurant_tables(order: str, tables, request_key: str) -> dict:
    _require({"Restaurant Captain", "Restaurant Cashier", "Hotel Manager", "System Manager"})
    if isinstance(tables, str):
        tables = json.loads(tables)
    order_doc = _lock("Hotel Restaurant Order", order)
    selected = sorted(set([order_doc.table] + list(tables or [])))
    table_rows = []
    for name in selected:
        if not name:
            continue
        locked = frappe.db.sql(
            "select name, outlet, status, active_order from `tabHotel Restaurant Table` where name=%s for update",
            name,
            as_dict=True,
        )
        if not locked:
            frappe.throw(_("Restaurant table {0} was not found.").format(name))
        table_rows.append(locked[0])
    decision = table_cluster_decision(table_rows, order_doc.outlet, order_doc.name)
    if not decision["allowed"]:
        frappe.throw(_(decision["reason"]))
    key = make_sync_key("TABLE-CLUSTER", order_doc.name, request_key)
    existing = frappe.db.get_value("Hotel Restaurant Table Cluster", {"request_key": key}, "name")
    if existing:
        return {"cluster": existing, "already_created": True}
    active_cluster = frappe.db.get_value(
        "Hotel Restaurant Table Cluster",
        {"restaurant_order": order_doc.name, "status": "Active"},
        "name",
    )
    if active_cluster:
        frappe.throw(_("Release the active table cluster before creating a replacement."))
    cluster = frappe.get_doc(
        {
            "doctype": "Hotel Restaurant Table Cluster",
            "property": order_doc.property,
            "outlet": order_doc.outlet,
            "restaurant_order": order_doc.name,
            "status": "Active",
            "created_at": now_datetime(),
            "request_key": key,
        }
    )
    for name in decision["tables"]:
        cluster.append("members", {"table": name})
    cluster.insert(ignore_permissions=True)
    for name in decision["tables"]:
        frappe.db.set_value(
            "Hotel Restaurant Table",
            name,
            {"active_order": order_doc.name, "status": "Occupied", "table_cluster": cluster.name},
            update_modified=False,
        )
    frappe.db.set_value("Hotel Restaurant Order", order_doc.name, "table_cluster", cluster.name, update_modified=False)
    return {"cluster": cluster.name, "tables": decision["tables"], "already_created": False}


@frappe.whitelist()
def release_restaurant_table_cluster(cluster: str, reason: str | None = None) -> dict:
    _require({"Restaurant Captain", "Restaurant Cashier", "Hotel Manager", "System Manager"})
    doc = _lock("Hotel Restaurant Table Cluster", cluster)
    if doc.status == "Released":
        return {"cluster": doc.name, "already_released": True}
    for row in doc.members:
        values = frappe.db.get_value("Hotel Restaurant Table", row.table, ["active_order", "table_cluster"], as_dict=True)
        if values and values.table_cluster == doc.name:
            frappe.db.set_value(
                "Hotel Restaurant Table",
                row.table,
                {"active_order": None, "table_cluster": None, "status": "Cleaning"},
                update_modified=False,
            )
    doc.status = "Released"
    doc.released_at = now_datetime()
    doc.release_reason = reason
    doc.save(ignore_permissions=True)
    return {"cluster": doc.name, "already_released": False}


def _next_kot_number(outlet: str) -> int:
    outlet_doc = _lock("Hotel Outlet", outlet)
    today = nowdate()
    if str(outlet_doc.daily_kot_date or "") != str(today):
        outlet_doc.daily_kot_date = today
        outlet_doc.daily_kot_counter = 0
    outlet_doc.daily_kot_counter = cint(outlet_doc.daily_kot_counter) + 1
    outlet_doc.save(ignore_permissions=True)
    return outlet_doc.daily_kot_counter


def _publish_kds(property_name: str, outlet: str, ticket: str, action: str) -> None:
    frappe.publish_realtime(
        "hotel_kds_update",
        {"property": property_name, "outlet": outlet, "ticket": ticket, "action": action},
        after_commit=True,
    )


@frappe.whitelist()
def sync_order_to_kitchen(order: str, request_key: str, change_reason: str | None = None) -> dict:
    _require({"Restaurant Captain", "Restaurant Cashier", "Hotel Manager", "System Manager"})
    order_doc = _lock("Hotel Restaurant Order", order)
    if order_doc.status not in ("Confirmed", "In Kitchen", "Ready", "Served"):
        frappe.throw(_("Confirm the order before synchronizing it to the kitchen."))
    current = build_kitchen_snapshot([row.as_dict() for row in order_doc.items])
    try:
        previous = json.loads(order_doc.kitchen_snapshot_json or "{}")
    except Exception:
        previous = {}
    current_hash = stable_hash(current)
    if current_hash == (order_doc.kitchen_snapshot_hash or ""):
        return {"order": order_doc.name, "tickets": [], "already_synchronized": True}
    deltas = diff_kitchen_snapshots(previous, current)
    if not deltas:
        order_doc.kitchen_snapshot_json = json.dumps(current, sort_keys=True)
        order_doc.kitchen_snapshot_hash = current_hash
        order_doc.save(ignore_permissions=True)
        return {"order": order_doc.name, "tickets": [], "already_synchronized": True}
    revision = cint(order_doc.kitchen_revision or 0) + 1
    # Emit separate KOTs for additions, reductions and modifications. This keeps
    # ERPNext recipe consumption strictly attached to positive quantity deltas;
    # cancellation tickets never trigger an automatic stock reversal.
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for delta in deltas:
        unit = str(delta.get("production_unit") or "Main Kitchen")
        action = str(delta.get("action") or "Modify")
        grouped[(unit, action)].append(delta)
    tickets: list[str] = []
    for (unit, action_bucket), rows in grouped.items():
        ticket_type = ticket_type_for_actions([str(row["action"]) for row in rows], first_revision=revision == 1)
        key = make_sync_key("KOT-REV", order_doc.name, revision, unit, action_bucket, request_key)
        existing = frappe.db.get_value("Hotel Kitchen Ticket", {"request_key": key}, "name")
        if existing:
            tickets.append(existing)
            continue
        production_unit = unit if frappe.db.exists("Hotel Kitchen Production Unit", unit) else frappe.db.get_value(
            "Hotel Kitchen Production Unit",
            {"outlet": order_doc.outlet, "unit_name": unit, "enabled": 1},
            "name",
        )
        if production_unit:
            unit_values = frappe.db.get_value("Hotel Kitchen Production Unit", production_unit, ["outlet", "enabled", "unit_name", "warning_minutes"], as_dict=True)
            if not unit_values or unit_values.outlet != order_doc.outlet or not cint(unit_values.enabled):
                frappe.throw(_("Kitchen Production Unit must be enabled and belong to the order outlet."))
            station_label = unit_values.unit_name
            warning_minutes = cint(unit_values.warning_minutes) or 15
        else:
            station_label = unit
            warning_minutes = cint(frappe.db.get_value("Hotel Outlet", order_doc.outlet, "kds_late_minutes")) or 15
        kot = frappe.get_doc(
            {
                "doctype": "Hotel Kitchen Ticket",
                "property": order_doc.property,
                "outlet": order_doc.outlet,
                "restaurant_order": order_doc.name,
                "kot_date": nowdate(),
                "daily_kot_number": _next_kot_number(order_doc.outlet),
                "kitchen_station": station_label,
                "production_unit": production_unit,
                "ticket_type": ticket_type,
                "revision_no": revision,
                "change_reason": change_reason,
                "source_snapshot_hash": current_hash,
                "sent_at": now_datetime(),
                "last_activity_at": now_datetime(),
                "target_ready_at": add_to_date(now_datetime(), minutes=warning_minutes),
                "table": order_doc.table,
                "table_cluster": order_doc.table_cluster,
                "room": order_doc.room,
                "guest_name": order_doc.guest_name,
                "captain": frappe.session.user,
                "priority": order_doc.priority or "Normal",
                "course": ", ".join(sorted({str(row.get("course") or "Main") for row in rows})),
                "request_key": key,
            }
        )
        for delta in rows:
            kot.append(
                "items",
                {
                    "order_item_row": delta["row_key"],
                    "menu_item": delta.get("menu_item"),
                    "item_code": delta.get("item_code"),
                    "item_name": delta.get("item_name"),
                    "qty": delta.get("qty"),
                    "delta_action": delta.get("action"),
                    "notes": delta.get("notes"),
                    "course": delta.get("course"),
                    "allergy_alert": delta.get("allergy_alert"),
                    "preparation_minutes": delta.get("preparation_minutes"),
                    "status": "Cancelled" if delta.get("action") == "Reduce" else "New",
                },
            )
        kot.insert(ignore_permissions=True)
        tickets.append(kot.name)
        if action_bucket == "Add":
            from hotel_pms.fnb_inventory import queue_ticket_stock_posting
            queue_ticket_stock_posting(kot.name)
        else:
            kot.db_set(
                {
                    "stock_posting_status": "Not Required",
                    "stock_error": _("Reduction/cancellation KOT does not auto-reverse ERPNext stock. Review wastage or correction separately."),
                },
                update_modified=False,
            )
        try:
            from hotel_pms.restaurant_printing import queue_restaurant_print_jobs

            queue_restaurant_print_jobs("Hotel Kitchen Ticket", kot.name, "KOT", request_key=key)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Queue restaurant KOT print failed: {kot.name}")
        _publish_kds(order_doc.property, order_doc.outlet, kot.name, "new")
    order_doc.kitchen_revision = revision
    order_doc.kitchen_snapshot_json = json.dumps(current, sort_keys=True)
    order_doc.kitchen_snapshot_hash = current_hash
    order_doc.status = "In Kitchen"
    order_doc.save(ignore_permissions=True)
    for row in order_doc.items:
        current_row = current.get(row.name) or {}
        if Decimal(str(current_row.get("qty") or 0)) > 0 and row.status == "Ordered":
            frappe.db.set_value("Hotel Restaurant Order Item", row.name, "status", "Sent", update_modified=False)
    return {"order": order_doc.name, "revision": revision, "tickets": tickets, "already_synchronized": False}


@frappe.whitelist()
def restaurant_prebill_context(order: str) -> dict:
    _require(SESSION_ROLES | {"Kitchen"})
    order_doc = frappe.get_doc("Hotel Restaurant Order", order)
    blockers: list[dict] = []
    session = active_restaurant_session(order_doc.outlet)
    if not session["allowed"]:
        blockers.append({"code": "POS_SESSION", "message": session["reason"]})
    current_snapshot = build_kitchen_snapshot([row.as_dict() for row in order_doc.items])
    current_hash = stable_hash(current_snapshot)
    has_active_qty = any(Decimal(str(row.get("qty") or 0)) > 0 for row in current_snapshot.values())
    if has_active_qty and (not order_doc.kitchen_snapshot_hash or current_hash != order_doc.kitchen_snapshot_hash):
        blockers.append({"code": "KITCHEN_UNSYNCED", "message": _("Order changes have not been synchronized to the kitchen.")})
    active_tickets = frappe.get_all(
        "Hotel Kitchen Ticket",
        filters={"restaurant_order": order_doc.name, "status": ["not in", ["Served", "Cancelled"]]},
        fields=["name", "status", "ticket_type", "stock_posting_status"],
    )
    late_or_open = [row for row in active_tickets if row.status not in ("Ready", "Served", "Cancelled")]
    if late_or_open:
        blockers.append({"code": "KITCHEN_OPEN", "message": _("Kitchen tickets are still open."), "tickets": [row.name for row in late_or_open]})
    failed_prints = frappe.get_all(
        "Hotel Restaurant Print Job",
        filters={"reference_doctype": "Hotel Kitchen Ticket", "reference_name": ["in", [row.name for row in active_tickets] or [""]], "status": ["in", ["Failed", "Dead Letter"]]},
        pluck="name",
    )
    if failed_prints:
        blockers.append({"code": "PRINT_FAILED", "message": _("One or more kitchen print jobs failed."), "jobs": failed_prints})
    stock_failed = [row.name for row in active_tickets if row.stock_posting_status == "Failed"]
    if stock_failed:
        blockers.append({"code": "STOCK_FAILED", "message": _("ERPNext recipe stock posting failed for one or more KOTs."), "tickets": stock_failed})
    return {"order": order_doc.name, "allowed": not blockers, "blockers": blockers, "session": session}


def _upsert_alert(property_name: str, outlet: str, candidate: RestaurantAlertCandidate) -> str:
    existing = frappe.db.get_value("Hotel Restaurant Alert", {"fingerprint": candidate.fingerprint}, "name")
    values = {
        "property": property_name,
        "outlet": outlet,
        "alert_type": candidate.alert_type,
        "severity": candidate.severity,
        "status": "Open",
        "reference_doctype": candidate.reference_doctype,
        "reference_name": candidate.reference_name,
        "message": candidate.message,
        "last_seen_at": now_datetime(),
    }
    if existing:
        frappe.db.set_value("Hotel Restaurant Alert", existing, values, update_modified=False)
        return existing
    doc = frappe.get_doc(
        {
            "doctype": "Hotel Restaurant Alert",
            **values,
            "fingerprint": candidate.fingerprint,
            "first_seen_at": now_datetime(),
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def monitor_restaurant_operations() -> dict:
    now = now_datetime()
    seen: set[str] = set()
    created_or_updated = 0
    for ticket in frappe.get_all(
        "Hotel Kitchen Ticket",
        filters={"status": ["in", ["New", "Accepted", "Cooking", "Partially Ready", "Recalled"]]},
        fields=["name", "property", "outlet", "status", "sent_at", "target_ready_at"],
    ):
        if ticket.target_ready_at and now > get_datetime(ticket.target_ready_at):
            candidate = RestaurantAlertCandidate(
                "KOT Delay",
                "High",
                "Hotel Kitchen Ticket",
                ticket.name,
                _("Kitchen ticket {0} exceeded its target ready time.").format(ticket.name),
            )
            seen.add(candidate.fingerprint)
            _upsert_alert(ticket.property, ticket.outlet, candidate)
            created_or_updated += 1
        elif ticket.status == "New" and ticket.sent_at and time_diff_in_seconds(now, get_datetime(ticket.sent_at)) > 300:
            candidate = RestaurantAlertCandidate(
                "KOT Not Accepted",
                "Medium",
                "Hotel Kitchen Ticket",
                ticket.name,
                _("Kitchen ticket {0} has not been accepted within five minutes.").format(ticket.name),
            )
            seen.add(candidate.fingerprint)
            _upsert_alert(ticket.property, ticket.outlet, candidate)
            created_or_updated += 1
    for order in frappe.get_all(
        "Hotel Restaurant Order",
        filters={"status": "Bill Requested"},
        fields=["name", "property", "outlet", "bill_requested_at"],
    ):
        if order.bill_requested_at and time_diff_in_seconds(now, get_datetime(order.bill_requested_at)) > 900:
            candidate = RestaurantAlertCandidate(
                "Bill Delay",
                "Medium",
                "Hotel Restaurant Order",
                order.name,
                _("Restaurant order {0} has waited more than fifteen minutes for billing.").format(order.name),
            )
            seen.add(candidate.fingerprint)
            _upsert_alert(order.property, order.outlet, candidate)
            created_or_updated += 1
    for order in frappe.get_all(
        "Hotel Restaurant Order",
        filters={"status": ["in", ["Confirmed", "In Kitchen", "Ready", "Served", "Bill Requested"]]},
        fields=["name", "property", "outlet", "kitchen_snapshot_hash"],
    ):
        items = frappe.get_all(
            "Hotel Restaurant Order Item",
            filters={"parent": order.name},
            fields=["name", "menu_item", "item_code", "item_name", "qty", "production_unit", "kitchen_station", "course", "notes", "allergy_alert", "preparation_minutes", "status"],
            order_by="idx",
        )
        snapshot = build_kitchen_snapshot(items)
        has_qty = any(Decimal(str(row.get("qty") or 0)) > 0 for row in snapshot.values())
        if has_qty and stable_hash(snapshot) != (order.kitchen_snapshot_hash or ""):
            candidate = RestaurantAlertCandidate(
                "Kitchen Sync Required", "High", "Hotel Restaurant Order", order.name,
                _("Restaurant order {0} has changes not synchronized to the kitchen.").format(order.name),
            )
            seen.add(candidate.fingerprint)
            _upsert_alert(order.property, order.outlet, candidate)
            created_or_updated += 1
    for job in frappe.get_all(
        "Hotel Restaurant Print Job",
        filters={"status": ["in", ["Failed", "Dead Letter"]]},
        fields=["name", "property", "outlet", "reference_doctype", "reference_name"],
    ):
        candidate = RestaurantAlertCandidate(
            "Print Failure",
            "High",
            "Hotel Restaurant Print Job",
            job.name,
            _("Restaurant print job {0} failed.").format(job.name),
        )
        seen.add(candidate.fingerprint)
        _upsert_alert(job.property, job.outlet, candidate)
        created_or_updated += 1
    open_alerts = frappe.get_all("Hotel Restaurant Alert", filters={"status": ["in", ["Open", "Acknowledged"]]}, fields=["name", "fingerprint"])
    resolved = 0
    for row in open_alerts:
        if row.fingerprint not in seen:
            frappe.db.set_value(
                "Hotel Restaurant Alert",
                row.name,
                {"status": "Resolved", "resolved_at": now_datetime()},
                update_modified=False,
            )
            resolved += 1
    return {"active": len(seen), "updated": created_or_updated, "resolved": resolved}

@frappe.whitelist()
def get_restaurant_control_dashboard(property: str, outlet: str | None = None) -> dict:
    _require(SESSION_ROLES | {"Kitchen"})
    from hotel_pms.platform import require_property
    require_property(property)
    filters = {"property": property}
    if outlet:
        filters["outlet"] = outlet
    outlets = frappe.get_all(
        "Hotel Outlet",
        filters={"property": property, "enabled": 1, **({"name": outlet} if outlet else {})},
        fields=["name", "outlet_name", "pos_profile", "require_pos_opening_entry", "cashier_discount_limit"],
        order_by="outlet_name",
    )
    shifts = frappe.get_all(
        "Hotel Cashier Shift",
        filters={**filters, "status": ["in", ["Open", "Closing Review"]]},
        fields=["name", "outlet", "cashier", "status", "pos_profile", "pos_opening_entry", "pos_closing_entry", "erpnext_session_status", "opened_at", "variance"],
        order_by="opened_at desc",
        limit=100,
    )
    tickets = frappe.get_all(
        "Hotel Kitchen Ticket",
        filters={**filters, "status": ["not in", ["Served", "Cancelled"]]},
        fields=["name", "outlet", "restaurant_order", "production_unit", "kitchen_station", "ticket_type", "revision_no", "status", "target_ready_at", "stock_posting_status"],
        order_by="sent_at asc",
        limit=100,
    )
    alerts = frappe.get_all(
        "Hotel Restaurant Alert",
        filters={**filters, "status": ["in", ["Open", "Acknowledged"]]},
        fields=["name", "outlet", "alert_type", "severity", "status", "reference_doctype", "reference_name", "message", "last_seen_at"],
        order_by="severity desc, last_seen_at desc",
        limit=100,
    )
    print_jobs = frappe.get_all(
        "Hotel Restaurant Print Job",
        filters={**filters, "status": ["in", ["Queued", "Printing", "Failed", "Dead Letter"]]},
        fields=["name", "outlet", "purpose", "reference_doctype", "reference_name", "status", "attempts", "network_printer", "last_error"],
        order_by="queued_at desc",
        limit=100,
    )
    return {"outlets": outlets, "shifts": shifts, "tickets": tickets, "alerts": alerts, "print_jobs": print_jobs}
