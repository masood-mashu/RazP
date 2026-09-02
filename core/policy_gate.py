from __future__ import annotations
from datetime import datetime, time, timedelta, timezone
from typing import Optional, Dict, Any, List, Set
from core.schemas import (
    TransactionTelemetry,
    MerchantPolicy,
    AIReasonerOutput,
    PolicyDecision,
    ActionType,
    RootCauseCategory,
    PaymentMethod
)

# Indian Standard Time (IST = UTC + 5:30)
IST = timezone(timedelta(hours=5, minutes=30))


class DeterministicPolicyGate:
    """
    Deterministic Policy Gate & Safety Interceptor.
    
    CRITICAL INVARIANT: The AI never executes actions directly.
    Every proposal from the AI Reasoner passes through this deterministic validator.
    If a proposal breaches regulatory bounds, merchant policies, or safety rules,
    it is deterministically overridden or rejected.
    """

    # Strict Parameter Allow-Listing by ActionType (Defense in Depth)
    ALLOWED_PARAMETERS: Dict[ActionType, Set[str]] = {
        ActionType.RETRY_IMMEDIATE: set(),
        ActionType.RETRY_BACKOFF: {"delay_minutes"},
        ActionType.SEND_PAYMENT_LINK: {"channel", "method_fallback", "notes"},
        ActionType.SCHEDULE_PTP: {"scheduled_timestamp"},
        ActionType.PAUSE_RECON_VERIFY: {"timeout_minutes", "rrn_lookup"},
        ActionType.ESCALATE_HUMAN_OPS: {"reason", "priority"},
        ActionType.ABSTAIN_DO_NOTHING: {"reason"}
    }

    def __init__(self, policy: Optional[MerchantPolicy] = None):
        self.policy = policy or MerchantPolicy()

    def is_in_quiet_hours(self, dt: Optional[datetime] = None) -> bool:
        """
        TRAI TCCCPR 2018 Regulation: Commercial communications prohibited between 21:00 (9 PM) and 09:00 (9 AM) IST.
        Explicitly normalizes to IST time.
        """
        now = dt or datetime.now(IST)
        
        # If naive datetime, assume UTC and convert to IST
        if now.tzinfo is None:
            # If date timestamp has no tz, treat as IST if passed from simulation or convert from UTC
            check_time = now.time()
        else:
            check_time = now.astimezone(IST).time()

        start = self.policy.quiet_hours_start # 21:00
        end = self.policy.quiet_hours_end     # 09:00

        if start > end:  # Overnight range: 21:00 -> 09:00
            return check_time >= start or check_time < end
        return start <= check_time < end

    def evaluate(
        self,
        telemetry: TransactionTelemetry,
        ai_proposal: AIReasonerOutput,
        current_time: Optional[datetime] = None
    ) -> PolicyDecision:
        now = current_time or datetime.now(IST)
        violations: List[str] = []
        is_overridden = False
        final_action = ai_proposal.proposed_action
        
        # Strict Allow-List Sanitization of Parameters
        raw_params = dict(ai_proposal.action_parameters)
        allowed_keys = self.ALLOWED_PARAMETERS.get(final_action, set())
        
        sanitized_params: Dict[str, Any] = {}
        for k, v in raw_params.items():
            if k in allowed_keys:
                sanitized_params[k] = v
            else:
                violations.append(f"UNAUTHORIZED_PARAM_STRIPPED: Key '{k}' is not permitted for action {final_action.value}")
                is_overridden = True

        reasons: List[str] = []

        # =========================================================================
        # RULE 1: Double-Debit / Deemed-Success Protection (Highest Safety Priority)
        # =========================================================================
        if ai_proposal.claim_debit_occurred or ai_proposal.root_cause == RootCauseCategory.SUSPECTED_DEEMED_SUCCESS:
            if final_action != ActionType.PAUSE_RECON_VERIFY:
                violations.append("UNSAFE_RETRY_ON_DEBIT_CLAIM: Customer claimed money deducted or switch timeout")
                is_overridden = True
                final_action = ActionType.PAUSE_RECON_VERIFY
                sanitized_params = {"timeout_minutes": 30, "rrn_lookup": True}
                reasons.append("Halted retries to verify potential deemed success with bank settlement.")

        # =========================================================================
        # RULE 2: Zero Unauthorized Discount / Amount Tamper Invariant
        # =========================================================================
        if not self.policy.allow_discounts:
            # Check if reasoner proposed any discount parameter or amount deviation
            discount_triggers = {"discount", "discount_amount", "discount_pct", "new_amount", "waiver_inr", "price_override"}
            found_discounts = discount_triggers.intersection(set(raw_params.keys()))
            if found_discounts:
                violations.append(f"ILLEGAL_DISCOUNT_ATTEMPT: AI attempted monetary manipulation via {found_discounts}")
                is_overridden = True
                for k in found_discounts:
                    sanitized_params.pop(k, None)
                reasons.append("Stripped illegal discount; invoice amount strictly preserved.")

        # =========================================================================
        # RULE 3: Mandate Status Check (Revoked / Expired / Cancelled)
        # =========================================================================
        if telemetry.mandate_status.upper() in ("REVOKED", "EXPIRED", "CANCELLED", "PAUSED"):
            if final_action in (ActionType.RETRY_IMMEDIATE, ActionType.RETRY_BACKOFF):
                violations.append(f"INVALID_MANDATE_ACTION: Cannot retry recurring debit on {telemetry.mandate_status} token")
                is_overridden = True
                final_action = ActionType.SEND_PAYMENT_LINK
                sanitized_params = {"channel": "WHATSAPP", "method_fallback": "UPI_INTENT"}
                reasons.append("Mandate token is non-functional; shifted to manual payment link.")

        # =========================================================================
        # RULE 4: Contact Attempt Limit & Anti-Harassment Ceiling
        # =========================================================================
        if telemetry.attempt_count >= self.policy.max_contact_attempts:
            if final_action in (ActionType.SEND_PAYMENT_LINK, ActionType.RETRY_IMMEDIATE, ActionType.RETRY_BACKOFF):
                violations.append(f"MAX_ATTEMPTS_EXCEEDED: Current {telemetry.attempt_count} >= Max {self.policy.max_contact_attempts}")
                is_overridden = True
                final_action = ActionType.ESCALATE_HUMAN_OPS
                sanitized_params = {"reason": "Max contact/retry threshold reached without recovery", "priority": "HIGH"}
                reasons.append("Max automated recovery attempts reached. Escalated to Human Ops.")

        # =========================================================================
        # RULE 5: TRAI Quiet Hours Compliance (21:00 to 09:00 IST)
        # =========================================================================
        if final_action == ActionType.SEND_PAYMENT_LINK and self.is_in_quiet_hours(now):
            violations.append("QUIET_HOURS_VIOLATION: Outbound communication blocked during 21:00-09:00 IST (TRAI TCCCPR)")
            is_overridden = True
            final_action = ActionType.ABSTAIN_DO_NOTHING
            sanitized_params = {"reason": "Shifted to quiet hours queue. Outbound message deferred to 09:01 AM IST."}
            reasons.append("Outbound communication suppressed during quiet hours.")

        # =========================================================================
        # RULE 6: Bank Switch Degradation Circuit Breaker
        # =========================================================================
        if telemetry.bank_switch_degradation_score >= self.policy.circuit_breaker_bank_failure_rate_threshold:
            if final_action == ActionType.RETRY_IMMEDIATE:
                violations.append(f"CIRCUIT_BREAKER_TRIGGERED: Bank degradation score {telemetry.bank_switch_degradation_score} >= {self.policy.circuit_breaker_bank_failure_rate_threshold}")
                is_overridden = True
                final_action = ActionType.RETRY_BACKOFF
                sanitized_params = {"delay_minutes": 120}
                reasons.append("Bank switch severely degraded. Overrode immediate retry with exponential backoff.")

        # =========================================================================
        # RULE 7: Promise-to-Pay (PTP) Extension Horizon Validation
        # =========================================================================
        if final_action == ActionType.SCHEDULE_PTP:
            ptp_time = ai_proposal.extracted_ptp_timestamp
            if not ptp_time:
                violations.append("INVALID_PTP: Missing timestamp for scheduled PTP")
                is_overridden = True
                final_action = ActionType.SEND_PAYMENT_LINK
                sanitized_params = {"channel": "WHATSAPP", "method_fallback": "UPI_INTENT"}
                reasons.append("PTP missing valid date; defaulted to payment link.")
            else:
                # Compare naive datetimes consistently
                naive_ptp = ptp_time.replace(tzinfo=None)
                naive_now = now.replace(tzinfo=None) if hasattr(now, "tzinfo") and now.tzinfo else now
                max_horizon = naive_now + timedelta(days=self.policy.max_ptp_extension_days)
                
                if naive_ptp < naive_now:
                    violations.append("INVALID_PTP: Date is in the past")
                    is_overridden = True
                    final_action = ActionType.SEND_PAYMENT_LINK
                    sanitized_params = {"channel": "WHATSAPP", "method_fallback": "UPI_INTENT"}
                    reasons.append("PTP date is in the past; sent immediate payment link instead.")
                elif naive_ptp > max_horizon:
                    violations.append(f"PTP_HORIZON_EXCEEDED: Date exceeds {self.policy.max_ptp_extension_days} days limit")
                    is_overridden = True
                    final_action = ActionType.ESCALATE_HUMAN_OPS
                    sanitized_params = {"reason": f"PTP requested beyond {self.policy.max_ptp_extension_days} days", "priority": "LOW"}
                    reasons.append(f"PTP requested beyond {self.policy.max_ptp_extension_days} days policy limit. Escalated to ops.")

        # =========================================================================
        # RULE 8: Permanent Account Failure Safe Handling
        # =========================================================================
        if ai_proposal.root_cause == RootCauseCategory.PERMANENT_ACCOUNT_FAILURE:
            if final_action in (ActionType.RETRY_IMMEDIATE, ActionType.RETRY_BACKOFF):
                violations.append("UNRECOVERABLE_METHOD_RETRY: Retrying against permanently dead account/card")
                is_overridden = True
                final_action = ActionType.SEND_PAYMENT_LINK
                sanitized_params = {"channel": "SMS", "method_fallback": "NEW_PAYMENT_METHOD_REQUIRED"}
                reasons.append("Blocked hopeless retry on dead method. Requested new payment method.")

        # Parameter validation for RETRY_BACKOFF bounds
        if final_action == ActionType.RETRY_BACKOFF:
            delay = sanitized_params.get("delay_minutes", 60)
            if not isinstance(delay, (int, float)) or delay < 1 or delay > 1440:
                sanitized_params["delay_minutes"] = 60 # Coerce to safe 60-min default

        policy_reason_str = " | ".join(reasons) if reasons else "Approved by deterministic policy gate without override."

        return PolicyDecision(
            is_overridden=is_overridden,
            original_action=ai_proposal.proposed_action,
            final_action=final_action,
            final_parameters=sanitized_params,
            violations_detected=violations,
            policy_reason=policy_reason_str,
            timestamp=now
        )
