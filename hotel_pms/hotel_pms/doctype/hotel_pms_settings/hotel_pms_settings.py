import frappe
from frappe.model.document import Document
from frappe.utils import cint


class HotelPMSSettings(Document):
    def validate(self):
        # Duplicate protection is an invariant, not a decorative preference.
        self.strict_erpnext_sync = 1
        self.disk_warning_percent = min(max(cint(self.disk_warning_percent or 80), 1), 99)
        self.disk_critical_percent = min(max(cint(self.disk_critical_percent or 90), self.disk_warning_percent + 1), 100)
        self.webhook_max_attempts = min(max(cint(self.webhook_max_attempts or 8), 1), 20)
        self.migration_max_rows = min(max(cint(self.migration_max_rows or 10000), 100), 100000)

    def on_update(self):
        frappe.publish_realtime(
            "hotel_pms_photo_policy_changed",
            {"enabled": bool(cint(self.enable_photo_uploads))},
            after_commit=True,
        )
