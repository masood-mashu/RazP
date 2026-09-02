from datetime import datetime
import pytest
from core.schemas import (
    TransactionTelemetry,
    CustomerMessage,
    PaymentMethod,
    RootCauseCategory,
    CustomerIntentCategory,
    ActionType
)
from core.reasoner import AIReasoner


@pytest.fixture
def reasoner():
    return AIReasoner()


def test_reasoner_hinglish_ptp_extraction(reasoner):
    now = datetime(2026, 9, 1, 10, 0, 0)
    telem = TransactionTelemetry(
        payment_id="pay_hinglish_1",
        invoice_id="inv_hinglish_1",
        amount_inr=2499.0,
        gateway_error_code="BAD_REQUEST_ERROR",
        bank_raw_response_code="51",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=450,
        bank_switch_degradation_score=0.1,
        last_inbound_message=CustomerMessage(
            message_text="bhai salary 7 tareek ko aayegi tab kat lena please"
        )
    )
    
    out = reasoner.reason(telem, reference_time=now)
    assert out.customer_intent == CustomerIntentCategory.DELAY_REQUESTED_PTP
    assert out.proposed_action == ActionType.SCHEDULE_PTP
    assert out.extracted_ptp_timestamp is not None
    assert out.extracted_ptp_timestamp.day == 7


def test_reasoner_debit_claim_detection(reasoner):
    now = datetime(2026, 9, 1, 10, 0, 0)
    telem = TransactionTelemetry(
        payment_id="pay_debit_claim_1",
        invoice_id="inv_debit_claim_1",
        amount_inr=4999.0,
        gateway_error_code="GATEWAY_TIMEOUT",
        bank_raw_response_code="U19",
        payment_method=PaymentMethod.UPI_COLLECT,
        latency_ms=15000,
        bank_switch_degradation_score=0.8,
        last_inbound_message=CustomerMessage(
            message_text="mere account se paise kat gaye but order nahi mila dobara mat katna"
        )
    )
    
    out = reasoner.reason(telem, reference_time=now)
    assert out.claim_debit_occurred is True
    assert out.proposed_action == ActionType.PAUSE_RECON_VERIFY
    assert out.root_cause == RootCauseCategory.SUSPECTED_DEEMED_SUCCESS
