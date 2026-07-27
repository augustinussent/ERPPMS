import json
import frappe
from frappe import _
from frappe.model.document import Document
class HotelIntegrationConnection(Document):
    def validate(self):
        if self.configuration_json:
            try: json.loads(self.configuration_json)
            except Exception: frappe.throw(_("Configuration JSON must contain valid JSON."))
        duplicate=frappe.db.get_value(self.doctype,{"property":self.property,"integration":self.integration,"name":["!=",self.name]},"name")
        if duplicate: frappe.throw(_("Only one connection per property and integration is allowed."))
        if self.status in ("Ready", "Live"):
            if not self.enabled:
                frappe.throw(_("Ready or Live integrations must be enabled."))
            definition=frappe.get_doc("Hotel Integration Definition",self.integration)
            if definition.maturity_status not in ("Shipped","Adapter"):
                frappe.throw(_("Only Shipped or Adapter integrations can be marked Ready or Live."))
            if self.last_test_status != "Passed" or not self.last_tested_at:
                frappe.throw(_("A successful Test Connection result is required before Ready or Live status."))
            blockers=[r.check_code for r in self.go_live_checks if r.mandatory and r.status!="Passed"]
            if blockers: frappe.throw(_("Mandatory go-live checks are not passed: {0}").format(", ".join(blockers)))
