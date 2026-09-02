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
def sample_telemetry():
    return TransactionTelemetry(
        payment_id="pay_gate_test",
        invoice_id="inv_gate_test",
        amount_inr=2000.0,
        gateway_error_code="BAD_REQUEST_ERROR",
        bank_raw_response_code="51",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=400,
        bank_switch_degradation_score=0.1,
        attempt_count=1
    )


# -----------------------------------------------------------------------------
# QUIET HOURS BOUNDARY TESTS (TRAI TCCCPR: 21:00 - 09:00 IST)
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("hour,minute,second,expected_blocked", [
    (20, 59, 59, False), # 8:59:59 PM -> Allowed
    (21, 0, 0, True),    # 9:00:00 PM -> Blocked
    (21, 0, 1, True),    # 9:00:01 PM -> Blocked
    (23, 30, 0, True),   # 11:30:00 PM -> Blocked
    (4, 0, 0, True),     # 4:00:00 AM -> Blocked
    (8, 59, 59, True),   # 8:59:59 AM -> Blocked
    (9, 0, 0, False),    # 9:00:00 AM -> Allowed
    (9, 0, 1, False),    # 9:00:01 AM -> Allowed
    (14, 0, 0, False),   # 2:00:00 PM -> Allowed
])
def test_quiet_hours_exact_boundaries(sample_telemetry, hour, minute, second, expected_blocked):
    gate = DeterministicPolicyGate()
    eval_time = datetime(2026, 9, 1, hour, minute, second)
    
    ai_out = AIReasonerOutput(
        root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
        customer_intent=CustomerIntentCategory.COOPERATIVE_WILL_PAY,
        claim_debit_occurred=False,
        proposed_action=ActionType.SEND_PAYMENT_LINK,
        confidence=0.9,
        reasoning_audit_text="Sending payment link"
    )
    
    decision = gate.evaluate(sample_telemetry, ai_out, current_time=eval_time)
    
    if expected_blocked:
        assert decision.is_overridden is True
        assert decision.final_action == ActionType.ABSTAIN_DO_NOTHING
        assert any("QUIET_HOURS_VIOLATION" in v for v in decision.violations_detected)
    else:
        assert decision.final_action == ActionType.SEND_PAYMENT_LINK


# -----------------------------------------------------------------------------
# CONTACT CEILING BOUNDARY TESTS
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("attempt_count,expected_escalated", [
    (1, False),
    (2, False),
    (3, True),  # Max limit = 3 -> Intercepted
    (4, True),  # Exceeded -> Intercepted
])
def test_contact_ceiling_boundaries(sample_telemetry, attempt_count, expected_escalated):
    gate = DeterministicPolicyGate()
    sample_telemetry.attempt_count = attempt_count
    
    ai_out = AIReasonerOutput(
        root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
        customer_intent=CustomerIntentCategory.COOPERATIVE_WILL_PAY,
        claim_debit_occurred=False,
        proposed_action=ActionType.SEND_PAYMENT_LINK,
        confidence=0.9,
        reasoning_audit_text="Retry outbound contact"
    )
    
    eval_time = datetime(2026, 9, 1, 14, 0, 0)
    decision = gate.evaluate(sample_telemetry, ai_out, current_time=eval_time)
    
    if expected_escalated:
        assert decision.is_overridden is True
        assert decision.final_action == ActionType.ESCALATE_HUMAN_OPS
        assert any("MAX_ATTEMPTS_EXCEEDED" in v for v in decision.violations_detected)
    else:
        assert decision.final_action == ActionType.SEND_PAYMENT_LINK


# -----------------------------------------------------------------------------
# CIRCUIT BREAKER BOUNDARY TESTS
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("degradation_score,expected_backoff", [
    (0.0, False),
    (0.50, False),
    (0.64, False),
    (0.65, True), # Threshold 0.65 -> Overridden to RETRY_BACKOFF
    (0.85, True),
])
def test_circuit_breaker_boundaries(sample_telemetry, degradation_score, expected_backoff):
    gate = DeterministicPolicyGate()
    sample_telemetry.bank_switch_degradation_score = degradation_score
    
    ai_out = AIReasonerOutput(
        root_cause=RootCauseCategory.TRANSIENT_NETWORK_GLITCH,
        customer_intent=CustomerIntentCategory.NO_COMMUNICATION,
        claim_debit_occurred=False,
        proposed_action=ActionType.RETRY_IMMEDIATE,
        confidence=0.9,
        reasoning_audit_text="Immediate retry"
    )
    
    eval_time = datetime(2026, 9, 1, 14, 0, 0)
    decision = gate.evaluate(sample_telemetry, ai_out, current_time=eval_time)
    
    if expected_backoff:
        assert decision.is_overridden is True
        assert decision.final_action == ActionType.RETRY_BACKOFF
        assert any("CIRCUIT_BREAKER_TRIGGERED" in v for v in decision.violations_detected)
    else:
        assert decision.final_action == ActionType.RETRY_IMMEDIATE


# -----------------------------------------------------------------------------
# PROMISE-TO-PAY HORIZON BOUNDARY TESTS
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("days_offset,expected_approved", [
    (-1, False), # Past date -> Rejected
    (0, True),   # Today -> Approved
    (7, True),   # 7 days -> Approved
    (14, True),  # 14 days -> Approved (Max limit)
    (15, False), # 15 days -> Exceeded policy limit -> Escalated to Human Ops
])
def test_ptp_horizon_boundaries(sample_telemetry, days_offset, expected_approved):
    gate = DeterministicPolicyGate()
    now = datetime(2026, 9, 1, 14, 0, 0)
    ptp_time = now + timedelta(days=days_offset)
    
    ai_out = AIReasonerOutput(
        root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
        customer_intent=CustomerIntentCategory.DELAY_REQUESTED_PTP,
        claim_debit_occurred=False,
        extracted_ptp_timestamp=ptp_time,
        proposed_action=ActionType.SCHEDULE_PTP,
        confidence=0.95,
        reasoning_audit_text=f"Scheduling PTP with offset {days_offset} days"
    )
    
    decision = gate.evaluate(sample_telemetry, ai_out, current_time=now)
    
    if expected_approved:
        assert decision.final_action == ActionType.SCHEDULE_PTP
    else:
        assert decision.is_overridden is True
        assert decision.final_action != ActionType.SCHEDULE_PTP
