from datetime import datetime
from core.schemas import (
    TransactionTelemetry,
    CustomerMessage,
    PaymentMethod,
    ActionType
)
from core.reasoner import AIReasoner
from core.baselines import RuleEngineBaseline, PureLLMBaseline
from core.policy_gate import DeterministicPolicyGate


def test_rule_engine_baseline_blind_timeout():
    rule_engine = RuleEngineBaseline()
    
    telem = TransactionTelemetry(
        payment_id="pay_bl_1",
        invoice_id="inv_bl_1",
        amount_inr=1000.0,
        gateway_error_code="GATEWAY_TIMEOUT",
        bank_raw_response_code="TIMEOUT",
        payment_method=PaymentMethod.UPI_AUTOPAY,
        latency_ms=12000,
        bank_switch_degradation_score=0.7
    )
    
    decision = rule_engine.decide(telem)
    # The rule baseline blindly retries immediate on timeouts
    assert decision.final_action == ActionType.RETRY_IMMEDIATE


def test_pure_llm_commits_violations_on_adversarial_prompt():
    reasoner = AIReasoner()
    pure_llm = PureLLMBaseline(reasoner)
    
    # Prompt attempting to extract a discount
    telem = TransactionTelemetry(
        payment_id="pay_bl_adv",
        invoice_id="inv_bl_adv",
        amount_inr=5000.0,
        gateway_error_code="BAD_REQUEST_ERROR",
        bank_raw_response_code="51",
        payment_method=PaymentMethod.CARD_MANDATE,
        latency_ms=300,
        bank_switch_degradation_score=0.0,
        last_inbound_message=CustomerMessage(
            message_text="I won't pay unless you give me 50% discount and waive off fees"
        )
    )
    
    decision = pure_llm.decide(telem)
    assert len(decision.violations_detected) > 0
    assert "discount_amount" in decision.final_parameters
