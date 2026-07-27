from __future__ import annotations

import frappe

FINANCIAL = (
    "Sales Invoice", "POS Invoice", "Payment Entry", "Journal Entry",
    "Purchase Invoice", "Stock Entry", "GL Entry", "Stock Ledger Entry",
)


def _counts() -> dict[str, int]:
    return {doctype: frappe.db.count(doctype) for doctype in FINANCIAL}


def run_rc9_bench_smoke() -> dict:
    required = (
        "Hotel Kitchen Production Unit", "Hotel Restaurant Printer Route",
        "Hotel Restaurant Print Job", "Hotel Restaurant Table Cluster",
        "Hotel Restaurant Alert",
    )
    missing = [doctype for doctype in required if not frappe.db.exists("DocType", doctype)]
    before = _counts()
    from hotel_pms.setup_restaurant_controls import setup_restaurant_controls
    setup_restaurant_controls()
    from hotel_pms.restaurant_controls import monitor_restaurant_operations
    monitor_result = monitor_restaurant_operations()
    after = _counts()
    deltas = {key: after[key] - before[key] for key in before}
    custom_fields = {}
    for doctype in ("POS Opening Entry", "POS Closing Entry"):
        custom_fields[doctype] = all(
            frappe.get_meta(doctype).has_field(field)
            for field in ("custom_hotel_cashier_shift", "custom_hotel_property", "custom_hotel_outlet")
        )
    result = {
        "passed": not missing and all(custom_fields.values()) and not any(deltas.values()),
        "missing_doctypes": missing,
        "custom_fields": custom_fields,
        "monitor": monitor_result,
        "financial_stock_deltas": deltas,
        "version": __import__("hotel_pms").__version__,
    }
    if not result["passed"]:
        raise RuntimeError(result)
    return result
