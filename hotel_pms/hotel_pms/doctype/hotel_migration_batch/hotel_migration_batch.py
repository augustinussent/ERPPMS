import json
from frappe.model.document import Document
class HotelMigrationBatch(Document):
    def validate(self):
        if self.mapping_json: json.loads(self.mapping_json)
