import frappe
from frappe.model.document import Document


class HotelReleaseManifest(Document):
    def before_save(self):
        if self.is_new() or self.flags.get("validation_internal_update"):
            return
        frappe.throw(
            "Release manifests must be changed through controlled validation actions.",
            frappe.PermissionError,
        )

    def on_trash(self):
        if not self.flags.get("validation_internal_update"):
            frappe.throw("Release manifests are immutable audit records.", frappe.PermissionError)
