import json
from frappe.model.document import Document
class HotelMigrationRow(Document):
    def validate(self):
        self.unique_key=f"{self.batch}::{self.row_number}"
        if self.data_json: json.loads(self.data_json)
