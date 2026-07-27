from hotel_pms.intelligence_rules import (
    integration_readiness_reasons,
    payment_correction_plan,
)


def test_refund_cap_never_exceeds_source_payment_entry():
    plan = payment_correction_plan(
        docstatus=1,
        payment_type="Receive",
        hotel_transaction_type="Deposit",
        original_amount=100000,
        refundable_amount=300000,
    )
    assert plan["allowed_actions"] == ["Create Refund", "Manual Review"]
    assert plan["maximum_refundable"] == 100000


def test_refund_cap_never_exceeds_remaining_deposit():
    plan = payment_correction_plan(
        docstatus=1,
        payment_type="Receive",
        hotel_transaction_type="Deposit",
        original_amount=500000,
        refundable_amount=125000,
    )
    assert plan["maximum_refundable"] == 125000


def test_manual_review_has_zero_automatic_refundable_amount():
    plan = payment_correction_plan(
        docstatus=1,
        payment_type="Receive",
        hotel_transaction_type=None,
        original_amount=500000,
        refundable_amount=500000,
    )
    assert plan["allowed_actions"] == ["Manual Review"]
    assert plan["maximum_refundable"] == 0


def test_ready_connection_requires_successful_test():
    reasons = integration_readiness_reasons(
        maturity_status="Shipped",
        connection_status="Ready",
        last_test_status=None,
        last_tested_at=None,
        failed_mandatory_checks=[],
    )
    assert reasons == ["Ready/Live connection has no successful Test Connection result."]


def test_failed_enabled_connection_is_blocked_even_when_not_live():
    reasons = integration_readiness_reasons(
        maturity_status="Shipped",
        connection_status="Failed",
        last_test_status="Failed",
        last_tested_at="2026-07-27 12:00:00",
        failed_mandatory_checks=[],
    )
    assert "Connection health status is Failed." in reasons


def test_live_connection_requires_all_mandatory_checks():
    reasons = integration_readiness_reasons(
        maturity_status="Adapter",
        connection_status="Live",
        last_test_status="Passed",
        last_tested_at="2026-07-27 12:00:00",
        failed_mandatory_checks=["CREDENTIAL_ROTATION"],
    )
    assert reasons == ["Mandatory go-live checks are not Passed."]


def test_planned_integration_cannot_be_enabled_for_release():
    reasons = integration_readiness_reasons(
        maturity_status="Planned",
        connection_status="Draft",
        last_test_status=None,
        last_tested_at=None,
        failed_mandatory_checks=[],
    )
    assert reasons == ["Integration maturity is not Shipped or Adapter."]
