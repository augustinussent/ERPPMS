
from __future__ import annotations
import re
from datetime import date, datetime

def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()

def normalize_phone(value: str | None) -> str:
    digits=re.sub(r"\D+","",value or "")
    if digits.startswith("0"): digits="62"+digits[1:]
    return digits

def token_is_usable(status: str, expires_at, usage_count: int=0, max_uses: int=0, now=None) -> bool:
    now=now or datetime.now()
    if status != "Active" or not expires_at: return False
    expiry=expires_at if isinstance(expires_at,datetime) else datetime.fromisoformat(str(expires_at))
    if expiry <= now: return False
    return not max_uses or usage_count < max_uses

def blacklist_blocks(level: str | None, channel: str="Online") -> bool:
    if level == "Block All": return True
    return level == "Block Online" and channel == "Online"

def can_anonymize(active_reservations:int, outstanding_amount:float, legal_hold:bool=False) -> bool:
    return not legal_hold and active_reservations == 0 and abs(float(outstanding_amount or 0)) < 0.01
