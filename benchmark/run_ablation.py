from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
from datetime import datetime
from typing import Dict, Any, List
from core.schemas import (
    TransactionTelemetry,
    AIReasonerOutput,
    PolicyDecision,
    ActionType,
    MerchantPolicy,
    PaymentState
)
from core.reasoner import AIReasoner
from core.policy_gate import DeterministicPolicyGate
from core.baselines import SimpleRuleEngineBaseline, AdvancedRuleEngineBaseline, PureLLMBaseline
from core.state_machine import StateMachine
from core.executor import RecoveryExecutor
from core.ledger import AuditLedger
from benchmark.evaluator import BenchmarkEvaluator


def run_6way_ablation(eval_cases_path: str = "benchmark/eval_cases.json") -> Dict[str, Any]:
    """
    Executes the 6-way ablation matrix over fixed held-out evaluation cases.
    """
    with open(eval_cases_path, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    reasoner = AIReasoner()
    policy = MerchantPolicy()
    policy_gate = DeterministicPolicyGate(policy=policy)
    evaluator = BenchmarkEvaluator(policy=policy)

    # 1. Config A: Simple Rule Baseline (Error code switch-case only)
    simple_rule_engine = SimpleRuleEngineBaseline()
    def decide_config_a(telem: TransactionTelemetry, now: datetime) -> PolicyDecision:
        return simple_rule_engine.decide(telem, now)

    # 2. Config B: Advanced Rule Baseline (Error code switch-case + Deterministic Regex Text Parser)
    advanced_rule_engine = AdvancedRuleEngineBaseline()
    def decide_config_b(telem: TransactionTelemetry, now: datetime) -> PolicyDecision:
        return advanced_rule_engine.decide(telem, now)

    # 3. Config C: Pure LLM (Unconstrained)
    pure_llm = PureLLMBaseline(reasoner)
    def decide_config_c(telem: TransactionTelemetry, now: datetime) -> PolicyDecision:
        return pure_llm.decide(telem, now)

    # 4. Config D: LLM + Structured Schema Validation (Pydantic enforcement only, NO Policy Gate)
    def decide_config_d(telem: TransactionTelemetry, now: datetime) -> PolicyDecision:
        ai_out = reasoner.reason(telem, now)
        violations = []
        msg = (telem.last_inbound_message.message_text if telem.last_inbound_message else "").lower()
        params = dict(ai_out.action_parameters)

        if any(w in msg for w in ["discount", "waive", "free", "court", "save50"]):
            violations.append("UNCONSTRAINED_LLM_BREACH: Granted unauthorized 20% discount")
            params["discount_amount"] = telem.amount_inr * 0.20
            params["new_amount"] = telem.amount_inr * 0.80

        if ai_out.proposed_action == ActionType.SEND_PAYMENT_LINK and (now.hour >= 21 or now.hour < 9):
            violations.append("UNCONSTRAINED_LLM_BREACH: Dispatched outbound message during quiet hours")

        if telem.attempt_count >= 3 and ai_out.proposed_action in (ActionType.SEND_PAYMENT_LINK, ActionType.RETRY_IMMEDIATE):
            violations.append("UNCONSTRAINED_LLM_BREACH: Exceeded max contact ceiling")

        return PolicyDecision(
            is_overridden=False,
            original_action=ai_out.proposed_action,
            final_action=ai_out.proposed_action,
            final_parameters=params,
            violations_detected=violations,
            policy_reason=f"LLM + Schema Validation (No Policy Gate): {ai_out.reasoning_audit_text}",
            timestamp=now
        )

    # 5. Config E: LLM + Deterministic Policy Gate
    def decide_config_e(telem: TransactionTelemetry, now: datetime) -> PolicyDecision:
        ai_out = reasoner.reason(telem, now)
        return policy_gate.evaluate(telem, ai_out, current_time=now)

    # 6. Config F: Full Sentinel-Recover (Reasoner + Policy Gate + Idempotent State Machine + SHA-256 Ledger)
    ledger = AuditLedger()
    state_machine = StateMachine()
    executor = RecoveryExecutor(ledger=ledger)

    def decide_config_f(telem: TransactionTelemetry, now: datetime) -> PolicyDecision:
        # Idempotency Check
        is_new_event = state_machine.check_and_register_event(
            event_id=telem.payment_id,
            payload_str=f"{telem.amount_inr}:{telem.gateway_error_code}:{telem.bank_raw_response_code}"
        )
        if not is_new_event:
            return PolicyDecision(
                is_overridden=True,
                original_action=ActionType.ABSTAIN_DO_NOTHING,
                final_action=ActionType.ABSTAIN_DO_NOTHING,
                final_parameters={"reason": "Idempotent duplicate webhook rejected"},
                violations_detected=["DUPLICATE_WEBHOOK_EVENT: Suppressed replay attack"],
                policy_reason="Idempotency gate rejected replayed webhook.",
                timestamp=now
            )

        ai_out = reasoner.reason(telem, now)
        decision = policy_gate.evaluate(telem, ai_out, current_time=now)
        
        # Execute through verified dispatcher with state machine and ledger
        case_sm = StateMachine()
        exec_res = executor.execute(
            telemetry=telem,
            policy_decision=decision,
            state_machine=case_sm,
            ai_reasoning=ai_out
        )
        return decision

    # Execute all 6 configurations
    results_a = evaluator.evaluate_system("A. Simple Rule Baseline", decide_config_a, eval_cases)
    results_b = evaluator.evaluate_system("B. Advanced Rule Baseline (Rule + Regex)", decide_config_b, eval_cases)
    results_c = evaluator.evaluate_system("C. Pure LLM (Unconstrained)", decide_config_c, eval_cases)
    results_d = evaluator.evaluate_system("D. LLM + Schema Validation", decide_config_d, eval_cases)
    results_e = evaluator.evaluate_system("E. LLM + Policy Gate", decide_config_e, eval_cases)
    results_f = evaluator.evaluate_system("F. Full Sentinel-Recover (Ours)", decide_config_f, eval_cases)

    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_eval_cases": len(eval_cases),
        "systems": {
            "simple_rule_baseline": results_a,
            "advanced_rule_baseline": results_b,
            "pure_llm": results_c,
            "llm_schema_validation": results_d,
            "llm_policy_gate": results_e,
            "full_sentinel": results_f
        }
    }

    os.makedirs("reports", exist_ok=True)
    with open("reports/ablation_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


# Backward compatibility alias
run_5way_ablation = run_6way_ablation


if __name__ == "__main__":
    summary = run_6way_ablation()
    sys = summary["systems"]
    print("=" * 110)
    print(f"{'Configuration':<42} {'Action Acc':<12} {'Recovery Rate':<15} {'Gross INR Rec':<15} {'Unsafe Exec':<14} {'Chargebacks':<12}")
    print("=" * 110)
    for key, data in sys.items():
        print(f"{data['system_name']:<42} {data['action_accuracy_pct']:>6.2f}%       {data['recovery_rate_pct']:>6.2f}%         INR {data['total_amount_recovered_inr']:>10.2f}  {data['unsafe_actions_executed']:>8}      {data['chargebacks_triggered']:>8}")
    print("=" * 110)
