from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, nowdate

from hotel_pms.fnb_rules import aggregate_recipe_requirements, invoice_updates_stock, recipe_posting_enabled
from hotel_pms.notifications import notify_roles
from hotel_pms.sync import make_sync_key, create_document_once

ALLOWED_ROLES = {"Restaurant Captain", "Hotel Manager", "System Manager"}


def _require():
    if not (set(frappe.get_roles()) & ALLOWED_ROLES):
        frappe.throw(_("You do not have permission to post recipe consumption."), frappe.PermissionError)


def invoice_stock_fields(outlet_doc):
    update_stock = 1 if invoice_updates_stock(outlet_doc.inventory_posting_policy) else 0
    return {
        "update_stock": update_stock,
        "set_warehouse": outlet_doc.warehouse if update_stock else None,
    }


def should_post_recipe(outlet_doc) -> bool:
    enabled = cint(frappe.db.get_single_value("Hotel PMS Settings", "enable_recipe_stock_posting"))
    return recipe_posting_enabled(outlet_doc.inventory_posting_policy, enabled)


def validate_inventory_configuration(outlet_doc) -> None:
    if outlet_doc.inventory_posting_policy == "Recipe Material Issue":
        enabled = cint(frappe.db.get_single_value("Hotel PMS Settings", "enable_recipe_stock_posting"))
        if not enabled:
            frappe.throw(_("Recipe Material Issue is selected for this outlet, but global recipe stock posting is disabled."))
        if not (outlet_doc.recipe_source_warehouse or outlet_doc.warehouse):
            frappe.throw(_("Recipe Material Issue requires a source warehouse."))


def queue_ticket_stock_posting(ticket: str) -> None:
    outlet = frappe.db.get_value("Hotel Kitchen Ticket", ticket, "outlet")
    if not outlet:
        return
    outlet_doc = frappe.get_doc("Hotel Outlet", outlet)
    if not should_post_recipe(outlet_doc):
        frappe.db.set_value("Hotel Kitchen Ticket", ticket, "stock_posting_status", "Not Required", update_modified=False)
        return
    frappe.db.set_value("Hotel Kitchen Ticket", ticket, "stock_posting_status", "Queued", update_modified=False)
    frappe.enqueue(
        "hotel_pms.fnb_inventory._post_ticket_recipe_consumption_job",
        ticket=ticket,
        queue="short",
        enqueue_after_commit=True,
        job_name=f"hotel-recipe-stock:{ticket}",
    )


def _recipe_lines(ticket_doc, outlet_doc):
    lines = []
    for item in ticket_doc.items:
        if not item.menu_item:
            continue
        menu = frappe.get_doc("Hotel Outlet Menu Item", item.menu_item)
        if not cint(menu.recipe_enabled):
            continue
        for recipe in menu.recipe_items:
            qty = Decimal(str(recipe.qty_per_menu_unit or 0)) * Decimal(str(item.qty or 0))
            if qty <= 0:
                continue
            ingredient = frappe.db.get_value(
                "Item", recipe.ingredient_item, ["is_stock_item", "stock_uom", "disabled"], as_dict=True
            )
            if not ingredient or ingredient.disabled or not ingredient.is_stock_item:
                frappe.throw(_("Recipe ingredient {0} must be an enabled ERPNext stock Item.").format(recipe.ingredient_item))
            warehouse = recipe.source_warehouse or outlet_doc.recipe_source_warehouse or outlet_doc.warehouse
            if not warehouse:
                frappe.throw(_("A source warehouse is required for recipe ingredient {0}.").format(recipe.ingredient_item))
            warehouse_company = frappe.db.get_value("Warehouse", warehouse, "company")
            if warehouse_company and warehouse_company != outlet_doc.company:
                frappe.throw(_("Recipe warehouse {0} belongs to another company.").format(warehouse))
            lines.append({
                "menu_item": item.menu_item,
                "order_item_row": item.order_item_row,
                "ingredient_item": recipe.ingredient_item,
                "qty": float(qty),
                "stock_uom": ingredient.stock_uom,
                "source_warehouse": warehouse,
            })
    return lines



@frappe.whitelist()
def post_ticket_recipe_consumption(ticket: str, submit=None) -> dict:
    _require()
    return _post_ticket_recipe_consumption(ticket, submit=submit)


