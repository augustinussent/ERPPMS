import re
import frappe
from frappe import _
from frappe.model.document import Document
from hotel_pms.media import validate_photo_fields


class HotelProperty(Document):
    def validate(self):
        validate_photo_fields(self,{"public_hero_image"})
        if self.public_booking_enabled:
            if not self.public_slug:
                frappe.throw(_("Public Slug is required when the property is published."))
            self.public_slug=(self.public_slug or "").strip().lower()
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",self.public_slug):
                frappe.throw(_("Public Slug may contain lowercase letters, numbers, and single hyphens only."))
            public_images=[self.public_hero_image]+[row.image for row in (self.public_gallery or []) if row.enabled and row.image]
            if any(not str(url).startswith("/files/") for url in public_images if url):
                frappe.throw(_("Images used by the public booking page must be public /files attachments."))
