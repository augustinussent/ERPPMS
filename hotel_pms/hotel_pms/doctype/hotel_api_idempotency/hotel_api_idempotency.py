import json
from frappe.model.document import Document
class HotelAPIIdempotency(Document):
    def validate(self):
        if self.response_json: json.loads(self.response_json)
