import frappe
from frappe.model.document import Document
from frappe.utils import cint


class HotelPMSSettings(Document):
    def validate(self):
        # Duplicate protection is an invariant, not a decorative preference.
        self.strict_erpnext_sync = 1

    def on_update(self):
        frappe.publish_realtime(
            "hotel_pms_photo_policy_changed",
            {"enabled": bool(cint(self.enable_photo_uploads))},
            after_commit=True,
        )
