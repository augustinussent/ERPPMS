import re
import frappe
from frappe import _
from frappe.model.document import Document

class HotelChannelConnection(Document):
    def validate(self):
        if self.channel != "WhatsApp" or self.provider != "Meta Cloud API":
            frappe.throw(_("Only the governed Meta Cloud API WhatsApp provider is supported in this release."))
        if not re.fullmatch(r"v\d+\.\d+", (self.graph_api_version or "").strip()):
            frappe.throw(_("Graph API Version must be pinned in vXX.X format."))
        if not str(self.phone_number_id or "").isdigit():
            frappe.throw(_("Phone Number ID must contain digits only."))
        self.request_timeout_seconds=max(5,min(int(self.request_timeout_seconds or 15),60))
        if self.enabled:
            for field in ("access_token","webhook_verify_token","app_secret"):
                if not self.get(field) and not self.get_password(field,raise_exception=False):
                    frappe.throw(_("{0} is required before enabling the connection.").format(self.meta.get_label(field)))
        if self.is_default and self.property:
            other=frappe.db.get_value(self.doctype,{"property":self.property,"channel":self.channel,"is_default":1,"name":["!=",self.name]},"name")
            if other: frappe.throw(_("Only one default WhatsApp connection is allowed per property."))
