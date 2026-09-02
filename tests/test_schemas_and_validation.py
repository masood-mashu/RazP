import pytest
from datetime import datetime
from pydantic import ValidationError
from core.schemas import (
    TransactionTelemetry,
    CustomerMessage,
    AIReasonerOutput,
    PaymentMethod,
    RootCauseCategory,
    CustomerIntentCategory,
    ActionType
)


def test_schema_rejects_negative_or_zero_amount():
    with pytest.raises(ValidationError):
        TransactionTelemetry(
            payment_id="pay_inv_neg",
            invoice_id="inv_neg",
            amount_inr=-100.0,
            gateway_error_code="BAD_REQUEST_ERROR",
            bank_raw_response_code="51",
            payment_method=PaymentMethod.UPI_AUTOPAY,
            latency_ms=100,
            bank_switch_degradation_score=0.1
        )

    with pytest.raises(ValidationError):
        TransactionTelemetry(
            payment_id="pay_inv_zero",
            invoice_id="inv_zero",
            amount_inr=0.0,
            gateway_error_code="BAD_REQUEST_ERROR",
            bank_raw_response_code="51",
            payment_method=PaymentMethod.UPI_AUTOPAY,
            latency_ms=100,
            bank_switch_degradation_score=0.1
        )


def test_schema_rejects_missing_payment_id():
    with pytest.raises(ValidationError):
        TransactionTelemetry(
            payment_id="",
            invoice_id="inv_1",
            amount_inr=500.0,
            gateway_error_code="BAD_REQUEST_ERROR",
            bank_raw_response_code="51",
            payment_method=PaymentMethod.UPI_AUTOPAY,
            latency_ms=100,
            bank_switch_degradation_score=0.1
        )


def test_ai_output_requires_timestamp_for_schedule_ptp():
    # If proposed_action is SCHEDULE_PTP, extracted_ptp_timestamp is mandatory
    with pytest.raises(ValidationError):
        AIReasonerOutput(
            root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
            customer_intent=CustomerIntentCategory.DELAY_REQUESTED_PTP,
            claim_debit_occurred=False,
            extracted_ptp_timestamp=None, # Missing timestamp!
            proposed_action=ActionType.SCHEDULE_PTP,
            confidence=0.9,
            reasoning_audit_text="Scheduling PTP without date"
        )


def test_ai_output_rejects_short_rationale():
    with pytest.raises(ValidationError):
        AIReasonerOutput(
            root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
            customer_intent=CustomerIntentCategory.COOPERATIVE_WILL_PAY,
            claim_debit_occurred=False,
            proposed_action=ActionType.SEND_PAYMENT_LINK,
            confidence=0.9,
            reasoning_audit_text="bad" # Too short (< 5 chars)
        )


def test_customer_message_requires_text():
    with pytest.raises(ValidationError):
        CustomerMessage(message_text="")
