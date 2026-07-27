import frappe
from frappe.model.document import Document

from hotel_pms.revenue_rules import tax_breakdown


class HotelCityLedgerCharge(Document):
    def validate(self):
        self.amount = (self.qty or 0) * (self.rate or 0)
        self._set_display_tax_breakdown()

    def _set_display_tax_breakdown(self):
        profile_name = self.tax_profile
        if not profile_name and self.parent:
            property_name = frappe.db.get_value("Hotel City Ledger Folio", self.parent, "property")
            profile_name = (
                frappe.db.get_value("Hotel Property", property_name, "default_hotel_tax_profile")
                if property_name else None
            )
        if not profile_name:
            self.net_amount = self.gross_amount = self.amount
            self.service_charge_amount = self.tax_amount = 0
            return
        profile = frappe.get_cached_doc("Hotel Tax Profile", profile_name)
        row = tax_breakdown(
            self.amount,
            profile.service_charge_rate,
            profile.tax_rate,
            profile.tax_basis,
            bool(profile.prices_include_service_charge),
            bool(profile.prices_include_tax),
            profile.rounding_method,
        )
        self.tax_profile = profile.name
        self.net_amount = row["net"]
        self.service_charge_amount = row["service_charge"]
        self.tax_amount = row["tax"]
        self.gross_amount = row["gross"]
