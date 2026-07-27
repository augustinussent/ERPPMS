from __future__ import annotations
from hotel_pms.localization.base import HotelLocalizationPack

class IndonesiaPack(HotelLocalizationPack):
    code = "indonesia"
    countries = ("Indonesia",)
    default_locale = "id-ID"
    default_currency = "IDR"
    tax_label = "PBJT"
    tax_id_label = "NPWP"

    def validate_property(self, property_doc) -> list[str]:
        warnings=[]
        if property_doc.get("currency") and property_doc.currency != "IDR":
            warnings.append("Properti Indonesia biasanya menggunakan mata uang perusahaan IDR. Periksa konfigurasi Company ERPNext.")
        if not property_doc.get("tax_registration_number"):
            warnings.append("Nomor identitas pajak properti belum diisi. Pastikan NPWP/identitas yang sesuai diverifikasi Finance.")
        return warnings

    def validate_tax_profile(self, property_doc, profile_doc) -> list[str]:
        warnings=[]
        if profile_doc.get("transaction_scope") in ("Room", "F&B", "All") and not profile_doc.get("accountant_reviewed"):
            warnings.append("Tarif PBJT dan perlakuan service charge harus ditinjau Finance sesuai pemerintah daerah properti.")
        return warnings
