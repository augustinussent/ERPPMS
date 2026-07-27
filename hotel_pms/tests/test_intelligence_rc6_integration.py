import frappe
from frappe.tests import IntegrationTestCase


class TestIntelligenceRC6Integration(IntegrationTestCase):
    def test_rc6_doctypes_are_installed(self):
        for doctype in (
            "Hotel Intelligence Config",
            "Hotel Intelligence Run",
            "Hotel Intelligence Decision",
            "Hotel Night Audit Finding",
            "Hotel Payment Correction",
            "Hotel Integration Definition",
            "Hotel Integration Connection",
        ):
            self.assertTrue(frappe.db.exists("DocType", doctype), doctype)

    def test_registry_seed_does_not_create_financial_documents(self):
        from hotel_pms.intelligence import seed_integration_registry

        doctypes = ("Sales Invoice", "POS Invoice", "Payment Entry", "Journal Entry", "Purchase Invoice", "Stock Entry")
        before = {doctype: frappe.db.count(doctype) for doctype in doctypes}
        result = seed_integration_registry()
        after = {doctype: frappe.db.count(doctype) for doctype in doctypes}
        self.assertEqual(before, after)
        self.assertGreaterEqual(result["total"], 5)
