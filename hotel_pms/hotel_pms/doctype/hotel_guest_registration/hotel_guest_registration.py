import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from hotel_pms.media import validate_photo_fields


class HotelGuestRegistration(Document):
    def validate(self):
        validate_photo_fields(self, {"id_file"})
        if not self.occupants:
            frappe.throw(_("Add at least one registered occupant."))
        primary_count = len([row for row in self.occupants if row.is_primary_guest])
        if primary_count != 1:
            frappe.throw(_("Exactly one occupant must be marked as Primary Guest."))
        if self.id_retention_mode != "Store Image":
            self.id_file = None
        if self.status == "Verified":
            if not self.terms_accepted or not self.privacy_consent:
                frappe.throw(_("Terms acceptance and privacy consent are required before verification."))
            if not self.verified_by:
                self.verified_by = frappe.session.user
            if not self.verified_at:
                self.verified_at = now_datetime()
