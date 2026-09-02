from __future__ import annotations
from typing import Optional, Dict, Any
from core.schemas import (
    TransactionTelemetry,
    PolicyDecision,
    ExecutionResult,
    PaymentState,
    ActionType,
    MerchantPolicy,
    AIReasonerOutput
)
from core.state_machine import StateMachine
from core.ledger import AuditLedger


class RecoveryExecutor:
    """
    Deterministic Action Executor & State Synchronizer.
    Executes the validated action from the Policy Gate, tracks cost, and records to Ledger.
    """

    def __init__(self, ledger: Optional[AuditLedger] = None, policy: Optional[MerchantPolicy] = None):
        self.ledger = ledger or AuditLedger()
        self.policy = policy or MerchantPolicy()

    def execute(
        self,
        telemetry: TransactionTelemetry,
        policy_decision: PolicyDecision,
        state_machine: StateMachine,
        ai_reasoning: Optional[AIReasonerOutput] = None
    ) -> ExecutionResult:
        action = policy_decision.final_action
        cost_incurred = 0.0
        
        # Add LLM inference cost if AI was invoked
        if ai_reasoning:
            cost_incurred += self.policy.cost_per_llm_inference

        # Determine target state and calculate operational cost
        if action == ActionType.RETRY_IMMEDIATE:
            target_state = PaymentState.RETRY_SCHEDULED
            # Note: If this retry subsequently fails on bank switch, bank penalty cost applies
        elif action == ActionType.RETRY_BACKOFF:
            target_state = PaymentState.RETRY_SCHEDULED
        elif action == ActionType.SEND_PAYMENT_LINK:
            target_state = PaymentState.AWAITING_CUSTOMER_ACTION
            channel = policy_decision.final_parameters.get("channel", "WHATSAPP")
            cost_incurred += self.policy.cost_per_whatsapp if channel == "WHATSAPP" else self.policy.cost_per_sms
        elif action == ActionType.SCHEDULE_PTP:
            target_state = PaymentState.PTP_SCHEDULED
        elif action == ActionType.PAUSE_RECON_VERIFY:
            target_state = PaymentState.PAUSE_RECON_VERIFY
        elif action == ActionType.ESCALATE_HUMAN_OPS:
            target_state = PaymentState.ESCALATED_HUMAN_OPS
        elif action == ActionType.ABSTAIN_DO_NOTHING:
            target_state = PaymentState.DEAD_LETTER
        else:
            target_state = PaymentState.DEAD_LETTER

        # Perform atomic transition on state machine
        try:
            # If current state is PAYMENT_FAILED, transition through analysis/policy to target
            if state_machine.current_state == PaymentState.PAYMENT_FAILED:
                state_machine.transition(PaymentState.TELEMETRY_ANALYSIS, "Ingested failure telemetry")
                state_machine.transition(PaymentState.POLICY_GATED, "Policy gate passed")
            elif state_machine.current_state == PaymentState.AWAITING_CUSTOMER_ACTION:
                state_machine.transition(PaymentState.TELEMETRY_ANALYSIS, "Customer inbound received")
                state_machine.transition(PaymentState.POLICY_GATED, "Policy gate re-evaluated")
            
            state_machine.transition(target_state, policy_decision.policy_reason)
        except Exception:
            # Safety catch: if invalid transition attempted, force safe hold state
            target_state = state_machine.current_state

        # Immutable ledger recording
        self.ledger.record_entry(
            telemetry=telemetry,
            policy_decision=policy_decision,
            action_executed=action.value,
            resulting_state=state_machine.current_state.value,
            ai_reasoning=ai_reasoning
        )

        return ExecutionResult(
            success=True,
            action_executed=action,
            resulting_state=state_machine.current_state,
            details=policy_decision.final_parameters,
            financial_cost_incurred=round(cost_incurred, 4),
            recovered_amount=0.0,
            timestamp=policy_decision.timestamp
        )
