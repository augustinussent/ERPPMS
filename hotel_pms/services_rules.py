from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP

MONEY=Decimal("0.01")
def dec(v): return v if isinstance(v,Decimal) else Decimal(str(v or 0))
def money(v): return dec(v).quantize(MONEY,rounding=ROUND_HALF_UP)

def allocate_equal(total, shares):
    shares=int(shares)
    if shares<=0: raise ValueError("Shares must be positive")
    total=money(total); base=money(total/Decimal(shares)); result=[base]*shares
    result[-1]=money(total-sum(result[:-1],Decimal("0")))
    return result

def allocation_conserves(original, allocations):
    return money(original)==money(sum((dec(v) for v in allocations),Decimal("0")))

def derive_table_status(order_status, has_reservation=False):
    mapping={"Draft":"Occupied","Pending Confirmation":"Occupied","Confirmed":"Occupied","In Kitchen":"In Kitchen","Ready":"In Kitchen","Served":"Occupied","Bill Requested":"Bill Requested","Billed":"Cleaning","Cancelled":"Available"}
    return mapping.get(order_status,"Reserved" if has_reservation else "Available")

def laundry_is_overdue(status, promised_ready_at, now):
    return bool(promised_ready_at and status not in {"Ready","Returned","Billed","Cancelled"} and promised_ready_at < now)

def capacity_available(capacity, already_booked, requested):
    return max(int(capacity or 0)-int(already_booked or 0),0) >= int(requested or 0)
