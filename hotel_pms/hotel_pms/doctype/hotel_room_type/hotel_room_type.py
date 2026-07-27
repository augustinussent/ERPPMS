import frappe
from frappe import _
from frappe.model.document import Document
from hotel_pms.media import validate_photo_fields


class HotelRoomType(Document):
    def validate(self):
        validate_photo_fields(self,{"public_image"})
        if self.public_enabled and self.public_image and not str(self.public_image).startswith("/files/"):
            frappe.throw(_("Public room-type images must be public /files attachments."))
