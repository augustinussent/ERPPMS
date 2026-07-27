from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class LocalizationContext:
    code: str
    country: str
    currency: str
    number_locale: str
    tax_label: str
    tax_id_label: str
    tax_registration_number: str | None = None
    transaction_scope: str = "Room"

class HotelLocalizationPack:
    code = "generic"
    countries: tuple[str, ...] = ()
    default_locale = "en"
    default_currency = ""
    tax_label = "Tax"
    tax_id_label = "Tax ID"

    def context(self, property_doc, transaction_scope: str = "Room") -> LocalizationContext:
        return LocalizationContext(
            code=self.code,
            country=property_doc.get("country") or "",
            currency=property_doc.get("currency") or self.default_currency or "",
            number_locale=property_doc.get("number_locale") or self.default_locale,
            tax_label=property_doc.get("tax_label") or self.tax_label,
            tax_id_label=property_doc.get("tax_id_label") or self.tax_id_label,
            tax_registration_number=property_doc.get("tax_registration_number"),
            transaction_scope=transaction_scope,
        )

    def validate_property(self, property_doc) -> list[str]:
        return []

    def validate_tax_profile(self, property_doc, profile_doc) -> list[str]:
        return []
