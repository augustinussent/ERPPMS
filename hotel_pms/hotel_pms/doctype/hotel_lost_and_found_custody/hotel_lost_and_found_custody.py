from frappe.model.document import Document
from hotel_pms.media import validate_photo_fields


class HotelLostAndFoundCustody(Document):
    def validate(self):
        validate_photo_fields(self, {"handover_photo"})
