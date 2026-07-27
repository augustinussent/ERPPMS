from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any


def confidence_allows_execution(mode: str, confidence: float, threshold_percent: float, autopilot_allowed: bool) -> bool:
    """Autopilot is opt-in twice: mode and an explicit production approval flag."""
    return (
        mode == "Autopilot"
        and bool(autopilot_allowed)
        and float(confidence or 0) >= float(threshold_percent or 0)
    )


def numeric_payload(value: Any) -> Any:
    """Keep only numeric leaves so free-form guest/operator text never reaches an explanation model."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text.replace(",", ""))
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    if isinstance(value, list):
        rows = [numeric_payload(item) for item in value]
        rows = [item for item in rows if item is not None]
        return rows or None
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            filtered = numeric_payload(item)
            if filtered is not None:
                result[str(key)] = filtered
        return result or None
    return None


def _collect_numbers(value: Any, result: set[float] | None = None) -> set[float]:
    if result is None:
        result = set()
    if isinstance(value, bool) or value is None:
        return result
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        if math.isfinite(number):
            result.add(number)
    elif isinstance(value, str):
        try:
            number = float(value.replace(",", "").strip())
        except ValueError:
            return result
        if math.isfinite(number):
            result.add(number)
    elif isinstance(value, list):
        for item in value:
            _collect_numbers(item, result)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_numbers(item, result)
    return result


_NUMBER_RE = re.compile(r"([-+]?)(?:Rp\s*)?(\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?)(\s*%)?", re.IGNORECASE)


def significant_numbers(text: str) -> list[float]:
    values: list[float] = []
    for match in _NUMBER_RE.finditer(text or ""):
        sign = -1 if match.group(1) == "-" else 1
        raw = match.group(2)
        is_percent = bool(match.group(3))
        # Indonesian thousands separators and common decimal notation are normalized conservatively.
        if raw.count(".") > 1 or raw.count(",") > 1:
            raw = raw.replace(".", "").replace(",", "")
        elif "." in raw and "," in raw:
            raw = raw.replace(".", "").replace(",", ".")
        elif "," in raw:
            head, tail = raw.rsplit(",", 1)
            raw = head.replace(",", "") + ("." + tail if len(tail) <= 2 else tail)
        try:
            number = sign * float(raw)
        except ValueError:
            continue
        if is_percent or abs(number) >= 25:
            values.append(number)
    return values


def number_is_supported(value: float, supported: set[float]) -> bool:
    magnitude = abs(float(value))
    for item in supported:
        candidate = abs(float(item))
        tolerance = max(0.5, candidate * 0.02)
        if abs(magnitude - candidate) <= tolerance:
            return True
        if candidate <= 1 and abs(magnitude - candidate * 100) <= max(0.5, candidate * 2):
            return True
    return False


def ground_explanation(numbers: Any, rationale: str, suggestions: list[str] | None = None) -> dict:
    supported = _collect_numbers(numbers)
    rationale_ok = all(number_is_supported(number, supported) for number in significant_numbers(rationale))
    safe_suggestions = [
        text
        for text in (suggestions or [])
        if all(number_is_supported(number, supported) for number in significant_numbers(text))
    ]
    return {"grounded": rationale_ok, "rationale": rationale if rationale_ok else "", "suggestions": safe_suggestions}


def payment_correction_plan(
    *,
    docstatus: int,
    payment_type: str | None,
    hotel_transaction_type: str | None,
    original_amount: float,
    refundable_amount: float,
) -> dict:
    """Return the only legal operational actions. ERPNext remains the money ledger."""
    allowed: list[str] = []
    reason = ""
    if int(docstatus or 0) == 0:
        allowed = ["Delete Draft"]
        reason = "Draft Payment Entry has no GL impact and may be deleted after approval."
    elif int(docstatus or 0) == 2:
        allowed = ["Manual Review"]
        reason = "Cancelled Payment Entry cannot be corrected by creating another automatic action."
    elif hotel_transaction_type == "Deposit" and payment_type == "Receive" and float(refundable_amount or 0) > 0:
        allowed = ["Create Refund", "Manual Review"]
        reason = "Submitted hotel deposit may be refunded through a new ERPNext Payment Entry draft."
    else:
        allowed = ["Manual Review"]
        reason = "The current state requires Finance review; no automatic voucher mutation is legal."
    return {
        "allowed_actions": allowed,
        "reason": reason,
        "original_amount": max(float(original_amount or 0), 0.0),
        "maximum_refundable": max(float(refundable_amount or 0), 0.0),
    }


def severity_rank(severity: str) -> int:
    return {"Critical": 0, "Warning": 1, "Info": 2}.get(severity, 3)