def _post_ticket_recipe_consumption_job(ticket: str) -> dict:
    return _post_ticket_recipe_consumption(ticket, submit=None)


def _post_ticket_recipe_consumption(ticket: str, submit=None) -> dict:
    frappe.db.sql("select name from `tabHotel Kitchen Ticket` where name=%s for update", ticket)
    ticket_doc = frappe.get_doc("Hotel Kitchen Ticket", ticket)
    outlet_doc = frappe.get_doc("Hotel Outlet", ticket_doc.outlet)
    if not should_post_recipe(outlet_doc):
        ticket_doc.db_set("stock_posting_status", "Not Required", update_modified=False)
        return {"ticket": ticket, "posted": False, "reason": "Recipe posting is disabled"}
    base_key = make_sync_key("KOT-STOCK", ticket_doc.name)

    try:
        raw_lines = _recipe_lines(ticket_doc, outlet_doc)
        requirements = aggregate_recipe_requirements(raw_lines)
        if not requirements:
            ticket_doc.db_set({"stock_posting_status": "Not Required", "stock_sync_key": base_key, "stock_error": None}, update_modified=False)
            _refresh_order_reconciliation(ticket_doc.restaurant_order)
            return {"ticket": ticket, "posted": False, "reason": "No recipe-enabled items"}

        ticket_doc.set("ingredient_consumptions", [])
        for line in raw_lines:
            ticket_doc.append("ingredient_consumptions", line)
        ticket_doc.stock_error = None
        ticket_doc.save(ignore_permissions=True)

        def build_stock_entry():
            stock_doc = frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Issue",
                "purpose": "Material Issue",
                "company": outlet_doc.company,
                "posting_date": nowdate(),
                "custom_hotel_kitchen_ticket": ticket_doc.name,
                "custom_hotel_restaurant_order": ticket_doc.restaurant_order,
                "remarks": _("Recipe consumption for KOT {0}").format(ticket_doc.name),
            })
            for req in requirements:
                stock_doc.append("items", {
                    "item_code": req["ingredient_item"],
                    "s_warehouse": req["source_warehouse"],
                    "qty": req["qty"],
                    "uom": req["stock_uom"],
                    "stock_uom": req["stock_uom"],
                    "conversion_factor": 1,
                    "cost_center": outlet_doc.cost_center,
                })
            return stock_doc

        stock, already_created = create_document_once(
            base_key=base_key,
            operation="Restaurant recipe material issue",
            source_doctype="Hotel Kitchen Ticket",
            source_name=ticket_doc.name,
            target_doctype="Stock Entry",
            build_document=build_stock_entry,
            payload=requirements,
            ignore_permissions=True,
        )
        sync_key = stock.custom_hotel_sync_key
        ticket_doc.db_set({"stock_entry": stock.name, "stock_sync_key": sync_key, "stock_posting_status": "Submitted" if stock.docstatus == 1 else "Draft Created", "stock_error": None}, update_modified=False)
        requested_submit = cint(submit) if submit is not None else outlet_doc.recipe_stock_entry_mode == "Submit"
        if requested_submit and stock.docstatus == 0:
            try:
                stock.flags.ignore_permissions = True
                stock.submit()
            except Exception as exc:
                ticket_doc.db_set({"stock_posting_status": "Failed", "stock_error": str(exc)[:1000]}, update_modified=False)
                notify_roles(
                    ["Restaurant Captain", "Hotel Manager", "System Manager"],
                    property_name=ticket_doc.property,
                    subject=_("Recipe stock posting failed"),
                    message=_("KOT {0} created Stock Entry {1}, but submission failed: {2}").format(ticket_doc.name, stock.name, str(exc)[:300]),
                    document_type="Hotel Kitchen Ticket",
                    document_name=ticket_doc.name,
                    dedupe_key=f"kot-stock-failed:{ticket_doc.name}:{stock.name}",
                )
                return {"ticket": ticket, "stock_entry": stock.name, "submitted": False, "error": str(exc)}
        _sync_ticket_from_stock_entry(ticket_doc, stock.name, stock.docstatus)
        return {"ticket": ticket, "stock_entry": stock.name, "already_created": already_created, "submitted": stock.docstatus == 1}
    except Exception as exc:
        ticket_doc.db_set({"stock_posting_status": "Failed", "stock_error": str(exc)[:1000], "stock_sync_key": base_key}, update_modified=False)
        _refresh_order_reconciliation(ticket_doc.restaurant_order)
        notify_roles(
            ["Restaurant Captain", "Hotel Manager", "System Manager"],
            property_name=ticket_doc.property,
            subject=_("Recipe stock posting failed"),
            message=_("KOT {0}: {1}").format(ticket_doc.name, str(exc)[:500]),
            document_type="Hotel Kitchen Ticket",
            document_name=ticket_doc.name,
            dedupe_key=f"kot-stock-failed:{ticket_doc.name}:{base_key}",
        )
        frappe.log_error(frappe.get_traceback(), "Hotel recipe stock posting")
        return {"ticket": ticket, "posted": False, "error": str(exc)}


