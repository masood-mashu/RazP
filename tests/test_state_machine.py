import pytest
from core.schemas import PaymentState, ActionType
from core.state_machine import StateMachine, InvalidStateTransitionError


def test_valid_recovery_lifecycle():
    sm = StateMachine(PaymentState.PAYMENT_FAILED)
    assert sm.current_state == PaymentState.PAYMENT_FAILED

    sm.transition(PaymentState.TELEMETRY_ANALYSIS, "Webhook parsed")
    assert sm.current_state == PaymentState.TELEMETRY_ANALYSIS

    sm.transition(PaymentState.POLICY_GATED, "AI proposed action evaluated")
    assert sm.current_state == PaymentState.POLICY_GATED

    sm.transition(PaymentState.RETRY_SCHEDULED, "Action RETRY_BACKOFF scheduled")
    assert sm.current_state == PaymentState.RETRY_SCHEDULED

    sm.transition(PaymentState.RECOVERED, "Payment confirmed on gateway")
    assert sm.current_state == PaymentState.RECOVERED
    assert sm.is_terminal()


def test_illegal_state_jump_rejected():
    sm = StateMachine(PaymentState.PAYMENT_FAILED)
    
    # Trying to jump directly from PAYMENT_FAILED to RECOVERED without analysis or proof
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(PaymentState.RECOVERED, "Fake immediate recovery")


def test_deduction_claim_cycle():
    sm = StateMachine(PaymentState.PAYMENT_FAILED)
    sm.transition(PaymentState.TELEMETRY_ANALYSIS)
    sm.transition(PaymentState.DEDUCTION_SUSPECTED)
    sm.transition(PaymentState.PAUSE_RECON_VERIFY)
    sm.transition(PaymentState.RECOVERED, "Recon confirmed settlement")
    assert sm.is_terminal()
