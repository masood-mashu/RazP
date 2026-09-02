import pytest
from datetime import datetime
from core.schemas import (
    TransactionTelemetry,
    AIReasonerOutput,
    ActionType,
    RootCauseCategory,
    CustomerIntentCategory,
    PaymentMethod,
    CustomerMessage
)
from core.gemini_reasoner import GeminiReasoner, PROMPT_VERSION, SCHEMA_VERSION


def test_gemini_reasoner_missing_key_safe_fallback():
    """
    Verifies that when no API key is set, the reasoner returns a validated output
    with fallback_used=True without crashing.
    """
    reasoner = GeminiReasoner(api_key=None)
    telem = TransactionTelemetry(
        payment_id="pay_test_no_key",
        invoice_id="inv_test_no_key",
        amount_inr=1500.0,
        gateway_error_code="BAD_REQUEST_ERROR",
        bank_raw_response_code="51",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=300,
        bank_switch_degradation_score=0.05
    )
    
    result = reasoner.reason(telem)
    
    assert "reasoner_output" in result
    assert isinstance(result["reasoner_output"], AIReasonerOutput)
    assert result["is_live_gemini"] is False
    assert result["fallback_used"] is True
    assert result["latency_ms"] >= 0.0
    assert result["prompt_version"] == PROMPT_VERSION
    assert result["schema_version"] == SCHEMA_VERSION


def test_gemini_reasoner_api_exception_safe_fallback_and_redaction():
    """
    Verifies that upon API exception / network drop, the adapter catches the exception,
    safely redacts the API key from the error message, and returns a valid fallback output.
    """
    fake_secret_key = "AIzaSy_FAKE_SECRET_KEY_123456789"
    reasoner = GeminiReasoner(api_key=fake_secret_key)
    
    telem = TransactionTelemetry(
        payment_id="pay_test_err",
        invoice_id="inv_test_err",
        amount_inr=2499.0,
        gateway_error_code="BAD_REQUEST_ERROR",
        bank_raw_response_code="51",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=450,
        bank_switch_degradation_score=0.1,
        last_inbound_message=CustomerMessage(
            message_text="bhai salary 7 tareek ko aayegi tab kat lena"
        )
    )
    
    result = reasoner.reason(telem, reference_time=datetime(2026, 9, 1, 14, 0, 0))
    
    assert isinstance(result["reasoner_output"], AIReasonerOutput)
    assert result["fallback_used"] is True
    # Verify the secret API key is NOT leaked into the error string
    assert fake_secret_key not in result["error"]
    assert result["reasoner_output"].proposed_action == ActionType.SCHEDULE_PTP


def test_gemini_reasoner_model_provenance_recording():
    """
    Verifies that model provenance metadata is recorded.
    """
    reasoner = GeminiReasoner(model="gemini-3.7-flash", api_key=None)
    telem = TransactionTelemetry(
        payment_id="pay_test_prov",
        invoice_id="inv_test_prov",
        amount_inr=1999.0,
        gateway_error_code="GATEWAY_ERROR",
        bank_raw_response_code="91",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=8500,
        bank_switch_degradation_score=0.85
    )
    
    result = reasoner.reason(telem)
    assert result["prompt_version"] == "v1.0.0"
    assert result["schema_version"] == "v1.0.0"
    assert result["reasoner_output"].root_cause == RootCauseCategory.BANK_SWITCH_DEGRADATION
