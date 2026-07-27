from hotel_pms.adoption_rules import normalize_phone,FINANCIAL_DOCTYPES
from hotel_pms.localization.indonesia import IndonesiaPack
from hotel_pms.localization.generic import GenericPack

def test_indonesia_pack_identity():
    pack=IndonesiaPack();assert pack.code=="indonesia";assert pack.default_currency=="IDR";assert pack.tax_label=="PBJT";assert pack.tax_id_label=="NPWP"

def test_generic_pack_has_no_tax_assumption():
    pack=GenericPack();assert pack.tax_label=="Tax";assert not pack.default_currency

def test_phone_normalization_indonesia():
    assert normalize_phone("0812-3456-7890")=="6281234567890"
    assert normalize_phone("+62 812 3456 7890")=="6281234567890"

def test_communications_financial_guard_contract():
    assert FINANCIAL_DOCTYPES=={"Sales Invoice","POS Invoice","Payment Entry","Journal Entry","Purchase Invoice","Stock Entry"}
