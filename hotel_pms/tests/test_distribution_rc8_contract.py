import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_distribution_modules_do_not_create_erpnext_financial_documents_directly():
    forbidden = [
        '"doctype": "Sales Invoice"',
        '"doctype": "POS Invoice"',
        '"doctype": "Payment Entry"',
        '"doctype": "Journal Entry"',
        '"doctype": "Purchase Invoice"',
        '"doctype": "Stock Entry"',
    ]
    text = "\n".join((ROOT / "hotel_pms" / name).read_text() for name in ["distribution.py", "prearrival.py", "turnover.py"])
    assert not [pattern for pattern in forbidden if pattern in text]


def test_distribution_connection_hides_endpoint_and_secrets():
    path = ROOT / "hotel_pms" / "hotel_pms" / "doctype" / "hotel_distribution_connection" / "hotel_distribution_connection.json"
    doc = json.loads(path.read_text())
    fields = {row["fieldname"]: row for row in doc["fields"]}
    assert fields["endpoint"]["fieldtype"] == "Password"
    assert fields["api_key"]["fieldtype"] == "Password"
    assert fields["webhook_secret"]["fieldtype"] == "Password"
    assert fields["feed_token_hash"]["hidden"] == 1


def test_guest_token_supports_one_time_prearrival_purpose():
    path = ROOT / "hotel_pms" / "hotel_pms" / "doctype" / "hotel_guest_access_token" / "hotel_guest_access_token.json"
    doc = json.loads(path.read_text())
    purpose = next(row for row in doc["fields"] if row["fieldname"] == "purpose")
    assert "Pre-arrival Form" in purpose["options"].splitlines()


def test_rc8_patch_is_registered():
    assert "hotel_pms.patches.v1_0_rc8.setup_distribution_turnover" in (ROOT / "hotel_pms" / "patches.txt").read_text()


def test_distribution_doctypes_are_property_scoped():
    platform = (ROOT / "hotel_pms" / "platform.py").read_text()
    for doctype in [
        "Hotel Distribution Connection", "Hotel Distribution Room Mapping", "Hotel Distribution Event",
        "Hotel Prearrival Form Template", "Hotel Prearrival Form Submission",
    ]:
        assert f"'{doctype}':'property'" in platform


def test_rc8_production_gate_checks_exist():
    gate = (ROOT / "hotel_pms" / "production_gate.py").read_text()
    for code in ["DISTRIBUTION_READINESS", "PREARRIVAL_SECURITY", "TURNOVER_READINESS"]:
        assert code in gate


def test_uncertified_provider_adapters_are_not_marked_shipped():
    source = (ROOT / "hotel_pms" / "intelligence.py").read_text()
    for key in ["channex-channel-adapter", "staah-channel-adapter", "aiosell-channel-adapter"]:
        section = source[source.index(key):source.index(key)+600]
        assert '"maturity_status": "Adapter"' in section


def test_reservation_external_price_lock_is_not_a_second_ledger():
    path = ROOT / "hotel_pms" / "hotel_pms" / "doctype" / "hotel_reservation" / "hotel_reservation.json"
    fields = {row["fieldname"]: row for row in json.loads(path.read_text())["fields"]}
    assert fields["external_sell_price_locked"]["read_only"] == 1
    assert fields["external_event"]["options"] == "Hotel Distribution Event"


def test_public_ical_feed_is_tokenized_rate_limited_and_never_exports_guest_names():
    text = (ROOT / "hotel_pms" / "distribution.py").read_text()
    assert "_enforce_public_feed_rate_limit(slug)" in text
    assert "hmac.compare_digest(expected, supplied)" in text
    assert '"SUMMARY:Blocked"' in text
    assert "guest_name" not in text[text.index("def _feed_events"):text.index("def on_reservation_change")]


def test_inbound_foreign_currency_requires_finance_review_before_reservation_creation():
    text = (ROOT / "hotel_pms" / "distribution.py").read_text()
    marker = '"result": "currency_needs_review"'
    assert marker in text
    assert text.index(marker) < text.index('"doctype": "Hotel Reservation"')


def test_ical_scheduler_respects_per_connection_interval():
    text = (ROOT / "hotel_pms" / "distribution.py").read_text()
    section = text[text.index("def sync_all_ical_connections"):text.index("def _external_room_conflicts")]
    assert "sync_interval_minutes" in section
    assert "elapsed < interval * 60" in section


def test_frappe_cloud_python_floor_and_v16_dependencies_are_declared():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'requires-python = ">=3.10"' in text
    assert 'frappe = ">=16.0.0,<17.0.0"' in text
    assert 'erpnext = ">=16.0.0,<17.0.0"' in text
