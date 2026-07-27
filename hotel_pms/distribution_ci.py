from __future__ import annotations

import frappe

FINANCIAL = ("Sales Invoice", "POS Invoice", "Payment Entry", "Journal Entry", "Purchase Invoice", "Stock Entry", "GL Entry", "Stock Ledger Entry")


def _counts():
    return {doctype: frappe.db.count(doctype) for doctype in FINANCIAL}


def run_rc8_bench_smoke():
    required = (
        "Hotel Distribution Connection", "Hotel Distribution Room Mapping", "Hotel Distribution Event",
        "Hotel Prearrival Form Template", "Hotel Prearrival Form Submission",
    )
    missing = [doctype for doctype in required if not frappe.db.exists("DocType", doctype)]
    before = _counts()
    from hotel_pms.setup_distribution_turnover import setup_distribution_turnover
    setup_distribution_turnover()
    after = _counts()
    deltas = {key: after[key] - before[key] for key in before}
    result = {
        "passed": not missing and not any(deltas.values()),
        "missing_doctypes": missing,
        "financial_stock_deltas": deltas,
        "version": __import__('hotel_pms').__version__,
    }
    if not result["passed"]:
        raise RuntimeError(result)
    return result
