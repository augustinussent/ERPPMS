from __future__ import annotations
import re

FINANCIAL_DOCTYPES={"Sales Invoice","POS Invoice","Payment Entry","Journal Entry","Purchase Invoice","Stock Entry"}

def normalize_phone(value:str|None)->str:
    digits=re.sub(r"\D","",value or "")
    if digits.startswith("0"):
        digits="62"+digits[1:]
    return digits
