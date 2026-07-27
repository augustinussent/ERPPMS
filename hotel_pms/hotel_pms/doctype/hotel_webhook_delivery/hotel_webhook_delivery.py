import json
from frappe.model.document import Document
class HotelWebhookDelivery(Document):
    def validate(self):
        json.loads(self.payload_json or "{}")
