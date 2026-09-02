import pytest
from core.schemas import (
    TransactionTelemetry,
    CustomerMessage,
    PaymentMethod,
    ActionType,
    PaymentState,
    PolicyDecision
)
from core.state_machine import StateMachine, InvalidStateTransitionError
from core.policy_gate import DeterministicPolicyGate
from core.ledger import AuditLedger


def test_webhook_replay_and_idempotent_deduplication():
    """
    Verifies that delivering the exact same webhook payload twice is caught by
    idempotent event registration and suppressed without state mutation.
    """
    sm = StateMachine(PaymentState.PAYMENT_FAILED)
    
    event_id = "evt_recon_test_123"
    payload = "3200.0:GATEWAY_TIMEOUT:U30"
    
    # 1. First delivery -> Accepted
    is_first = sm.check_and_register_event(event_id, payload)
    assert is_first is True
    
    # 2. Duplicate delivery -> Suppressed
    is_second = sm.check_and_register_event(event_id, payload)
    assert is_second is False


def test_multi_event_lifecycle_prevents_double_recovery():
    """
    Verifies that once a payment reaches RECOVERED via bank reconciliation,
    subsequent duplicate recovery attempts or actions are rejected.
    """
    sm = StateMachine(PaymentState.PAYMENT_FAILED)
    
    # Transition to PAUSE_RECON_VERIFY
    sm.transition(PaymentState.TELEMETRY_ANALYSIS, "Telemetry Ingest")
    sm.transition(PaymentState.POLICY_GATED, "Gated")
    sm.transition(PaymentState.PAUSE_RECON_VERIFY, "Debit claim lock")
    
    # Ingest Recon settlement -> Transitions to RECOVERED
    sm.transition(PaymentState.RECOVERED, "Bank recon confirmed RRN")
    assert sm.current_state == PaymentState.RECOVERED
    
    # Attempt illegal transition out of terminal state
    with pytest.raises(InvalidStateTransitionError, match="Cannot transition out of terminal state"):
        sm.transition(PaymentState.RETRY_SCHEDULED, "Illegal retry after recovery")


def test_ledger_tamper_and_restore_cycle():
    """
    Verifies that ledger tampering is immediately detected and can be restored.
    """
    ledger = AuditLedger()
    telem = TransactionTelemetry(
        payment_id="pay_test_001",
        invoice_id="inv_test_001",
        amount_inr=3200.0,
        gateway_error_code="GATEWAY_TIMEOUT",
        bank_raw_response_code="U30",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=12400,
        bank_switch_degradation_score=0.85
    )
    pol_dec = PolicyDecision(
        payment_id="pay_test_001",
        original_action=ActionType.PAUSE_RECON_VERIFY,
        proposed_action=ActionType.PAUSE_RECON_VERIFY,
        final_action=ActionType.PAUSE_RECON_VERIFY,
        final_parameters={},
        is_overridden=False,
        policy_reason="Recon lock"
    )
    
    ledger.record_entry(
        telemetry=telem,
        policy_decision=pol_dec,
        action_executed=ActionType.PAUSE_RECON_VERIFY.value,
        resulting_state=PaymentState.PAUSE_RECON_VERIFY.value
    )
    
    is_valid, err = ledger.verify_integrity()
    assert is_valid is True
    assert err is None
    
    # Corrupt block
    original = ledger.chain[0].action_executed
    ledger.chain[0].action_executed = "FORGED_UNAUTHORIZED_ACTION"
    
    is_valid_corrupt, err_corrupt = ledger.verify_integrity()
    assert is_valid_corrupt is False
    assert "hash mismatch" in err_corrupt.lower()
    
    # Restore block
    ledger.chain[0].action_executed = original
    is_valid_restored, err_restored = ledger.verify_integrity()
    assert is_valid_restored is True
    assert err_restored is None
