from datetime import datetime, timedelta
from core.executor import RecoveryExecutor
from core.ledger import AuditLedger
from core.policy_gate import DeterministicPolicyGate
from core.schemas import (
    ActionType,
    AIReasonerOutput,
    CustomerIntentCategory,
    PaymentMethod,
    PaymentState,
    PolicyDecision,
    RootCauseCategory,
    TransactionTelemetry,
)
from core.state_machine import StateMachine


def make_telemetry(**overrides):
    values = {
        "payment_id": "pay_regression",
        "invoice_id": "inv_regression",
        "amount_inr": 2000.0,
        "gateway_error_code": "BAD_REQUEST_ERROR",
        "bank_raw_response_code": "51",
        "payment_method": PaymentMethod.UPI_AUTOPAY,
        "latency_ms": 400,
        "bank_switch_degradation_score": 0.1,
        "attempt_count": 1,
    }
    values.update(overrides)
    return TransactionTelemetry(**values)


def make_ai(action, root_cause=RootCauseCategory.INSUFFICIENT_FUNDS, **overrides):
    values = {
        "root_cause": root_cause,
        "customer_intent": CustomerIntentCategory.COOPERATIVE_WILL_PAY,
        "claim_debit_occurred": False,
        "proposed_action": action,
        "confidence": 0.9,
        "reasoning_audit_text": "Regression test proposal",
    }
    values.update(overrides)
    return AIReasonerOutput(**values)


def test_quiet_hours_rechecked_after_permanent_failure_fallback():
    gate = DeterministicPolicyGate()
    decision = gate.evaluate(
        make_telemetry(),
        make_ai(ActionType.RETRY_IMMEDIATE, RootCauseCategory.PERMANENT_ACCOUNT_FAILURE),
        current_time=datetime(2026, 9, 1, 22, 0, 0),
    )

    assert decision.final_action == ActionType.ABSTAIN_DO_NOTHING
    assert any("QUIET_HOURS_VIOLATION" in v for v in decision.violations_detected)
    assert "Outbound communication suppressed" in decision.policy_reason


def test_quiet_hours_rechecked_after_invalid_ptp_fallback():
    gate = DeterministicPolicyGate()
    now = datetime(2026, 9, 1, 22, 0, 0)
    decision = gate.evaluate(
        make_telemetry(),
        make_ai(
            ActionType.SCHEDULE_PTP,
            extracted_ptp_timestamp=now - timedelta(days=1),
        ),
        current_time=now,
    )

    assert decision.final_action == ActionType.ABSTAIN_DO_NOTHING
    assert any("INVALID_PTP" in v for v in decision.violations_detected)
    assert any("QUIET_HOURS_VIOLATION" in v for v in decision.violations_detected)


def test_executor_reports_rejected_repeat_retry_as_failure():
    sm = StateMachine(PaymentState.RETRY_SCHEDULED)
    decision = PolicyDecision(
        is_overridden=False,
        original_action=ActionType.RETRY_BACKOFF,
        final_action=ActionType.RETRY_BACKOFF,
        final_parameters={"delay_minutes": 120},
        policy_reason="Repeated retry regression test",
        timestamp=datetime(2026, 9, 1, 14, 0, 0),
    )
    result = RecoveryExecutor(ledger=AuditLedger()).execute(
        telemetry=make_telemetry(),
        policy_decision=decision,
        state_machine=sm,
    )

    assert result.success is False
    assert result.resulting_state == PaymentState.RETRY_SCHEDULED
    assert "execution_error" in result.details


def test_quiet_hours_naive_utc_1630_blocked_in_ist():
    """
    REGRESSION: Naive UTC datetime at 16:30 UTC corresponds to 22:00 IST (Quiet Hours).
    Ensure it is normalized to UTC, converted to IST, and outbound message is blocked.
    """
    gate = DeterministicPolicyGate()
    # 16:30 UTC without tzinfo (22:00 IST)
    naive_utc_dt = datetime(2026, 9, 1, 16, 30, 0)
    
    decision = gate.evaluate(
        make_telemetry(),
        make_ai(ActionType.SEND_PAYMENT_LINK),
        current_time=naive_utc_dt,
    )
    assert decision.is_overridden is True
    assert decision.final_action == ActionType.ABSTAIN_DO_NOTHING
    assert any("QUIET_HOURS_VIOLATION" in v for v in decision.violations_detected)


def test_escalated_human_ops_transitions_to_recovered():
    """
    REGRESSION: Authoritative settlement can transition a case from
    ESCALATED_HUMAN_OPS directly to RECOVERED.
    """
    sm = StateMachine(PaymentState.ESCALATED_HUMAN_OPS)
    # Must succeed without InvalidStateTransitionError
    new_state = sm.transition(PaymentState.RECOVERED, "Bank settlement confirmed by reconciliation")
    assert new_state == PaymentState.RECOVERED
    assert sm.is_terminal() is True


def test_evaluate_single_replay_idempotency():
    """
    REGRESSION: Replaying the same webhook payload against /api/evaluate/single
    triggers durable deduplication and suppresses duplicate state transitions.
    """
    from fastapi.testclient import TestClient
    from server.app import app
    import os

    os.environ["RAZP_DEMO_IN_MEMORY"] = "true"
    client = TestClient(app)
    
    payment_id = "pay_idemp_eval_single_test"
    payload = {
        "payment_id": payment_id,
        "invoice_id": "inv_idemp_01",
        "amount_inr": 3500.0,
        "gateway_error_code": "BAD_REQUEST_ERROR",
        "bank_raw_response_code": "51",
        "payment_method": "UPI_AUTOPAY",
        "attempt_count": 1,
        "inbound_message": "bhai link bhejo please",
        "event_id": "evt_eval_single_unique_01"
    }

    headers = {"X-API-Key": "razp_op_key_demo"}

    # First delivery: processed
    res1 = client.post("/api/evaluate/single", json=payload, headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1.get("idempotent_duplicate") is not True

    # Second delivery (replay): intercepted and suppressed
    res2 = client.post("/api/evaluate/single", json=payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2.get("idempotent_duplicate") is True
    assert data2.get("status") == "DUPLICATE_EVENT_SUPPRESSED"
