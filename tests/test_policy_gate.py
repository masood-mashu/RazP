from datetime import datetime, time, timedelta
import pytest
from core.schemas import (
    TransactionTelemetry,
    MerchantPolicy,
    AIReasonerOutput,
    ActionType,
    RootCauseCategory,
    CustomerIntentCategory,
    PaymentMethod
)
from core.policy_gate import DeterministicPolicyGate


@pytest.fixture
def base_telemetry():
    return TransactionTelemetry(
        payment_id="pay_test_123",
        invoice_id="inv_test_123",
        amount_inr=1500.0,
        gateway_error_code="BAD_REQUEST_ERROR",
        bank_raw_response_code="U30",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=350,
        bank_switch_degradation_score=0.1,
        attempt_count=1
    )


def test_debit_claim_forces_recon_lock(base_telemetry):
    gate = DeterministicPolicyGate()
    
    # AI proposed RETRY_IMMEDIATE, but customer claimed money was deducted
    ai_output = AIReasonerOutput(
        root_cause=RootCauseCategory.UNKNOWN_AMBIGUOUS,
        customer_intent=CustomerIntentCategory.DISPUTE_CLAIMED,
        claim_debit_occurred=True,
        proposed_action=ActionType.RETRY_IMMEDIATE,
        confidence=0.9,
        reasoning_audit_text="Customer claims deduction occurred"
    )
    
    decision = gate.evaluate(base_telemetry, ai_output)
    assert decision.is_overridden is True
    assert decision.final_action == ActionType.PAUSE_RECON_VERIFY
    assert any("UNSAFE_RETRY_ON_DEBIT_CLAIM" in v for v in decision.violations_detected)


def test_illegal_discount_is_stripped(base_telemetry):
    gate = DeterministicPolicyGate()
    
    # AI maliciously or mistakenly tried to apply a discount
    ai_output = AIReasonerOutput(
        root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
        customer_intent=CustomerIntentCategory.EXPLOITATIVE_ADVERSARIAL,
        claim_debit_occurred=False,
        proposed_action=ActionType.SEND_PAYMENT_LINK,
        action_parameters={"discount_amount": 200, "new_amount": 1300},
        confidence=0.85,
        reasoning_audit_text="Offering 200 INR discount to placate customer"
    )
    
    decision = gate.evaluate(base_telemetry, ai_output)
    assert decision.is_overridden is True
    assert "discount_amount" not in decision.final_parameters
    assert "new_amount" not in decision.final_parameters
    assert any("ILLEGAL_DISCOUNT_ATTEMPT" in v for v in decision.violations_detected)


def test_quiet_hours_blocks_outbound_messages(base_telemetry):
    gate = DeterministicPolicyGate()
    
    # Simulate nighttime: 23:30 (11:30 PM IST)
    night_time = datetime(2026, 9, 1, 23, 30, 0)
    
    ai_output = AIReasonerOutput(
        root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
        customer_intent=CustomerIntentCategory.COOPERATIVE_WILL_PAY,
        claim_debit_occurred=False,
        proposed_action=ActionType.SEND_PAYMENT_LINK,
        action_parameters={"channel": "WHATSAPP"},
        confidence=0.95,
        reasoning_audit_text="Send payment link on WhatsApp"
    )
    
    decision = gate.evaluate(base_telemetry, ai_output, current_time=night_time)
    assert decision.is_overridden is True
    assert decision.final_action == ActionType.ABSTAIN_DO_NOTHING
    assert any("QUIET_HOURS_VIOLATION" in v for v in decision.violations_detected)


def test_max_attempts_escalates_to_human_ops(base_telemetry):
    gate = DeterministicPolicyGate()
    base_telemetry.attempt_count = 3  # Hit max limit
    
    ai_output = AIReasonerOutput(
        root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
        customer_intent=CustomerIntentCategory.NO_COMMUNICATION,
        claim_debit_occurred=False,
        proposed_action=ActionType.RETRY_IMMEDIATE,
        confidence=0.7,
        reasoning_audit_text="Retry again"
    )
    
    decision = gate.evaluate(base_telemetry, ai_output)
    assert decision.is_overridden is True
    assert decision.final_action == ActionType.ESCALATE_HUMAN_OPS
    assert any("MAX_ATTEMPTS_EXCEEDED" in v for v in decision.violations_detected)
