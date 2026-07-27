from __future__ import annotations

import importlib

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from hotel_pms.sync import make_sync_key


def _reference_context(reference_doctype: str, reference_name: str) -> dict:
    doc = frappe.get_doc(reference_doctype, reference_name)
    if reference_doctype == "Hotel Kitchen Ticket":
        return {
            "property": doc.property,
            "outlet": doc.outlet,
            "production_unit": doc.production_unit,
        }
    if reference_doctype in ("POS Invoice", "Sales Invoice"):
        order = doc.get("custom_hotel_restaurant_order")
        if order:
            values = frappe.db.get_value("Hotel Restaurant Order", order, ["property", "outlet"], as_dict=True)
            return {"property": values.property, "outlet": values.outlet, "production_unit": None}
    frappe.throw(_("Unsupported restaurant print reference."))


def resolve_printer_routes(property_name: str, outlet: str, purpose: str, production_unit: str | None = None) -> list[dict]:
    filters = {"property": property_name, "outlet": outlet, "enabled": 1, "purpose": ["in", [purpose, "Both"]]}
    rows = frappe.get_all(
        "Hotel Restaurant Printer Route",
        filters=filters,
        fields=["name", "network_printer", "copies", "priority", "production_unit", "print_format"],
        order_by="priority asc, name asc",
    )
    exact = [row for row in rows if production_unit and row.production_unit == production_unit]
    generic = [row for row in rows if not row.production_unit]
    return exact or generic


def queue_restaurant_print_jobs(reference_doctype: str, reference_name: str, purpose: str, request_key: str) -> dict:
    context = _reference_context(reference_doctype, reference_name)
    routes = resolve_printer_routes(context["property"], context["outlet"], purpose, context.get("production_unit"))
    jobs = []
    for route in routes:
        key = make_sync_key("REST-PRINT", reference_doctype, reference_name, purpose, route.name, request_key)
        existing = frappe.db.get_value("Hotel Restaurant Print Job", {"request_key": key}, "name")
        if existing:
            jobs.append(existing)
            continue
        job = frappe.get_doc(
            {
                "doctype": "Hotel Restaurant Print Job",
                "property": context["property"],
                "outlet": context["outlet"],
                "purpose": purpose,
                "reference_doctype": reference_doctype,
                "reference_name": reference_name,
                "printer_route": route.name,
                "network_printer": route.network_printer,
                "print_format": route.print_format,
                "copies": cint(route.copies or 1),
                "status": "Queued",
                "request_key": key,
                "queued_at": now_datetime(),
            }
        )
        job.insert(ignore_permissions=True)
        jobs.append(job.name)
        frappe.enqueue("hotel_pms.restaurant_printing.process_restaurant_print_job", job=job.name, enqueue_after_commit=True)
    return {"jobs": jobs, "route_count": len(routes)}


def _network_print(doctype: str, name: str, printer: str, print_format: str | None) -> None:
    candidates = [
        ("frappe.printing.doctype.network_printer_settings.network_printer_settings", "print_file"),
        ("frappe.core.doctype.network_printer_settings.network_printer_settings", "print_file"),
    ]
    last_error = None
    for module_name, function_name in candidates:
        try:
            fn = getattr(importlib.import_module(module_name), function_name)
            fn(doctype=doctype, name=name, printer=printer, print_format=print_format)
            return
        except Exception as exc:  # runtime adapter differs slightly between Frappe builds
            last_error = exc
    raise RuntimeError(f"ERPNext network printer adapter is unavailable: {last_error}")


@frappe.whitelist()
def process_restaurant_print_job(job: str) -> dict:
    if frappe.session.user != "Administrator" and not ({"Restaurant Cashier", "Restaurant Captain", "Hotel Manager", "System Manager"} & set(frappe.get_roles())):
        frappe.throw(_("You do not have permission to retry restaurant printing."), frappe.PermissionError)
    rows = frappe.db.sql("select name from `tabHotel Restaurant Print Job` where name=%s for update", job)
    if not rows:
        return {"job": job, "missing": True}
    doc = frappe.get_doc("Hotel Restaurant Print Job", job)
    if doc.status == "Printed":
        return {"job": doc.name, "already_printed": True}
    if doc.status == "Dead Letter":
        return {"job": doc.name, "dead_letter": True}
    doc.status = "Printing"
    doc.attempts = cint(doc.attempts or 0) + 1
    doc.last_attempt_at = now_datetime()
    doc.save(ignore_permissions=True)
    try:
        for _ in range(max(cint(doc.copies or 1), 1)):
            _network_print(doc.reference_doctype, doc.reference_name, doc.network_printer, doc.print_format)
        doc.status = "Printed"
        doc.printed_at = now_datetime()
        doc.last_error = None
    except Exception:
        doc.last_error = frappe.get_traceback()[-2000:]
        doc.status = "Dead Letter" if cint(doc.attempts) >= 5 else "Failed"
        frappe.log_error(frappe.get_traceback(), f"Restaurant print job failed: {doc.name}")
    doc.save(ignore_permissions=True)
    return {"job": doc.name, "status": doc.status, "attempts": doc.attempts}


def retry_failed_restaurant_print_jobs() -> dict:
    jobs = frappe.get_all("Hotel Restaurant Print Job", filters={"status": "Failed", "attempts": ["<", 5]}, pluck="name", limit=100)
    for name in jobs:
        frappe.enqueue("hotel_pms.restaurant_printing.process_restaurant_print_job", job=name)
    return {"queued": len(jobs)}
