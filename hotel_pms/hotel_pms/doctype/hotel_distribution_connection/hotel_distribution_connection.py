from __future__ import annotations

import secrets
import frappe
from frappe import _
from frappe.model.document import Document


SHIPPED_PROVIDERS = {"Generic iCal", "Generic JSON"}
ADAPTER_PROVIDERS = {"Channex", "STAAH", "AioSell", "Custom"}


class HotelDistributionConnection(Document):
    def before_insert(self):
        if not self.feed_slug:
            self.feed_slug = secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:18].lower()

    def validate(self):
        expected = "Shipped" if self.provider in SHIPPED_PROVIDERS else "Adapter"
        if self.maturity_status in ("Shipped", "Adapter") and self.maturity_status != expected:
            frappe.throw(_("Provider {0} must use maturity {1} in this release.").format(self.provider, expected))
        if self.provider == "Generic iCal" and self.enabled and not self.endpoint:
            frappe.throw(_("An HTTPS iCal import URL is required before enabling this connection."))
        if self.status in ("Ready", "Live"):
            if not self.enabled:
                frappe.throw(_("Ready or Live connections must be enabled."))
            if self.maturity_status not in ("Shipped", "Adapter"):
                frappe.throw(_("Only Shipped or Adapter integrations can become Ready or Live."))
            if not self.last_test_at or not str(self.last_test_status or "").startswith("OK"):
                frappe.throw(_("A successful connection test is required before Ready or Live status."))
        if self.provider in ADAPTER_PROVIDERS and self.status == "Live":
            frappe.throw(_("Uncertified provider adapter cannot be marked Live in RC8."))
