from frappe.model.document import Document
from hotel_pms.media import validate_photo_fields


class HotelHousekeepingChecklistItem(Document):
    def validate(self):
        validate_photo_fields(self, {"photo"})
