from frappe.model.document import Document
from hotel_pms.media import validate_photo_fields


class HotelRoomInspectionItem(Document):
    def validate(self):
        validate_photo_fields(self, {"photo"})
