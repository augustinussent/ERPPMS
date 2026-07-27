from __future__ import annotations
from decimal import Decimal, InvalidOperation

PASSING = {"Passed", "Not Applicable"}

def money_variance(expected, actual):
    try:
        return abs(Decimal(str(expected or 0)) - Decimal(str(actual or 0)))
    except (InvalidOperation, ValueError):
        return Decimal("Infinity")

def threshold_status(value, maximum, warning_ratio=0.8):
    value=float(value or 0); maximum=float(maximum or 0)
    if maximum < 0: return "Failed"
    if value > maximum: return "Failed"
    if maximum and value > maximum*warning_ratio: return "Warning"
    return "Passed"

def summarize_checks(checks):
    blockers=sum(1 for c in checks if c.get("mandatory") and c.get("status") not in PASSING)
    warnings=sum(1 for c in checks if c.get("status")=="Warning")
    passed=sum(1 for c in checks if c.get("status") in PASSING)
    return {"blockers":blockers,"warnings":warnings,"passed":passed}

def gate_status(checks, signoffs):
    s=summarize_checks(checks)
    if s["blockers"]: return "Blocked"
    if any(x.get("status")=="Rejected" for x in signoffs): return "Rejected"
    if signoffs and all(x.get("status")=="Approved" for x in signoffs): return "Approved"
    return "Ready for Sign-off"
