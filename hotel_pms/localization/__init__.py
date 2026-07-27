def get_localization_context(*args, **kwargs):
    from hotel_pms.localization.registry import get_localization_context as fn
    return fn(*args, **kwargs)

def get_pack(*args, **kwargs):
    from hotel_pms.localization.registry import get_pack as fn
    return fn(*args, **kwargs)

def validate_tax_profile_mapping(*args, **kwargs):
    from hotel_pms.localization.registry import validate_tax_profile_mapping as fn
    return fn(*args, **kwargs)

__all__=["get_localization_context","get_pack","validate_tax_profile_mapping"]
