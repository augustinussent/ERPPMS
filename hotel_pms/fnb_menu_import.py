from __future__ import annotations

import csv
import io
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from hotel_pms.sync import make_sync_key

ROLES = {"Restaurant Captain", "Hotel Manager", "System Manager"}


def _require():
    if not (set(frappe.get_roles()) & ROLES):
        frappe.throw(_("You do not have permission to import restaurant menus."), frappe.PermissionError)


def _parse_recipe(value):
    if not value:
        return []
    try:
        rows = json.loads(value)
    except json.JSONDecodeError:
        raise ValueError("recipe_json must be a JSON array")
    if not isinstance(rows, list):
        raise ValueError("recipe_json must be a JSON array")
    return rows


@frappe.whitelist()
def preview_menu_import(outlet: str, csv_text: str, request_key: str, source_filename: str | None = None) -> dict:
    _require()
    outlet_doc = frappe.get_doc("Hotel Outlet", outlet)
    key = make_sync_key("MENU-IMPORT", outlet, request_key)
    existing = frappe.db.get_value("Hotel Menu Import Batch", {"request_key": key}, "name")
    if existing:
        return {"batch": existing, "already_created": True}
    limit = cint(frappe.db.get_single_value("Hotel PMS Settings", "menu_import_max_rows") or 1000)
    reader = csv.DictReader(io.StringIO(csv_text or ""))
    rows = list(reader)
    if not rows:
        frappe.throw(_("The CSV file contains no data rows."))
    if len(rows) > limit:
        frappe.throw(_("The CSV exceeds the configured maximum of {0} rows.").format(limit))
    batch = frappe.get_doc({
        "doctype": "Hotel Menu Import Batch",
        "property": outlet_doc.property,
        "outlet": outlet,
        "status": "Preview",
        "request_key": key,
        "source_filename": source_filename,
    })
    counts = {"Insert": 0, "Update": 0, "Skip": 0, "Reject": 0}
    for idx, raw in enumerate(rows, start=2):
        row = {str(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        item_code = row.get("item_code") or row.get("erpnext_item")
        menu_name = row.get("menu_name") or row.get("name")
        action, message = "Insert", ""
        recipe_json = row.get("recipe_json") or ""
        try:
            if not item_code or not frappe.db.exists("Item", item_code):
                raise ValueError("ERPNext Item does not exist")
            if not menu_name:
                menu_name = frappe.db.get_value("Item", item_code, "item_name")
            rate = flt(row.get("rate"))
            if rate < 0:
                raise ValueError("rate cannot be negative")
            recipe = _parse_recipe(recipe_json)
            for rec in recipe:
                ingredient = rec.get("item_code") or rec.get("ingredient_item")
                if not ingredient or not frappe.db.exists("Item", ingredient):
                    raise ValueError(f"recipe ingredient {ingredient or '-'} does not exist")
                if flt(rec.get("qty")) <= 0:
                    raise ValueError(f"recipe ingredient {ingredient} requires positive qty")
            exists = frappe.db.get_value("Hotel Outlet Menu Item", {"outlet": outlet, "item_code": item_code}, "name")
            action = "Update" if exists else "Insert"
        except ValueError as exc:
            action, message = "Reject", str(exc)
        counts[action] += 1
        batch.append("rows", {
            "row_no": idx,
            "action": action,
            "status": "Preview",
            "item_code": item_code,
            "menu_name": menu_name,
            "rate": flt(row.get("rate")),
            "kitchen_station": row.get("kitchen_station") or "Main Kitchen",
            "course": row.get("course") or "Main",
            "allergy_alert": row.get("allergy_alert"),
            "preparation_minutes": cint(row.get("preparation_minutes") or 15),
            "recipe_json": recipe_json,
            "message": message,
        })
    batch.insert_count, batch.update_count, batch.skip_count, batch.reject_count = counts["Insert"], counts["Update"], counts["Skip"], counts["Reject"]
    batch.insert(ignore_permissions=True)
    return {"batch": batch.name, "already_created": False, "counts": counts}


@frappe.whitelist()
def commit_menu_import(batch: str) -> dict:
    _require()
    frappe.db.sql("select name from `tabHotel Menu Import Batch` where name=%s for update", batch)
    doc = frappe.get_doc("Hotel Menu Import Batch", batch)
    if doc.status == "Committed":
        return {"batch": doc.name, "already_processed": True}
    if doc.status != "Preview":
        frappe.throw(_("Only a preview batch can be committed."))
    failed = 0
    for row in doc.rows:
        if row.action == "Reject":
            continue
        try:
            name = frappe.db.get_value("Hotel Outlet Menu Item", {"outlet": doc.outlet, "item_code": row.item_code}, "name")
            menu = frappe.get_doc("Hotel Outlet Menu Item", name) if name else frappe.new_doc("Hotel Outlet Menu Item")
            menu.outlet = doc.outlet
            menu.item_code = row.item_code
            menu.menu_name = row.menu_name
            menu.rate = row.rate
            menu.kitchen_station = row.kitchen_station
            menu.course = row.course
            menu.allergy_alert = row.allergy_alert
            menu.preparation_minutes = row.preparation_minutes
            recipe = _parse_recipe(row.recipe_json)
            menu.recipe_enabled = 1 if recipe else 0
            menu.set("recipe_items", [])
            for rec in recipe:
                item_code = rec.get("item_code") or rec.get("ingredient_item")
                menu.append("recipe_items", {
                    "ingredient_item": item_code,
                    "qty_per_menu_unit": flt(rec.get("qty")),
                    "source_warehouse": rec.get("warehouse"),
                    "notes": rec.get("notes"),
                })
            menu.save(ignore_permissions=True) if name else menu.insert(ignore_permissions=True)
            row.menu_item = menu.name
            row.status = "Committed"
        except Exception as exc:
            row.status = "Failed"
            row.message = str(exc)[:1000]
            failed += 1
    doc.status = "Partially Failed" if failed else "Committed"
    doc.committed_at = now_datetime()
    doc.committed_by = frappe.session.user
    doc.save(ignore_permissions=True)
    return {"batch": doc.name, "status": doc.status, "failed": failed}
