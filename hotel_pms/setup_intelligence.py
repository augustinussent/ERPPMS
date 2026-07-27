from __future__ import annotations

import frappe

ROLE = "Hotel Intelligence Analyst"


def setup_intelligence() -> None:
    if not frappe.db.exists("Role", ROLE):
        frappe.get_doc({"doctype": "Role", "role_name": ROLE}).insert(ignore_permissions=True)
    indexes = {
        "Hotel Intelligence Config": [["property", "agent_type"]],
        "Hotel Intelligence Run": [["property", "agent_type", "business_date", "status"]],
        "Hotel Intelligence Decision": [["property", "agent_type", "status"], ["intelligence_run"]],
        "Hotel Night Audit Finding": [["property", "business_date", "status", "severity"], ["reference_doctype", "reference_name"]],
        "Hotel Payment Correction": [["property", "payment_entry", "status"]],
        "Hotel Integration Connection": [["property", "integration", "status"]],
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
        frappe.log_error(frappe.get_traceback(), "Hotel integration registry seed failed")
