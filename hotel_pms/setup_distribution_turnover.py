from __future__ import annotations

import frappe


def setup_distribution_turnover() -> None:
    indexes = {
        "Hotel Distribution Connection": [["property", "provider", "enabled", "status"]],
        "Hotel Distribution Room Mapping": [["connection", "external_room_id"], ["property", "room_type"]],
        "Hotel Distribution Event": [["property", "status", "arrival_date"], ["room", "arrival_date", "departure_date"], ["room_type", "arrival_date", "departure_date"], ["echo_key"]],
        "Hotel Prearrival Form Template": [["property", "enabled"]],
        "Hotel Prearrival Form Submission": [["property", "reservation", "status"], ["token_record"]],
    }
    for doctype, groups in indexes.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        for fields in groups:
            try:
                frappe.db.add_index(doctype, fields)
            except Exception:
                pass
    try:
        from hotel_pms.intelligence import seed_integration_registry
        seed_integration_registry()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "RC8 integration registry seed failed")
