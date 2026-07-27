from __future__ import annotations
import re
import frappe
from frappe import _
from hotel_pms.localization.generic import GenericPack
from hotel_pms.localization.indonesia import IndonesiaPack

_PACKS={"generic":GenericPack(),"indonesia":IndonesiaPack()}
_COUNTRY={country.lower():pack for pack in _PACKS.values() for country in pack.countries}

def get_pack(property_doc):
    requested=(property_doc.get("localization_pack") or "Auto").strip().lower()
    if requested and requested != "auto":
        return _PACKS.get(requested, _PACKS["generic"])
    return _COUNTRY.get((property_doc.get("country") or "").strip().lower(), _PACKS["generic"])

def hydrate_property_localization(property_doc):
    """Hydrate display/localization fields from ERPNext Company.

    Company remains authoritative for country, currency and tax ID. The PMS
    localization layer only derives labels/locale and never creates accounting
    rows or overrides ERPNext tax templates.
    """
    if property_doc.get("company"):
        company=frappe.db.get_value(
            "Company", property_doc.company, ["country", "default_currency", "tax_id"], as_dict=True
        ) or {}
        property_doc.country=company.get("country") or property_doc.get("country")
        property_doc.currency=company.get("default_currency") or property_doc.get("currency")
        property_doc.tax_registration_number=company.get("tax_id") or property_doc.get("tax_registration_number")
    pack=get_pack(property_doc)
    if not property_doc.get("number_locale"):
        property_doc.number_locale=pack.default_locale
    property_doc.tax_label=pack.tax_label
    property_doc.tax_id_label=pack.tax_id_label
    property_doc.localization_code=pack.code
    return pack

def get_localization_context(property_name: str, transaction_scope: str="Room") -> dict:
    prop=frappe.get_doc("Hotel Property",property_name)
    pack=get_pack(prop)
    return pack.context(prop,transaction_scope).__dict__

def _account_company(account):
    return frappe.db.get_value("Account",account,"company") if account else None

def validate_tax_profile_mapping(profile_doc, property_doc=None, *, throw=True) -> list[str]:
    prop=property_doc or frappe.get_doc("Hotel Property",profile_doc.property)
    warnings=[]; errors=[]
    if profile_doc.get("tax_rate") or profile_doc.get("service_charge_rate"):
        if not profile_doc.get("sales_taxes_template"):
            errors.append(_("Sales Taxes and Charges Template ERPNext wajib diisi saat tarif pajak/service charge tidak nol."))
        if not profile_doc.get("accountant_reviewed"):
            errors.append(_("Profil pajak harus ditandai telah ditinjau Finance sebelum digunakan untuk quote."))
    if profile_doc.get("sales_taxes_template"):
        company=frappe.db.get_value("Sales Taxes and Charges Template",profile_doc.sales_taxes_template,"company")
        if company and company != prop.company:
            errors.append(_("Template pajak ERPNext berasal dari Company lain."))
    for field in ("service_charge_account","tax_account","rounding_account"):
        account=profile_doc.get(field)
        if account and _account_company(account) != prop.company:
            errors.append(_("Account pada {0} harus berasal dari Company properti.").format(profile_doc.meta.get_label(field)))
    pack=get_pack(prop)
    warnings.extend(pack.validate_tax_profile(prop,profile_doc))
    if errors and throw: frappe.throw("<br>".join(errors),title=_("ERPNext Tax Mapping Invalid"))
    return errors+warnings


def resolve_invoice_tax_context(property_name: str, profile_names=None) -> dict:
    """Resolve exactly one PMS profile to exactly one ERPNext tax template.

    The PMS may calculate display breakdowns, but ERPNext owns tax posting.
    A single invoice cannot silently combine different PMS tax profiles because
    one Sales Taxes and Charges Template would then be applied to every line.
    """
    prop=frappe.get_doc("Hotel Property",property_name)
    provided=list(profile_names or [])
    default_profile=prop.default_hotel_tax_profile
    names={str(name or default_profile) for name in provided if (name or default_profile)}
    if not provided and default_profile:
        names={default_profile}
    if len(names)>1:
        frappe.throw(
            _("Charges use multiple Hotel Tax Profiles. Split them into separate ERPNext invoices."),
            title=_("Mixed Tax Profiles"),
        )
    profile_name=next(iter(names),None)
    template=None
    if profile_name:
        profile=frappe.get_doc("Hotel Tax Profile",profile_name)
        if profile.property != prop.name:
            frappe.throw(_("Hotel Tax Profile belongs to a different property."))
        validate_tax_profile_mapping(profile,prop,throw=True)
        template=profile.sales_taxes_template
    else:
        template=prop.default_sales_taxes_template
    if template:
        company=frappe.db.get_value("Sales Taxes and Charges Template",template,"company")
        if company and company != prop.company:
            frappe.throw(_("ERPNext tax template belongs to a different Company."))
    return {"tax_profile":profile_name,"sales_taxes_template":template}

@frappe.whitelist()
def localization_context(property: str, transaction_scope: str="Room") -> dict:
    frappe.get_doc("Hotel Property",property).check_permission("read")
    return get_localization_context(property,transaction_scope)
