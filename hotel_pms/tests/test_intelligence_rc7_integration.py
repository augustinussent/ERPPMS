import frappe
from frappe.tests import IntegrationTestCase


class TestIntelligenceRC7Integration(IntegrationTestCase):
    def test_payment_correction_refundable_is_capped_by_source_payment(self):
        from hotel_pms.intelligence_rules import payment_correction_plan

        plan = payment_correction_plan(
            docstatus=1,
            payment_type="Receive",
            hotel_transaction_type="Deposit",
            original_amount=100,
            refundable_amount=500,
        )
        self.assertEqual(plan["maximum_refundable"], 100)

    def test_enabled_failed_integration_is_a_gate_blocker(self):
        from hotel_pms.intelligence_rules import integration_readiness_reasons

        reasons = integration_readiness_reasons(
            maturity_status="Shipped",
            connection_status="Failed",
            last_test_status="Failed",
            last_tested_at=frappe.utils.now_datetime(),
            failed_mandatory_checks=[],
        )
        self.assertTrue(reasons)
