import json
from frappe.model.document import Document
class HotelOnboardingSession(Document):
    def validate(self):
        for field in ("configuration_json","readiness_json","plan_json","applied_steps_json"):
            if self.get(field): json.loads(self.get(field))
