from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone

def canonical_json(value)->str:
    return json.dumps(value,sort_keys=True,separators=(",",":"),default=str)

def request_hash(value)->str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()

def webhook_signature(secret:str,timestamp:str,body:str)->str:
    return __import__('hmac').new((secret or '').encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()

def retry_delay_seconds(attempt:int,base:int=60,cap:int=21600)->int:
    attempt=max(1,int(attempt)); return min(cap,base*(2**(attempt-1)))

def event_matches(patterns,event:str)->bool:
    for raw in patterns or []:
        p=(raw or '').strip()
        if p=='*' or p==event or (p.endswith('*') and event.startswith(p[:-1])): return True
    return False

def normalize_phone(value:str)->str:
    digits=re.sub(r'\D','',value or '')
    if digits.startswith('0'): digits='62'+digits[1:]
    return digits

def normalize_email(value:str)->str: return (value or '').strip().lower()

def natural_key(entity:str,row:dict)->str:
    entity=(entity or '').lower()
    if entity=='customer': return normalize_email(row.get('email')) or normalize_phone(row.get('phone')) or (row.get('customer_name') or '').strip().lower()
    if entity=='room type': return f"{row.get('property','')}::{(row.get('room_type_name') or '').strip().lower()}"
    if entity=='room': return f"{row.get('property','')}::{(row.get('room_number') or '').strip().lower()}"
    if entity=='reservation': return (row.get('source_reference') or row.get('reservation_id') or '').strip()
    if entity=='rate calendar': return '::'.join(str(row.get(k,'')).strip() for k in ('property','rate_plan','room_type','stay_date'))
    return canonical_json(row)
