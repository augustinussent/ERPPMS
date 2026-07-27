from hotel_pms.localization.base import HotelLocalizationPack

class GenericPack(HotelLocalizationPack):
    code = "generic"
    default_locale = "en"
    tax_label = "Tax"
    tax_id_label = "Tax ID"
