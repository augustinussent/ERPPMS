from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

TERMINAL_ITEM_STATUSES = {"Served", "Cancelled"}


def derive_kds_ticket_status(statuses):
    values = [s for s in statuses if s]
    active = [s for s in values if s != "Cancelled"]
    if not active:
        return "Cancelled" if values else "New"
    if all(s == "Served" for s in active):
        return "Served"
    if all(s in {"Ready", "Served"} for s in active):
        return "Ready"
    if any(s in {"Ready", "Served"} for s in active):
        return "Partially Ready"
    if any(s == "Cooking" for s in active):
        return "Cooking"
    if all(s == "Accepted" for s in active):
        return "Accepted"
    if any(s == "Recalled" for s in active):
        return "Recalled"
    return "New"


def kds_progress(statuses):
    active = [s for s in statuses if s != "Cancelled"]
    if not active:
        return 100
    finished = sum(1 for s in active if s in {"Ready", "Served"})
    return round((finished / len(active)) * 100)


def invoice_updates_stock(policy: str) -> bool:
    """Exactly one inventory path may own the movement."""
    return (policy or "ERPNext POS Finished Goods") == "ERPNext POS Finished Goods"


def recipe_posting_enabled(policy: str, global_enabled: bool) -> bool:
    return bool(global_enabled and policy == "Recipe Material Issue")


def aggregate_recipe_requirements(lines):
    """Aggregate snapshots by (item, warehouse, uom) without inventing a balance ledger."""
    result = defaultdict(Decimal)
    for line in lines:
        qty = Decimal(str(line.get("qty") or 0))
        if qty <= 0:
            continue
        key = (line.get("ingredient_item"), line.get("source_warehouse"), line.get("stock_uom"))
        result[key] += qty
    return [
        {
            "ingredient_item": item,
            "source_warehouse": warehouse,
            "stock_uom": uom,
            "qty": float(qty),
        }
        for (item, warehouse, uom), qty in sorted(result.items())
    ]
