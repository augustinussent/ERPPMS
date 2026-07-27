import json
import frappe
from frappe import _
from frappe.model.document import Document

class HotelIntelligenceConfig(Document):
    def validate(self):
        if self.mode == "Autopilot" and not self.autopilot_allowed:
            frappe.throw(_("Autopilot cannot be selected until Autopilot Approved is enabled after a dedicated Production Gate review."))
        threshold=float(self.confidence_threshold or 85)
        if threshold < 50 or threshold > 100:
            frappe.throw(_("Confidence Threshold must be between 50 and 100 percent."))
        for field in ("config_json", "model_state_json"):
            value=self.get(field)
            if value:
                try: json.loads(value)
                except Exception: frappe.throw(_("{0} must contain valid JSON.").format(self.meta.get_label(field)))
        duplicate=frappe.db.get_value(self.doctype,{"property":self.property,"agent_type":self.agent_type,"name":["!=",self.name]},"name")
        if duplicate:
            frappe.throw(_("Only one configuration is allowed for each property and agent type."))
