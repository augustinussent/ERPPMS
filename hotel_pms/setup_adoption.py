from __future__ import annotations
import frappe

def setup_adoption() -> None:
    for doctype, fields in [
        ("Hotel Channel Connection", ["property", "enabled", "is_default"]),
        ("Hotel Guest Message", ["property", "status", "creation"]),
        ("Hotel Guest Message", ["provider_message_id"]),
    ]:
        try:
            frappe.db.add_index(doctype, fields)
        except Exception:
            pass
    _backfill_properties()

def _backfill_properties() -> None:
    from hotel_pms.localization.registry import hydrate_property_localization
    for name in frappe.get_all("Hotel Property", pluck="name"):
        doc=frappe.get_doc("Hotel Property",name)
        before=(doc.country,doc.currency,doc.localization_code,doc.number_locale,doc.tax_label,doc.tax_id_label)
        hydrate_property_localization(doc)
        after=(doc.country,doc.currency,doc.localization_code,doc.number_locale,doc.tax_label,doc.tax_id_label)
        if before!=after:
            doc.flags.ignore_permissions=True
            doc.save()
