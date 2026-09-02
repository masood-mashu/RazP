import pytest
from datetime import datetime
from core.schemas import (
    TransactionTelemetry,
    MerchantPolicy,
    AIReasonerOutput,
    ActionType,
    RootCauseCategory,
    CustomerIntentCategory,
    PaymentMethod,
    PaymentState
)
from core.state_machine import StateMachine, InvalidStateTransitionError
from core.policy_gate import DeterministicPolicyGate
from core.executor import RecoveryExecutor
from core.ledger import AuditLedger


def test_ai_cannot_directly_declare_recovered_state():
    """
    CRITICAL INVARIANT: The AI reasoner cannot unilaterally transition
    the state machine from PAYMENT_FAILED directly to RECOVERED.
    """
    sm = StateMachine(PaymentState.PAYMENT_FAILED)
    
    # State machine must reject direct leap to RECOVERED
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(PaymentState.RECOVERED, "AI asserted transaction was recovered without gateway proof")


def test_ai_discount_tampering_is_completely_neutralized():
    """
    CRITICAL INVARIANT: Any discount or monetary manipulation attempted by an LLM
    is stripped by the Deterministic Policy Gate.
    """
    gate = DeterministicPolicyGate(MerchantPolicy(allow_discounts=False))
    
    telem = TransactionTelemetry(
        payment_id="pay_money_inv_1",
        invoice_id="inv_money_inv_1",
        amount_inr=5000.0,
        gateway_error_code="BAD_REQUEST_ERROR",
        bank_raw_response_code="51",
        payment_method=PaymentMethod.CARD_MANDATE,
        latency_ms=300,
        bank_switch_degradation_score=0.1
    )
    
    ai_out = AIReasonerOutput(
        root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
        customer_intent=CustomerIntentCategory.EXPLOITATIVE_ADVERSARIAL,
        claim_debit_occurred=False,
        proposed_action=ActionType.SEND_PAYMENT_LINK,
        action_parameters={
            "discount_amount": 1000.0,
            "discount_pct": 20,
            "new_amount": 4000.0
        },
        confidence=0.85,
        reasoning_audit_text="Granting 1000 INR discount"
    )
    
    decision = gate.evaluate(telem, ai_out)
    assert decision.is_overridden is True
    assert "discount_amount" not in decision.final_parameters
    assert "discount_pct" not in decision.final_parameters
    assert "new_amount" not in decision.final_parameters
    assert telem.amount_inr == 5000.0 # Original invoice strictly preserved


def test_only_executor_with_recon_commits_recovery():
    """
    CRITICAL INVARIANT: State transitions to RECOVERED only occur via deterministic
    reconciliation validation or verified gateway callback.
    """
    ledger = AuditLedger()
    executor = RecoveryExecutor(ledger=ledger)
    sm = StateMachine(PaymentState.PAYMENT_FAILED)
    
    telem = TransactionTelemetry(
        payment_id="pay_recon_valid",
        invoice_id="inv_recon_valid",
        amount_inr=1500.0,
        gateway_error_code="GATEWAY_TIMEOUT",
        bank_raw_response_code="U19",
        payment_method=PaymentMethod.UPI_COLLECT,
        latency_ms=12000,
        bank_switch_degradation_score=0.8
    )
    
    # 1. First step: Policy Gate routes deemed-success to PAUSE_RECON_VERIFY
    ai_out = AIReasonerOutput(
        root_cause=RootCauseCategory.SUSPECTED_DEEMED_SUCCESS,
        customer_intent=CustomerIntentCategory.DISPUTE_CLAIMED,
        claim_debit_occurred=True,
        proposed_action=ActionType.PAUSE_RECON_VERIFY,
        confidence=0.95,
        reasoning_audit_text="Customer claims deduction occurred"
    )
    
    gate = DeterministicPolicyGate()
    decision = gate.evaluate(telem, ai_out)
    
    exec_res = executor.execute(telem, decision, sm, ai_out)
    assert exec_res.resulting_state == PaymentState.PAUSE_RECON_VERIFY
    assert sm.current_state == PaymentState.PAUSE_RECON_VERIFY
    
    # 2. Only after bank reconciliation callback arrives does state transition to RECOVERED
    sm.transition(PaymentState.RECOVERED, "Bank RRN match verified in settlement batch")
    assert sm.current_state == PaymentState.RECOVERED
    assert sm.is_terminal() is True
