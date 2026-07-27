from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable
from urllib.parse import urlparse

GENERIC_ICAL_MARKERS = (
    "reserved",
    "closed",
    "not available",
    "blocked",
    "unavailable",
    "fully booked",
)


def stable_hash(*parts: object) -> str:
    payload = "|".join("" if part is None else str(part).strip() for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_generic_ical_summary(value: str | None) -> bool:
    text = re.sub(r"\s+", " ", (value or "").strip().lower())
    if not text:
        return True
    return any(marker in text for marker in GENERIC_ICAL_MARKERS)


def canonical_date(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) >= 10:
        text = text[:10]
    return date.fromisoformat(text).isoformat()


def strict_overlap(start_a, end_a, start_b, end_b) -> bool:
    """Checkout touching the next check-in is a turnover, not a conflict."""
    a1, a2 = date.fromisoformat(canonical_date(start_a)), date.fromisoformat(canonical_date(end_a))
    b1, b2 = date.fromisoformat(canonical_date(start_b)), date.fromisoformat(canonical_date(end_b))
    return a1 < b2 and b1 < a2


def echo_key(property_name: str, room_or_type: str, start_date, end_date) -> str:
    return stable_hash("ICAL-ECHO", property_name, room_or_type, canonical_date(start_date), canonical_date(end_date))


def event_key(connection: str, uid: str, start_date, end_date) -> str:
    return stable_hash("DIST-EVENT", connection, uid, canonical_date(start_date), canonical_date(end_date))


def normalized_guest_label(summary: str | None, provider: str) -> str:
    return provider if is_generic_ical_summary(summary) else re.sub(r"\s+", " ", (summary or "").strip())[:140]


def parse_money(value, *, required: bool = False) -> Decimal | None:
    if value in (None, ""):
        if required:
            raise ValueError("A monetary value is required.")
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid monetary value.") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Monetary value must be a finite non-negative number.")
    return amount.quantize(Decimal("0.01"))


def room_rate_per_night(room_rate_total, arrival, departure) -> Decimal:
    total = parse_money(room_rate_total, required=True)
    nights = (date.fromisoformat(canonical_date(departure)) - date.fromisoformat(canonical_date(arrival))).days
    if nights <= 0:
        raise ValueError("Departure must be after arrival.")
    return (total / Decimal(nights)).quantize(Decimal("0.01"))


def validate_outbound_url(url: str, resolved_ips: Iterable[str] = ()) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS calendar URLs are allowed.")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Calendar URL must contain a normal public host and no embedded credentials.")
    if parsed.port not in (None, 443):
        raise ValueError("Only the standard HTTPS port is allowed.")
    for raw in resolved_ips:
        ip = ipaddress.ip_address(raw)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("Calendar URL resolves to a non-public address.")
    return parsed.geturl()


def sanitize_ical_text(value: str | None, limit: int = 180) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def parse_ical_date(value: str) -> str:
    raw = (value or "").strip()
    # RFC 5545 all-day dates are deliberately interpreted as local calendar dates.
    # Do not convert them through UTC and manufacture the classic off-by-one fiasco.
    if re.fullmatch(r"\d{8}", raw):
        return datetime.strptime(raw, "%Y%m%d").date().isoformat()
    match = re.match(r"(\d{8})T", raw)
    if match:
        return datetime.strptime(match.group(1), "%Y%m%d").date().isoformat()
    raise ValueError("Unsupported iCal date value.")


def unfold_ical(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def parse_ical_events(text: str) -> list[dict]:
    if "BEGIN:VCALENDAR" not in text.upper():
        raise ValueError("Response is not an iCal calendar.")
    events: list[dict] = []
    current: dict | None = None
    for line in unfold_ical(text):
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            current = {}
            continue
        if upper == "END:VEVENT":
            if current and current.get("start_date") and current.get("end_date"):
                current.setdefault("uid", stable_hash("ICAL", current.get("summary"), current["start_date"], current["end_date"]))
                current.setdefault("summary", "Blocked")
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        base = key.split(";", 1)[0].upper()
        if base == "UID":
            current["uid"] = sanitize_ical_text(value, 200)
        elif base == "SUMMARY":
            current["summary"] = sanitize_ical_text(value)
        elif base == "DTSTART":
            current["start_date"] = parse_ical_date(value)
        elif base == "DTEND":
            current["end_date"] = parse_ical_date(value)
    return [e for e in events if e["end_date"] > e["start_date"]]


def dedupe_ical_events(events: Iterable[dict]) -> list[dict]:
    by_uid: dict[tuple[str, str, str], dict] = {}
    for event in events:
        key = (str(event.get("uid") or ""), canonical_date(event["start_date"]), canonical_date(event["end_date"]))
        current = by_uid.get(key)
        if current is None or (is_generic_ical_summary(current.get("summary")) and not is_generic_ical_summary(event.get("summary"))):
            by_uid[key] = dict(event)
    return sorted(by_uid.values(), key=lambda e: (e["start_date"], e["end_date"], e.get("uid") or ""))


def turnover_window_minutes(check_out_time: str | None, check_in_time: str | None) -> int:
    def minutes(value: str | None, default: str) -> int:
        hh, mm = (value or default).split(":")[:2]
        return int(hh) * 60 + int(mm)
    start = minutes(check_out_time, "12:00")
    end = minutes(check_in_time, "14:00")
    delta = end - start
    return delta if delta > 0 else delta + 1440


def recommend_room(rows: Iterable[dict], preferred_floor: str | None = None) -> dict | None:
    candidates = []
    for row in rows:
        hk = (row.get("housekeeping_status") or "").strip()
        score = 0
        reasons = []
        if hk == "Inspected":
            score += 40; reasons.append("inspected")
        elif hk == "Clean":
            score += 30; reasons.append("clean")
        else:
            score -= 100; reasons.append(f"housekeeping {hk or 'unknown'}")
        if preferred_floor and str(row.get("floor") or "").strip().lower() == str(preferred_floor).strip().lower():
            score += 15; reasons.append("preferred floor")
        candidates.append((score, str(row.get("room_number") or row.get("name") or ""), row, reasons))
    if not candidates:
        return None
    score, _, row, reasons = sorted(candidates, key=lambda item: (-item[0], item[1]))[0]
    return {**row, "score": score, "reason": ", ".join(reasons)}


def snapshot_answers(questions: Iterable[dict], incoming: dict) -> list[dict]:
    output = []
    for question in questions:
        key = str(question.get("field_key") or "").strip()
        raw = incoming.get(key)
        empty = raw is None or raw == "" or raw == []
        if question.get("required") and empty:
            raise ValueError(f"Required: {question.get('label') or key}")
        if isinstance(raw, str):
            raw = re.sub(r"[\x00-\x1f\x7f]", " ", raw).strip()[:2000]
        elif isinstance(raw, list):
            raw = [re.sub(r"[\x00-\x1f\x7f]", " ", str(x)).strip()[:200] for x in raw[:20]]
        elif raw is not None and not isinstance(raw, (int, float, bool)):
            raw = str(raw)[:2000]
        output.append({
            "field_key": key,
            "field_type": question.get("field_type") or "Short Text",
            "label": question.get("label") or key,
            "value": None if empty else raw,
        })
    return output


def json_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
