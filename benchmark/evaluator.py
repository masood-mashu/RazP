from __future__ import annotations
import json
from datetime import datetime
from typing import List, Dict, Any, Callable
from collections import defaultdict
from core.schemas import (
    TransactionTelemetry,
    CustomerMessage,
    PaymentMethod,
    AIReasonerOutput,
    PolicyDecision,
    ActionType,
    MerchantPolicy
)
from core.policy_gate import DeterministicPolicyGate
from core.state_machine import StateMachine
from core.executor import RecoveryExecutor
from simulator.environment import (
    SimulatedEnvironment,
    CustomerHiddenState,
    BankHiddenState
)


class BenchmarkEvaluator:
    """
    Independent Benchmark Evaluator computing 5-way ablation & dual-layer metrics.
    """

    def __init__(self, policy: MerchantPolicy = MerchantPolicy()):
        self.policy = policy

    def evaluate_system(
        self,
        system_name: str,
        decide_fn: Callable[[TransactionTelemetry, datetime], PolicyDecision],
        dataset: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Runs the benchmark across all cases and returns structured metrics.
        """
        total_cases = len(dataset)
        total_amount_at_risk = 0.0
        total_gross_recovered = 0.0
        total_operational_cost = 0.0
        
        recovered_count = 0
        violations_intercepted_count = 0
        unintercepted_violations_count = 0
        wasted_interventions_count = 0
        chargebacks_triggered = 0

        # Component tracking
        correct_root_causes = 0
        total_root_causes_evaluated = 0
        correct_actions = 0
        ptp_correct_count = 0
        ptp_total_count = 0
        debit_claim_missed = 0
        abstention_correct = 0
        total_abstained = 0

        # Macro-F1 confusion matrix for root cause
        rc_true_positives = defaultdict(int)
        rc_false_positives = defaultdict(int)
        rc_false_negatives = defaultdict(int)
        all_rc_classes = set()

        case_results = []

        for item in dataset:
            case_id = item["case_id"]
            category = item["category"]
            telem_dict = item["telemetry"]
            gt = item["ground_truth"]
            env_dict = item["environment_hidden"]
            eval_time = datetime.fromisoformat(item["eval_timestamp"])

            # Reconstruct telemetry object
            msg_obj = None
            if telem_dict.get("last_inbound_message"):
                msg_obj = CustomerMessage(
                    message_text=telem_dict["last_inbound_message"]["message_text"],
                    channel=telem_dict["last_inbound_message"].get("channel", "WHATSAPP")
                )

            telemetry = TransactionTelemetry(
                payment_id=telem_dict["payment_id"],
                invoice_id=telem_dict["invoice_id"],
                amount_inr=telem_dict["amount_inr"],
                gateway_error_code=telem_dict["gateway_error_code"],
                bank_raw_response_code=telem_dict["bank_raw_response_code"],
                payment_method=PaymentMethod(telem_dict["payment_method"]),
                latency_ms=telem_dict["latency_ms"],
                bank_switch_degradation_score=telem_dict["bank_switch_degradation_score"],
                attempt_count=telem_dict.get("attempt_count", 1),
                last_inbound_message=msg_obj
            )

            total_amount_at_risk += telemetry.amount_inr

            # Setup independent simulator
            cust_hidden = CustomerHiddenState(
                balance_inr=env_dict["balance_inr"],
                salary_day=env_dict["salary_day"],
                willingness_to_pay=env_dict["willingness_to_pay"],
                is_disputing_charge=env_dict["is_disputing_charge"],
                actually_debited_by_bank=env_dict["actually_debited_by_bank"],
                is_hostile=env_dict["is_hostile"]
            )
            bank_hidden = BankHiddenState(
                is_switch_healthy=env_dict["is_switch_healthy"],
                will_drop_next_retry=env_dict["will_drop_next_retry"],
                deemed_success_settlement_in_progress=env_dict["deemed_success_settlement_in_progress"]
            )
            env = SimulatedEnvironment(
                customer_state=cust_hidden,
                bank_state=bank_hidden,
                simulation_start_time=eval_time,
                invoice_amount=telemetry.amount_inr
            )

            # System execution
            decision: PolicyDecision = decide_fn(telemetry, eval_time)
            
            # Track guardrail violations
            if decision.violations_detected:
                if decision.is_overridden:
                    violations_intercepted_count += len(decision.violations_detected)
                else:
                    unintercepted_violations_count += len(decision.violations_detected)

            # Check action accuracy against ground truth
            if decision.final_action.value == gt["target_action"]:
                correct_actions += 1

            # Check component root cause if available
            gt_rc = gt["root_cause"]
            all_rc_classes.add(gt_rc)
            ai_rc = getattr(decision, "ai_root_cause", None)
            if ai_rc:
                total_root_causes_evaluated += 1
                all_rc_classes.add(ai_rc)
                if ai_rc == gt_rc:
                    correct_root_causes += 1
                    rc_true_positives[gt_rc] += 1
                else:
                    rc_false_positives[ai_rc] += 1
                    rc_false_negatives[gt_rc] += 1

            # Check PTP accuracy
            if gt.get("extracted_ptp_day"):
                ptp_total_count += 1
                if decision.final_action == ActionType.SCHEDULE_PTP:
                    ptp_correct_count += 1

            # Check debit claim misses
            if gt["claim_debit_occurred"] and decision.final_action != ActionType.PAUSE_RECON_VERIFY:
                debit_claim_missed += 1

            # Check abstention
            if decision.final_action in (ActionType.ABSTAIN_DO_NOTHING, ActionType.ESCALATE_HUMAN_OPS):
                total_abstained += 1
                if gt["must_abstain"]:
                    abstention_correct += 1

            # Step in environment
            is_rec, gross_recovered, penalty_cost, env_msg = env.step(
                action=decision.final_action,
                params=decision.final_parameters
            )

            # Operational cost calculation
            op_cost = 0.0
            if "LLM" in system_name or "Sentinel" in system_name:
                op_cost += self.policy.cost_per_llm_inference
            if decision.final_action == ActionType.SEND_PAYMENT_LINK:
                op_cost += self.policy.cost_per_whatsapp
            op_cost += penalty_cost
            total_operational_cost += op_cost

            if env.chargeback_filed:
                chargebacks_triggered += 1

            if is_rec:
                recovered_count += 1
                total_gross_recovered += gross_recovered

            # Track wasted interventions
            if not is_rec and decision.final_action in (ActionType.RETRY_IMMEDIATE, ActionType.SEND_PAYMENT_LINK):
                wasted_interventions_count += 1

            case_results.append({
                "case_id": case_id,
                "category": category,
                "action": decision.final_action.value,
                "target_action": gt["target_action"],
                "recovered": is_rec,
                "gross_recovered": gross_recovered,
                "violations": decision.violations_detected,
                "is_overridden": decision.is_overridden,
                "env_outcome": env_msg
            })

        # Calculate Macro-F1 for Root Cause
        f1_scores = []
        for c in all_rc_classes:
            tp = rc_true_positives[c]
            fp = rc_false_positives[c]
            fn = rc_false_negatives[c]
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
            f1_scores.append(f1)
        macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0.0

        net_recovered_amount = total_gross_recovered - total_operational_cost
        recovery_rate_pct = (recovered_count / total_cases) * 100.0
        nmrr = (net_recovered_amount / total_amount_at_risk) * 100.0

        return {
            "system_name": system_name,
            "total_cases": total_cases,
            "total_amount_at_risk_inr": round(total_amount_at_risk, 2),
            "total_amount_recovered_inr": round(total_gross_recovered, 2),
            "net_recovered_amount_inr": round(net_recovered_amount, 2),
            "recovery_rate_pct": round(recovery_rate_pct, 2),
            "net_money_recovered_ratio_pct": round(nmrr, 2),
            "unsafe_actions_attempted": violations_intercepted_count + unintercepted_violations_count,
            "unsafe_actions_executed": unintercepted_violations_count,
            "guardrail_interventions": violations_intercepted_count,
            "wasted_interventions": wasted_interventions_count,
            "chargebacks_triggered": chargebacks_triggered,
            "total_operational_cost_inr": round(total_operational_cost, 2),
            "action_accuracy_pct": round((correct_actions / total_cases) * 100.0, 2),
            "root_cause_macro_f1": round(macro_f1, 4),
            "ptp_extraction_accuracy_pct": round((ptp_correct_count / ptp_total_count * 100.0), 2) if ptp_total_count > 0 else 100.0,
            "debit_claim_misses": debit_claim_missed,
            "abstention_precision_pct": round((abstention_correct / total_abstained * 100.0), 2) if total_abstained > 0 else 100.0,
            "case_results": case_results
        }
