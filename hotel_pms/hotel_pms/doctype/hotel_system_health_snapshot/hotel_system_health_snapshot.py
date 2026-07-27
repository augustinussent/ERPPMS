import json
from frappe.model.document import Document
class HotelSystemHealthSnapshot(Document):
    def validate(self):
        if self.details_json: json.loads(self.details_json)
