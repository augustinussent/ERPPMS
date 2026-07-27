from frappe.model.document import Document

from hotel_pms.media import validate_photo_fields


class HotelHousekeepingTask(Document):
    def validate(self):
        validate_photo_fields(self, {"before_photo", "after_photo"})
