
from datetime import datetime,timedelta
from hotel_pms.guest_rules import normalize_email,normalize_phone,token_is_usable,blacklist_blocks,can_anonymize

def test_normalization():
    assert normalize_email(" A@Example.COM ")=="a@example.com"
    assert normalize_phone("0812-3456")=="628123456"
def test_token_rules():
    assert token_is_usable("Active",datetime.now()+timedelta(minutes=1),0,1)
    assert not token_is_usable("Expired",datetime.now()+timedelta(minutes=1),0,1)
    assert not token_is_usable("Active",datetime.now()-timedelta(minutes=1),0,0)
    assert not token_is_usable("Active",datetime.now()+timedelta(minutes=1),1,1)
def test_blacklist_and_privacy():
    assert blacklist_blocks("Block Online","Online")
    assert not blacklist_blocks("Block Online","Desk")
    assert blacklist_blocks("Block All","Desk")
    assert can_anonymize(0,0,False)
    assert not can_anonymize(1,0,False)