def _refresh_order_reconciliation(order_name: str) -> None:
    if not order_name or not frappe.db.exists("Hotel Restaurant Order", order_name):
        return
    tickets = frappe.get_all(
        "Hotel Kitchen Ticket",
        filters={"restaurant_order": order_name, "status": ["!=", "Cancelled"]},
        fields=["name", "stock_posting_status"],
    )
    incomplete = [row.name for row in tickets if row.stock_posting_status not in ("Submitted", "Not Required")]
    values = {
        "stock_reconciliation_status": "Pending" if incomplete else "Reconciled",
        "stock_reconciliation_note": (_("Pending KOT stock posting: {0}").format(", ".join(incomplete)) if incomplete else _("All active KOT recipe Stock Entries are reconciled.")),
    }
    frappe.db.set_value("Hotel Restaurant Order", order_name, values, update_modified=False)


def _sync_ticket_from_stock_entry(ticket_doc, stock_entry, docstatus):
    status = "Submitted" if docstatus == 1 else "Draft Created"
    values = {"stock_entry": stock_entry, "stock_posting_status": status, "stock_error": None}
    if docstatus == 1:
        values["stock_posted_at"] = now_datetime()
    ticket_doc.db_set(values, update_modified=False)
    for row in ticket_doc.items:
        frappe.db.set_value(
            "Hotel Restaurant Order Item",
            row.order_item_row,
            {"stock_posted": 1 if docstatus == 1 else 0, "stock_kitchen_ticket": ticket_doc.name},
            update_modified=False,
        )
    _refresh_order_reconciliation(ticket_doc.restaurant_order)


def on_stock_entry_submit(doc, method=None):
    ticket = getattr(doc, "custom_hotel_kitchen_ticket", None)
    if ticket and frappe.db.exists("Hotel Kitchen Ticket", ticket):
        _sync_ticket_from_stock_entry(frappe.get_doc("Hotel Kitchen Ticket", ticket), doc.name, 1)


def on_stock_entry_cancel(doc, method=None):
    ticket = getattr(doc, "custom_hotel_kitchen_ticket", None)
    if not ticket or not frappe.db.exists("Hotel Kitchen Ticket", ticket):
        return
    ticket_doc = frappe.get_doc("Hotel Kitchen Ticket", ticket)
    ticket_doc.db_set({"stock_posting_status": "Cancelled", "stock_error": _("ERPNext Stock Entry was cancelled.")}, update_modified=False)
    for row in ticket_doc.items:
        frappe.db.set_value("Hotel Restaurant Order Item", row.order_item_row, "stock_posted", 0, update_modified=False)
    frappe.db.set_value("Hotel Restaurant Order", ticket_doc.restaurant_order, {
        "stock_reconciliation_status": "Pending",
        "stock_reconciliation_note": _("Stock Entry {0} was cancelled; repost or reconcile the KOT.").format(doc.name),
    }, update_modified=False)
    notify_roles(
        ["Restaurant Captain", "Hotel Manager", "System Manager"],
        property_name=ticket_doc.property,
        subject=_("Restaurant stock reconciliation required"),
        message=_("ERPNext Stock Entry {0} for KOT {1} was cancelled.").format(doc.name, ticket_doc.name),
        document_type="Hotel Kitchen Ticket",
        document_name=ticket_doc.name,
        dedupe_key=f"kot-stock-cancelled:{doc.name}",
    )
