import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_rc9_version_patch_and_setup_are_registered():
    assert '1.0.0rc9' in (ROOT / 'hotel_pms/__init__.py').read_text()
    assert 'hotel_pms.patches.v1_0_rc9.setup_restaurant_controls' in (ROOT / 'hotel_pms/patches.txt').read_text()
    assert 'setup_restaurant_controls()' in (ROOT / 'hotel_pms/install.py').read_text()


def test_new_operational_modules_do_not_create_financial_or_stock_documents():
    text = '\n'.join((ROOT / 'hotel_pms' / name).read_text() for name in [
        'restaurant_controls.py', 'restaurant_printing.py', 'restaurant_controls_rules.py'
    ])
    for doctype in ('Sales Invoice', 'POS Invoice', 'Payment Entry', 'Journal Entry', 'Purchase Invoice', 'Stock Entry'):
        assert f'"doctype": "{doctype}"' not in text


def test_all_new_top_level_doctypes_are_property_scoped():
    platform = (ROOT / 'hotel_pms/platform.py').read_text()
    for doctype in (
        'Hotel Kitchen Production Unit', 'Hotel Restaurant Printer Route', 'Hotel Restaurant Print Job',
        'Hotel Restaurant Table Cluster', 'Hotel Restaurant Alert',
    ):
        assert f"'{doctype}':'property'" in platform


def test_rc9_production_gate_controls_exist():
    source = (ROOT / 'hotel_pms/production_gate.py').read_text()
    for code in ('RESTAURANT_SESSION_CONTROL', 'KITCHEN_DELTA_CONTROL', 'RESTAURANT_PRINT_CONTROL'):
        assert code in source


def test_cashier_shift_links_to_erpnext_pos_session_documents():
    path = ROOT / 'hotel_pms/hotel_pms/doctype/hotel_cashier_shift/hotel_cashier_shift.json'
    fields = {f['fieldname']: f for f in json.loads(path.read_text())['fields']}
    assert fields['pos_opening_entry']['options'] == 'POS Opening Entry'
    assert fields['pos_closing_entry']['options'] == 'POS Closing Entry'
    setup = (ROOT / 'hotel_pms/setup_restaurant_controls.py').read_text()
    assert 'custom_hotel_cashier_shift' in setup
    assert 'POS Opening Entry' in setup and 'POS Closing Entry' in setup


def test_kitchen_delta_stock_consumption_only_accepts_add_actions():
    source = (ROOT / 'hotel_pms/fnb_inventory.py').read_text()
    assert 'getattr(item, "delta_action", "Add") != "Add"' in source
    controls = (ROOT / 'hotel_pms/restaurant_controls.py').read_text()
    assert 'action_bucket == "Add"' in controls
    assert 'does not auto-reverse ERPNext stock' in controls


def test_discount_is_written_to_erpnext_pos_invoice_not_custom_ledger():
    source = (ROOT / 'hotel_pms/services.py').read_text()
    assert 'doc.additional_discount_percentage=flt(split_doc.discount_percentage)' in source
    assert 'split_doc.discount_amount=flt(doc.discount_amount or 0)' in source
    assert 'validate_discount(split_doc, outlet)' in source


def test_fractional_quantity_uses_erpnext_uom_rule():
    source = (ROOT / 'hotel_pms/restaurant_controls.py').read_text()
    assert 'must_be_whole_number' in source
    order = (ROOT / 'hotel_pms/hotel_pms/doctype/hotel_restaurant_order/hotel_restaurant_order.py').read_text()
    assert 'validate_order_item_uom' in order


def test_incremental_kot_has_revision_and_delta_fields():
    ticket = json.loads((ROOT / 'hotel_pms/hotel_pms/doctype/hotel_kitchen_ticket/hotel_kitchen_ticket.json').read_text())
    fields = {f['fieldname']: f for f in ticket['fields']}
    for name in ('production_unit', 'ticket_type', 'revision_no', 'source_snapshot_hash'):
        assert name in fields
    item = json.loads((ROOT / 'hotel_pms/hotel_pms/doctype/hotel_kitchen_ticket_item/hotel_kitchen_ticket_item.json').read_text())
    assert any(f['fieldname'] == 'delta_action' for f in item['fields'])


def test_restaurant_control_console_is_packaged():
    page = ROOT / 'hotel_pms/hotel_pms/page/hotel_restaurant_control'
    assert (page / 'hotel_restaurant_control.json').exists()
    assert (page / 'hotel_restaurant_control.js').exists()


def test_print_queue_is_idempotent_and_retry_bounded():
    source = (ROOT / 'hotel_pms/restaurant_printing.py').read_text()
    assert 'make_sync_key("REST-PRINT"' in source
    assert 'cint(doc.attempts) >= 5' in source
    assert 'Dead Letter' in source
