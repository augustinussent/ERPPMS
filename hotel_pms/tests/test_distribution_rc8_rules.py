from decimal import Decimal

import pytest

from hotel_pms.distribution_rules import (
    canonical_date,
    dedupe_ical_events,
    echo_key,
    event_key,
    is_generic_ical_summary,
    parse_ical_events,
    recommend_room,
    room_rate_per_night,
    snapshot_answers,
    strict_overlap,
    turnover_window_minutes,
    validate_outbound_url,
)


def test_checkout_touching_checkin_is_not_overlap():
    assert not strict_overlap("2026-08-01", "2026-08-03", "2026-08-03", "2026-08-05")


def test_partial_overlap_is_conflict():
    assert strict_overlap("2026-08-01", "2026-08-04", "2026-08-03", "2026-08-05")


def test_ical_all_day_dates_do_not_shift_timezone():
    events = parse_ical_events("""BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x1\nDTSTART;VALUE=DATE:20260801\nDTEND;VALUE=DATE:20260804\nSUMMARY:Reserved\nEND:VEVENT\nEND:VCALENDAR""")
    assert events[0]["start_date"] == "2026-08-01"
    assert events[0]["end_date"] == "2026-08-04"


def test_ical_line_folding_is_supported():
    events = parse_ical_events("""BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:x2\nDTSTART:20260801T140000Z\nDTEND:20260802T110000Z\nSUMMARY:Guest\n Name\nEND:VEVENT\nEND:VCALENDAR""")
    assert events[0]["summary"] == "GuestName"


def test_ical_uid_dedupe_prefers_descriptive_summary():
    rows = dedupe_ical_events([
        {"uid": "u", "start_date": "2026-08-01", "end_date": "2026-08-03", "summary": "Reserved"},
        {"uid": "u", "start_date": "2026-08-01", "end_date": "2026-08-03", "summary": "Booking 123"},
    ])
    assert rows == [{"uid": "u", "start_date": "2026-08-01", "end_date": "2026-08-03", "summary": "Booking 123"}]


def test_generic_host_blocks_are_identified():
    assert is_generic_ical_summary("CLOSED")
    assert is_generic_ical_summary("Reserved")
    assert not is_generic_ical_summary("Smith Family")


def test_event_key_is_connection_scoped():
    assert event_key("A", "uid", "2026-08-01", "2026-08-03") != event_key("B", "uid", "2026-08-01", "2026-08-03")


def test_echo_key_collapses_exact_same_room_dates():
    assert echo_key("P", "R101", "2026-08-01", "2026-08-03") == echo_key("P", "R101", "2026-08-01", "2026-08-03")


def test_url_requires_https():
    with pytest.raises(ValueError):
        validate_outbound_url("http://example.com/feed.ics", ["93.184.216.34"])


def test_url_rejects_embedded_credentials():
    with pytest.raises(ValueError):
        validate_outbound_url("https://user:pass@example.com/feed.ics", ["93.184.216.34"])


def test_url_rejects_private_address():
    with pytest.raises(ValueError):
        validate_outbound_url("https://example.com/feed.ics", ["127.0.0.1"])


def test_url_accepts_public_https_address():
    assert validate_outbound_url("https://example.com/feed.ics", ["93.184.216.34"]) == "https://example.com/feed.ics"


def test_room_rate_per_night_uses_exact_decimal():
    assert room_rate_per_night("1000000", "2026-08-01", "2026-08-05") == Decimal("250000.00")


def test_room_rate_rejects_invalid_stay():
    with pytest.raises(ValueError):
        room_rate_per_night("100", "2026-08-05", "2026-08-05")


def test_room_recommendation_prefers_inspected():
    row = recommend_room([
        {"name": "C", "room_number": "101", "housekeeping_status": "Clean", "floor": "1"},
        {"name": "I", "room_number": "201", "housekeeping_status": "Inspected", "floor": "2"},
    ])
    assert row["name"] == "I"


def test_room_recommendation_honors_floor_when_readiness_equal():
    row = recommend_room([
        {"name": "A", "room_number": "101", "housekeeping_status": "Clean", "floor": "1"},
        {"name": "B", "room_number": "201", "housekeeping_status": "Clean", "floor": "2"},
    ], "2")
    assert row["name"] == "B"


def test_turnover_window_same_day():
    assert turnover_window_minutes("12:00", "14:00") == 120


def test_turnover_window_crosses_midnight():
    assert turnover_window_minutes("23:00", "01:00") == 120


def test_prearrival_snapshot_keeps_label_at_submission_time():
    result = snapshot_answers(
        [{"field_key": "eta", "field_type": "Time", "label": "Arrival time", "required": True}],
        {"eta": "14:30"},
    )
    assert result == [{"field_key": "eta", "field_type": "Time", "label": "Arrival time", "value": "14:30"}]


def test_prearrival_required_answer_is_enforced():
    with pytest.raises(ValueError):
        snapshot_answers([{"field_key": "eta", "label": "Arrival", "required": True}], {})


def test_canonical_date_discards_time_without_utc_conversion():
    assert canonical_date("2026-08-01T23:30:00Z") == "2026-08-01"
