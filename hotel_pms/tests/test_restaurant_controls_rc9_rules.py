from decimal import Decimal

from hotel_pms.restaurant_controls_rules import (
    RestaurantAlertCandidate,
    allocate_payment_by_rounded_totals,
    build_kitchen_snapshot,
    diff_kitchen_snapshots,
    discount_decision,
    session_gate,
    table_cluster_decision,
    ticket_type_for_actions,
    validate_fractional_quantity,
)


def _item(name="ROW-1", qty=1, **extra):
    return {"name": name, "qty": qty, "item_code": "FOOD-1", "item_name": "Food", "production_unit": "Hot Kitchen", **extra}


def test_first_snapshot_creates_add_delta_and_new_ticket():
    current = build_kitchen_snapshot([_item(qty=1.5)])
    delta = diff_kitchen_snapshots({}, current)
    assert delta[0]["action"] == "Add"
    assert delta[0]["qty"] == "1.500"
    assert ticket_type_for_actions(["Add"], first_revision=True) == "New"


def test_incremental_quantity_addition_only_sends_delta():
    before = build_kitchen_snapshot([_item(qty=1)])
    after = build_kitchen_snapshot([_item(qty=2.25)])
    assert diff_kitchen_snapshots(before, after)[0]["qty"] == "1.250"


def test_reduction_is_cancellation_delta_not_negative_quantity():
    before = build_kitchen_snapshot([_item(qty=3)])
    after = build_kitchen_snapshot([_item(qty=1)])
    delta = diff_kitchen_snapshots(before, after)[0]
    assert delta["action"] == "Reduce"
    assert delta["qty"] == "2.000"
    assert ticket_type_for_actions(["Reduce"]) == "Cancellation"


def test_cancelled_order_row_becomes_full_reduction():
    before = build_kitchen_snapshot([_item(qty=2)])
    after = build_kitchen_snapshot([_item(qty=2, status="Cancelled")])
    assert diff_kitchen_snapshots(before, after)[0]["qty"] == "2.000"


def test_note_change_is_modification_without_quantity_delta():
    before = build_kitchen_snapshot([_item(notes="no salt")])
    after = build_kitchen_snapshot([_item(notes="low salt")])
    delta = diff_kitchen_snapshots(before, after)[0]
    assert delta["action"] == "Modify"
    assert delta["qty"] == "1.000"



def test_production_unit_move_creates_cancel_for_old_and_add_for_new():
    before = build_kitchen_snapshot([_item(qty=2, production_unit="Cold Kitchen")])
    after = build_kitchen_snapshot([_item(qty=2, production_unit="Hot Kitchen")])
    deltas = diff_kitchen_snapshots(before, after)
    assert [(d["action"], d["production_unit"], d["qty"]) for d in deltas] == [
        ("Reduce", "Cold Kitchen", "2.000"),
        ("Add", "Hot Kitchen", "2.000"),
    ]


def test_whole_number_uom_rejects_fractional_quantity():
    result = validate_fractional_quantity("1.5", whole_number_only=True)
    assert not result["valid"]


def test_fractional_uom_rounds_to_three_decimals():
    result = validate_fractional_quantity("1.2346", whole_number_only=False)
    assert result["valid"]
    assert result["quantity"] == Decimal("1.235")


def test_discount_above_cashier_limit_requires_manager():
    result = discount_decision(12, 10, authorized=False)
    assert not result["allowed"] and result["requires_approval"]
    assert discount_decision(12, 10, authorized=True)["allowed"]


def test_discount_cannot_exceed_one_hundred_percent():
    assert not discount_decision(101, 100, authorized=True)["allowed"]


def test_session_gate_requires_both_shift_and_erpnext_opening():
    assert not session_gate(outlet_requires_opening=True, shift_open=False, pos_opening_submitted=False)["allowed"]
    assert not session_gate(outlet_requires_opening=True, shift_open=True, pos_opening_submitted=False)["allowed"]
    assert session_gate(outlet_requires_opening=True, shift_open=True, pos_opening_submitted=True)["allowed"]


def test_session_gate_can_be_disabled_per_outlet():
    assert session_gate(outlet_requires_opening=False, shift_open=False, pos_opening_submitted=False)["allowed"]


def test_table_cluster_requires_same_outlet_unique_available_tables():
    rows = [
        {"name": "T1", "outlet": "OUT-1", "status": "Occupied", "active_order": "ORD-1"},
        {"name": "T2", "outlet": "OUT-1", "status": "Available", "active_order": ""},
    ]
    assert table_cluster_decision(rows, "OUT-1", "ORD-1")["allowed"]
    assert not table_cluster_decision(rows + [rows[0]], "OUT-1", "ORD-1")["allowed"]


def test_table_cluster_rejects_other_active_order():
    rows = [
        {"name": "T1", "outlet": "OUT-1", "status": "Occupied", "active_order": "ORD-1"},
        {"name": "T2", "outlet": "OUT-1", "status": "Occupied", "active_order": "ORD-2"},
    ]
    assert not table_cluster_decision(rows, "OUT-1", "ORD-1")["allowed"]


def test_combined_payment_allocation_preserves_exact_residual():
    allocated = allocate_payment_by_rounded_totals([10.01, 20.02, 30.03], 60.06)
    assert allocated == [Decimal("10.01"), Decimal("20.02"), Decimal("30.03")]
    assert sum(allocated) == Decimal("60.06")


def test_alert_fingerprint_is_stable_and_ignores_message_wording():
    a = RestaurantAlertCandidate("KOT Delay", "High", "Hotel Kitchen Ticket", "KOT-1", "late")
    b = RestaurantAlertCandidate("KOT Delay", "Critical", "Hotel Kitchen Ticket", "KOT-1", "very late")
    assert a.fingerprint == b.fingerprint
