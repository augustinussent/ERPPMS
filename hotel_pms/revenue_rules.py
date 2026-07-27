from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Iterable

MONEY = Decimal("0.01")


def dec(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or 0))


def money(value) -> Decimal:
    return dec(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def apply_adjustment(rate, adjustment_type: str | None, adjustment_value) -> Decimal:
    current = dec(rate)
    value = dec(adjustment_value)
    if not adjustment_type or not value:
        return money(current)
    if adjustment_type == "Percentage":
        return money(current * (Decimal("1") + value / Decimal("100")))
    if adjustment_type == "Fixed Amount":
        return money(current + value)
    if adjustment_type == "Fixed Rate":
        return money(value)
    raise ValueError(f"Unsupported adjustment type: {adjustment_type}")


def apply_derived_rate(base_rate, adjustment_type: str | None, adjustment_value, meal_supplement=0) -> Decimal:
    current = dec(base_rate)
    value = dec(adjustment_value)
    if adjustment_type == "Percentage":
        current = current * (Decimal("1") + value / Decimal("100"))
    elif adjustment_type == "Fixed Amount":
        current = current + value
    elif adjustment_type == "Fixed Rate":
        current = value
    elif adjustment_type not in (None, "", "None"):
        raise ValueError(f"Unsupported derived adjustment: {adjustment_type}")
    return money(current + dec(meal_supplement))


def voucher_discount(subtotal, discount_type: str | None, discount_value=0, maximum_discount=0) -> Decimal:
    subtotal = max(dec(subtotal), Decimal("0"))
    value = max(dec(discount_value), Decimal("0"))
    if not discount_type or value == 0:
        return Decimal("0.00")
    if discount_type == "Percentage":
        discount = subtotal * value / Decimal("100")
    elif discount_type == "Fixed Amount":
        discount = value
    else:
        raise ValueError(f"Unsupported discount type: {discount_type}")
    maximum = dec(maximum_discount)
    if maximum > 0:
        discount = min(discount, maximum)
    return money(min(discount, subtotal))


def round_total(value, method: str | None) -> Decimal:
    amount = dec(value)
    increments = {
        "No Rounding": Decimal("0.01"),
        None: Decimal("0.01"),
        "": Decimal("0.01"),
        "Nearest 1": Decimal("1"),
        "Nearest 10": Decimal("10"),
        "Nearest 100": Decimal("100"),
        "Nearest 1000": Decimal("1000"),
    }
    increment = increments.get(method)
    if increment is None:
        raise ValueError(f"Unsupported rounding method: {method}")
    return (amount / increment).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * increment


def tax_breakdown(
    advertised_amount,
    service_rate=0,
    tax_rate=0,
    tax_basis: str = "Net Amount plus Service Charge",
    prices_include_service: bool = False,
    prices_include_tax: bool = False,
    rounding_method: str | None = "No Rounding",
) -> dict[str, Decimal]:
    """Return deterministic display estimates.

    ERPNext Sales Taxes and Charges Template remains authoritative for ledger posting.
    This function is deliberately algebraic so inclusive and exclusive pricing can be
    tested without database state or floating-point drift.
    """
    advertised = dec(advertised_amount)
    sr = dec(service_rate) / Decimal("100")
    tr = dec(tax_rate) / Decimal("100")
    tax_on_service = tax_basis == "Net Amount plus Service Charge"

    if prices_include_service and prices_include_tax:
        denominator = Decimal("1") + sr + tr * (Decimal("1") + sr if tax_on_service else Decimal("1"))
        net = advertised / denominator if denominator else advertised
        service = net * sr
        tax = (net + service if tax_on_service else net) * tr
        gross_before_rounding = advertised
    elif prices_include_service and not prices_include_tax:
        net = advertised / (Decimal("1") + sr) if sr else advertised
        service = advertised - net
        tax = (net + service if tax_on_service else net) * tr
        gross_before_rounding = advertised + tax
    elif prices_include_tax and not prices_include_service:
        denominator = Decimal("1") + tr * (Decimal("1") + sr if tax_on_service else Decimal("1"))
        net = advertised / denominator if denominator else advertised
        service = net * sr
        tax = advertised - net
        gross_before_rounding = advertised + service
    else:
        net = advertised
        service = net * sr
        tax = (net + service if tax_on_service else net) * tr
        gross_before_rounding = net + service + tax

    rounded = round_total(gross_before_rounding, rounding_method)
    return {
        "net": money(net),
        "service_charge": money(service),
        "tax": money(tax),
        "gross_before_rounding": money(gross_before_rounding),
        "rounding_adjustment": money(rounded - gross_before_rounding),
        "gross": money(rounded),
    }


def validate_stay_restrictions(
    *,
    arrival_date: date,
    departure_date: date,
    booking_date: date,
    arrival_rules: dict,
    departure_rules: dict,
    daily_rules: Iterable[dict],
) -> list[str]:
    nights = (departure_date - arrival_date).days
    errors: list[str] = []
    if nights <= 0:
        return ["Departure must be after arrival."]
    min_stay = max(int(r.get("minimum_stay") or 0) for r in daily_rules) if daily_rules else 0
    positive_max = [int(r.get("maximum_stay") or 0) for r in daily_rules if int(r.get("maximum_stay") or 0) > 0]
    max_stay = min(positive_max) if positive_max else 0
    if min_stay and nights < min_stay:
        errors.append(f"Minimum stay is {min_stay} night(s).")
    if max_stay and nights > max_stay:
        errors.append(f"Maximum stay is {max_stay} night(s).")
    if bool(arrival_rules.get("closed_to_arrival")):
        errors.append("Closed to arrival on the selected arrival date.")
    if bool(departure_rules.get("closed_to_departure")):
        errors.append("Closed to departure on the selected departure date.")
    if any(bool(r.get("stop_sell")) for r in daily_rules):
        errors.append("Stop sell applies to one or more stay dates.")
    advance = (arrival_date - booking_date).days
    min_advance = max(int(r.get("minimum_advance_days") or 0) for r in daily_rules) if daily_rules else 0
    positive_max_advance = [int(r.get("maximum_advance_days") or 0) for r in daily_rules if int(r.get("maximum_advance_days") or 0) > 0]
    max_advance = min(positive_max_advance) if positive_max_advance else 0
    if min_advance and advance < min_advance:
        errors.append(f"Booking requires at least {min_advance} advance day(s).")
    if max_advance and advance > max_advance:
        errors.append(f"Booking cannot be made more than {max_advance} day(s) in advance.")
    return errors


def conserve_split(original, transfer, remainder) -> bool:
    return money(original) == money(dec(transfer) + dec(remainder))


def stable_quote_hash(payload: dict) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(normalized.encode("utf-8")).hexdigest()
