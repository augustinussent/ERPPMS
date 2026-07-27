from hotel_pms.fnb_rules import (
    aggregate_recipe_requirements,
    derive_kds_ticket_status,
    invoice_updates_stock,
    kds_progress,
    recipe_posting_enabled,
)


def test_kds_status_progression():
    assert derive_kds_ticket_status(["New", "New"]) == "New"
    assert derive_kds_ticket_status(["Accepted", "Accepted"]) == "Accepted"
    assert derive_kds_ticket_status(["Cooking", "Accepted"]) == "Cooking"
    assert derive_kds_ticket_status(["Ready", "Cooking"]) == "Partially Ready"
    assert derive_kds_ticket_status(["Ready", "Ready"]) == "Ready"
    assert derive_kds_ticket_status(["Served", "Served"]) == "Served"
    assert derive_kds_ticket_status(["Cancelled"]) == "Cancelled"
    assert kds_progress(["Ready", "Cooking"]) == 50


def test_exactly_one_inventory_path():
    assert invoice_updates_stock("ERPNext POS Finished Goods") is True
    assert invoice_updates_stock("Recipe Material Issue") is False
    assert invoice_updates_stock("No Stock Posting") is False
    assert recipe_posting_enabled("Recipe Material Issue", True) is True
    assert recipe_posting_enabled("ERPNext POS Finished Goods", True) is False
    assert recipe_posting_enabled("Recipe Material Issue", False) is False


def test_recipe_requirements_aggregate_without_balance_ledger():
    rows = [
        {"ingredient_item":"ING-A","source_warehouse":"Kitchen - H","stock_uom":"Kg","qty":0.2},
        {"ingredient_item":"ING-A","source_warehouse":"Kitchen - H","stock_uom":"Kg","qty":0.3},
        {"ingredient_item":"ING-B","source_warehouse":"Kitchen - H","stock_uom":"Nos","qty":2},
    ]
    result = aggregate_recipe_requirements(rows)
    assert result == [
        {"ingredient_item":"ING-A","source_warehouse":"Kitchen - H","stock_uom":"Kg","qty":0.5},
        {"ingredient_item":"ING-B","source_warehouse":"Kitchen - H","stock_uom":"Nos","qty":2.0},
    ]
