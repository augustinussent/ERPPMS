from hotel_pms.platform_rules import event_matches,natural_key,retry_delay_seconds,request_hash,webhook_signature

def test_retry_backoff_is_bounded():
 assert retry_delay_seconds(1,60)==60
 assert retry_delay_seconds(4,60)==480
 assert retry_delay_seconds(100,60)==21600

def test_event_patterns():
 assert event_matches(['reservation.*'],'reservation.created')
 assert not event_matches(['payment.*'],'reservation.created')

def test_natural_keys_are_stable():
 assert natural_key('Customer',{'email':' A@EXAMPLE.COM '})=='a@example.com'
 assert natural_key('Room',{'property':'P1','room_number':' 101 '})=='P1::101'

def test_hashes_are_deterministic():
 assert request_hash({'b':2,'a':1})==request_hash({'a':1,'b':2})
 assert webhook_signature('secret','1','{}')==webhook_signature('secret','1','{}')
