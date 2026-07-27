import frappe
from frappe.tests import IntegrationTestCase


class TestRestaurantControlsRC9Integration(IntegrationTestCase):
    def test_pos_session_bridge_fields_exist(self):
        for doctype in ("POS Opening Entry", "POS Closing Entry"):
            meta = frappe.get_meta(doctype)
            for field in ("custom_hotel_cashier_shift", "custom_hotel_property", "custom_hotel_outlet"):
                self.assertTrue(meta.has_field(field))

    def test_operational_monitor_does_not_create_financial_documents(self):
        financial = ("Sales Invoice", "POS Invoice", "Payment Entry", "Journal Entry", "Purchase Invoice", "Stock Entry")
        before = {doctype: frappe.db.count(doctype) for doctype in financial}
        from hotel_pms.restaurant_controls import monitor_restaurant_operations
        monitor_restaurant_operations()
        after = {doctype: frappe.db.count(doctype) for doctype in financial}
        self.assertEqual(before, after)

    def test_rc9_production_gate_functions_return_structured_results(self):
        from hotel_pms.production_gate import (
            kitchen_delta_control_check,
            restaurant_print_control_check,
            restaurant_session_control_check,
        )
        for result in (
            restaurant_session_control_check(),
            kitchen_delta_control_check(),
            restaurant_print_control_check(),
        ):
            self.assertIn("blockers", result)
            self.assertIsInstance(result["blockers"], int)
