from decimal import Decimal
from datetime import datetime, timedelta
from hotel_pms.services_rules import allocate_equal, allocation_conserves, derive_table_status, laundry_is_overdue, capacity_available

def test_equal_allocation_conserves_rounding():
    values=allocate_equal("100.00",3)
    assert values==[values[0],values[1],values[2]]
    assert allocation_conserves("100.00",values)
    assert values[-1]==values[0]+Decimal("0.01")

def test_table_statuses():
    assert derive_table_status("In Kitchen")=="In Kitchen"
    assert derive_table_status("Billed")=="Cleaning"
    assert derive_table_status("Cancelled")=="Available"

def test_laundry_overdue():
    now=datetime(2026,7,21,12,0)
    assert laundry_is_overdue("In Process",now-timedelta(minutes=1),now)
    assert not laundry_is_overdue("Ready",now-timedelta(minutes=1),now)

def test_capacity():
    assert capacity_available(10,7,3)
    assert not capacity_available(10,8,3)
