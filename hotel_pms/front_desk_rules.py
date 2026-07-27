from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

MONEY = Decimal("0.01")


@dataclass(frozen=True)
class CancellationQuote:
    gross_stay_amount: Decimal
    fee_amount: Decimal
    refundable_amount: Decimal
    days_before_arrival: int
    free_cancellation_applies: bool


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def room_nights(arrival: date, departure: date) -> int:
    return max((departure - arrival).days, 0)


def stay_total(arrival: date, departure: date, nightly_rates: Iterable[float | Decimal]) -> Decimal:
    nights = room_nights(arrival, departure)
    return money(sum((money(rate) for rate in nightly_rates), Decimal("0")) * nights)


def calculate_fee(base_amount, fee_type: str, fee_value=0, first_night_amount=0) -> Decimal:
    base = money(base_amount)
    fee_type = (fee_type or "None").strip()
    if fee_type == "None":
        return money(0)
    if fee_type == "Fixed Amount":
        return min(base, money(fee_value))
    if fee_type == "Percentage":
        return min(base, money(base * Decimal(str(fee_value or 0)) / Decimal("100")))
    if fee_type == "First Night":
        return min(base, money(first_night_amount))
    if fee_type == "Full Stay":
        return base
    raise ValueError(f"Unsupported fee type: {fee_type}")


def quote_cancellation(
    *,
    arrival: date,
    departure: date,
    nightly_rates: Iterable[float | Decimal],
    reference_date: date,
    free_cancellation_days: int,
    fee_type: str,
    fee_value=0,
    deposit_received=0,
) -> CancellationQuote:
    rates = list(nightly_rates)
    gross = stay_total(arrival, departure, rates)
    days_before = (arrival - reference_date).days
    free = days_before >= int(free_cancellation_days or 0)
    first_night = sum((money(rate) for rate in rates), Decimal("0"))
    fee = money(0) if free else calculate_fee(gross, fee_type, fee_value, first_night)
    refundable = max(money(deposit_received) - fee, money(0))
    return CancellationQuote(gross, fee, refundable, days_before, free)
