from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Iterable, Mapping

QTY_QUANTUM = Decimal("0.001")
MONEY_QUANTUM = Decimal("0.01")


def decimal_qty(value: object) -> Decimal:
    """Return a stable three-decimal restaurant quantity."""
    return Decimal(str(value or 0)).quantize(QTY_QUANTUM, rounding=ROUND_HALF_UP)


def decimal_money(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: object) -> str:
    return sha256(stable_json(value).encode("utf-8")).hexdigest()


def build_kitchen_snapshot(items: Iterable[Mapping[str, object]]) -> dict[str, dict[str, object]]:
    """Build an immutable, row-keyed snapshot used for incremental KOT deltas.

    The order-item row name is the primary key. A deterministic fallback is kept
    for import/test payloads where the row has not yet received a Frappe name.
    """
    snapshot: dict[str, dict[str, object]] = {}
    for idx, raw in enumerate(items, start=1):
        if str(raw.get("status") or "") == "Cancelled":
            qty = Decimal("0")
        else:
            qty = decimal_qty(raw.get("qty"))
        key = str(raw.get("name") or raw.get("row_key") or f"ROW-{idx}")
        snapshot[key] = {
            "qty": str(qty),
            "item_code": str(raw.get("item_code") or ""),
            "item_name": str(raw.get("item_name") or ""),
            "menu_item": str(raw.get("menu_item") or ""),
            "production_unit": str(raw.get("production_unit") or raw.get("kitchen_station") or "Main Kitchen"),
            "course": str(raw.get("course") or "Main"),
            "notes": str(raw.get("notes") or ""),
            "allergy_alert": str(raw.get("allergy_alert") or ""),
            "preparation_minutes": int(raw.get("preparation_minutes") or 0),
        }
    return snapshot


def diff_kitchen_snapshots(
    previous: Mapping[str, Mapping[str, object]] | None,
    current: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    """Return deterministic Add/Reduce/Modify deltas between kitchen snapshots."""
    previous = previous or {}
    deltas: list[dict[str, object]] = []
    for row_key in sorted(set(previous) | set(current)):
        before = previous.get(row_key) or {}
        after = current.get(row_key) or before
        before_qty = decimal_qty(before.get("qty"))
        after_qty = decimal_qty((current.get(row_key) or {}).get("qty"))
        before_unit = str(before.get("production_unit") or "")
        after_unit = str(after.get("production_unit") or "")
        if row_key in current and row_key in previous and before_unit != after_unit and before_qty > 0 and after_qty > 0:
            deltas.append({**before, "row_key": row_key, "action": "Reduce", "qty": str(before_qty)})
            deltas.append({**after, "row_key": row_key, "action": "Add", "qty": str(after_qty)})
            continue
        qty_delta = (after_qty - before_qty).quantize(QTY_QUANTUM)
        if qty_delta > 0:
            deltas.append({**after, "row_key": row_key, "action": "Add", "qty": str(qty_delta)})
        elif qty_delta < 0:
            deltas.append({**before, "row_key": row_key, "action": "Reduce", "qty": str(abs(qty_delta))})
        elif row_key in current and row_key in previous:
            comparable = ("notes", "course", "allergy_alert")
            if any(str(before.get(k) or "") != str(after.get(k) or "") for k in comparable):
                deltas.append({**after, "row_key": row_key, "action": "Modify", "qty": str(after_qty)})
    return deltas


def ticket_type_for_actions(actions: Iterable[str], first_revision: bool = False) -> str:
    values = set(actions)
    if first_revision and values <= {"Add"}:
        return "New"
    if values == {"Add"}:
        return "Addition"
    if values <= {"Reduce"}:
        return "Cancellation"
    if values <= {"Modify"}:
        return "Modification"
    return "Mixed Change"


def discount_decision(percent: object, threshold: object, authorized: bool) -> dict[str, object]:
    value = Decimal(str(percent or 0))
    limit = Decimal(str(threshold or 0))
    if value < 0 or value > 100:
        return {"allowed": False, "requires_approval": False, "reason": "Discount must be between 0 and 100 percent."}
    requires = value > limit if limit >= 0 else value > 0
    if requires and not authorized:
        return {"allowed": False, "requires_approval": True, "reason": "Manager approval is required for this discount."}
    return {"allowed": True, "requires_approval": requires, "reason": ""}


def validate_fractional_quantity(qty: object, whole_number_only: bool) -> dict[str, object]:
    value = decimal_qty(qty)
    if value <= 0:
        return {"valid": False, "quantity": value, "reason": "Quantity must be greater than zero."}
    if whole_number_only and value != value.to_integral_value():
        return {"valid": False, "quantity": value, "reason": "This item's UOM only permits whole-number quantities."}
    return {"valid": True, "quantity": value, "reason": ""}


def allocate_payment_by_rounded_totals(totals: Iterable[object], payment: object) -> list[Decimal]:
    """Allocate a combined payment without losing cents.

    The first n-1 allocations are capped at each rounded invoice total; the final
    invoice receives the exact residual. This mirrors URY's merged-bill fix while
    keeping each ERPNext invoice financially independent.
    """
    values = [decimal_money(v) for v in totals]
    remaining = decimal_money(payment)
    out: list[Decimal] = []
    for idx, total in enumerate(values):
        if idx == len(values) - 1:
            amount = max(Decimal("0.00"), remaining)
        else:
            amount = min(max(Decimal("0.00"), remaining), total)
        amount = decimal_money(amount)
        out.append(amount)
        remaining = decimal_money(remaining - amount)
    return out


def session_gate(*, outlet_requires_opening: bool, shift_open: bool, pos_opening_submitted: bool) -> dict[str, object]:
    if not outlet_requires_opening:
        return {"allowed": True, "reason": ""}
    if not shift_open:
        return {"allowed": False, "reason": "Open a Hotel Cashier Shift before restaurant operations."}
    if not pos_opening_submitted:
        return {"allowed": False, "reason": "Link a submitted ERPNext POS Opening Entry to the cashier shift."}
    return {"allowed": True, "reason": ""}


def table_cluster_decision(rows: Iterable[Mapping[str, object]], outlet: str, order: str) -> dict[str, object]:
    seen: set[str] = set()
    for row in rows:
        name = str(row.get("name") or "")
        if not name or name in seen:
            return {"allowed": False, "reason": "Table selections must be unique."}
        seen.add(name)
        if str(row.get("outlet") or "") != outlet:
            return {"allowed": False, "reason": "All merged tables must belong to the order outlet."}
        active = str(row.get("active_order") or "")
        if active and active != order:
            return {"allowed": False, "reason": f"Table {name} already belongs to another active order."}
        if str(row.get("status") or "Available") in {"Out of Service", "Cleaning"}:
            return {"allowed": False, "reason": f"Table {name} is not available for merging."}
    if len(seen) < 2:
        return {"allowed": False, "reason": "Select at least two tables."}
    return {"allowed": True, "reason": "", "tables": sorted(seen)}


@dataclass(frozen=True)
class RestaurantAlertCandidate:
    alert_type: str
    severity: str
    reference_doctype: str
    reference_name: str
    message: str

    @property
    def fingerprint(self) -> str:
        return stable_hash(
            {
                "alert_type": self.alert_type,
                "reference_doctype": self.reference_doctype,
                "reference_name": self.reference_name,
            }
        )
