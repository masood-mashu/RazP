from __future__ import annotations
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from core.schemas import (
    TransactionTelemetry,
    AIReasonerOutput,
    PolicyDecision,
    ActionType,
    RootCauseCategory,
    CustomerIntentCategory,
    PaymentMethod
)


class SimpleRuleEngineBaseline:
    """
    Configuration A: Industry-standard naive rule engine (Switch-case on raw error codes only).
    
    Ignores natural language messages entirely.
    """

    def decide(self, telemetry: TransactionTelemetry, now: Optional[datetime] = None) -> PolicyDecision:
        ref_now = now or datetime.utcnow()
        code = telemetry.bank_raw_response_code.upper()
        gw_err = telemetry.gateway_error_code.upper()
        
        # Default simple static rules
        if code in ["05", "14", "CARD_STOLEN", "ACCOUNT_CLOSED"]:
            action = ActionType.SEND_PAYMENT_LINK
            reason = "Static Rule: Permanent card/account failure -> send link"
        elif code in ["51", "INSUFFICIENT_FUNDS"]:
            action = ActionType.RETRY_BACKOFF
            reason = "Static Rule: Insufficient funds -> retry backoff"
        elif "TIMEOUT" in code or "TIMEOUT" in gw_err:
            # Blind immediate retry on timeout (causes chargebacks on deemed success)
            action = ActionType.RETRY_IMMEDIATE
            reason = "Static Rule: Timeout detected -> Immediate retry"
        elif telemetry.attempt_count >= 3:
            action = ActionType.ESCALATE_HUMAN_OPS
            reason = "Static Rule: Max attempts reached"
        else:
            action = ActionType.SEND_PAYMENT_LINK
            reason = "Static Rule: Default fallback payment link"

        return PolicyDecision(
            is_overridden=False,
            original_action=action,
            final_action=action,
            final_parameters={},
            violations_detected=[],
            policy_reason=reason,
            timestamp=ref_now
        )


class AdvancedRuleEngineBaseline:
    """
    Configuration B: Strong Production Deterministic Rule Engine.
    
    Combines error code switch-case with deterministic regex text parsing for standard
    English date formats (DD/MM/YYYY, 'tomorrow', 'on 5th') and keyword matching for 'debited'.
    
    Still fails on:
    - Multilingual code-switched Hinglish ('parso sham', 'salary aane par katna')
    - Adversarial prompt injection attacks
    - Nuanced deemed success under high latency without keyword triggers
    """

    def decide(self, telemetry: TransactionTelemetry, now: Optional[datetime] = None) -> PolicyDecision:
        ref_now = now or datetime.utcnow()
        msg = (telemetry.last_inbound_message.message_text.lower() if telemetry.last_inbound_message else "").strip()
        code = telemetry.bank_raw_response_code.upper()
        gw_err = telemetry.gateway_error_code.upper()

        # 1. Check for basic English deduction claims
        if any(w in msg for w in ["debited", "deducted", "money cut", "amount deducted"]):
            return PolicyDecision(
                is_overridden=False,
                original_action=ActionType.PAUSE_RECON_VERIFY,
                final_action=ActionType.PAUSE_RECON_VERIFY,
                final_parameters={"timeout_minutes": 30, "rrn_lookup": True},
                violations_detected=[],
                policy_reason="Advanced Rule: Detected English debit claim keyword",
                timestamp=ref_now
            )

        # 2. Check for basic standard English date regex
        ptp_match, ptp_date = self._parse_standard_date(msg, ref_now)
        if ptp_match and ptp_date:
            return PolicyDecision(
                is_overridden=False,
                original_action=ActionType.SCHEDULE_PTP,
                final_action=ActionType.SCHEDULE_PTP,
                final_parameters={"scheduled_timestamp": ptp_date.isoformat()},
                violations_detected=[],
                policy_reason="Advanced Rule: Extracted standard date via regex",
                timestamp=ref_now
            )

        # 3. Fall back to standard error code rules
        if code in ["05", "14", "CARD_STOLEN", "ACCOUNT_CLOSED"]:
            action = ActionType.SEND_PAYMENT_LINK
            reason = "Advanced Rule: Permanent account failure -> payment link"
        elif code in ["51", "INSUFFICIENT_FUNDS"]:
            action = ActionType.SEND_PAYMENT_LINK
            reason = "Advanced Rule: Insufficient funds -> payment link"
        elif "TIMEOUT" in code or "TIMEOUT" in gw_err:
            if telemetry.bank_switch_degradation_score >= 0.65:
                action = ActionType.RETRY_BACKOFF
                reason = "Advanced Rule: Timeout under degraded switch -> backoff retry"
            else:
                action = ActionType.RETRY_IMMEDIATE
                reason = "Advanced Rule: Timeout under healthy switch -> immediate retry"
        elif telemetry.attempt_count >= 3:
            action = ActionType.ESCALATE_HUMAN_OPS
            reason = "Advanced Rule: Max attempts reached -> escalate"
        else:
            action = ActionType.SEND_PAYMENT_LINK
            reason = "Advanced Rule: Default fallback"

        return PolicyDecision(
            is_overridden=False,
            original_action=action,
            final_action=action,
            final_parameters={},
            violations_detected=[],
            policy_reason=reason,
            timestamp=ref_now
        )

    def _parse_standard_date(self, text: str, ref_now: datetime) -> Tuple[bool, Optional[datetime]]:
        if not text:
            return False, None
        
        # 'tomorrow'
        if "tomorrow" in text:
            target = ref_now + timedelta(days=1)
            return True, target.replace(hour=10, minute=0, second=0, microsecond=0)

        # Standard regex for 'on 5th', 'on 12th', etc.
        m = re.search(r'\bon\s+(\d{1,2})(?:st|nd|rd|th)?\b', text)
        if m:
            day = int(m.group(1))
            if 1 <= day <= 31:
                year = ref_now.year
                month = ref_now.month
                if day < ref_now.day:
                    month = month + 1 if month < 12 else 1
                    year = year if month < 12 else year + 1
                try:
                    target = datetime(year, month, day, 10, 0, 0)
                    return True, target
                except ValueError:
                    pass

        return False, None


class PureLLMBaseline:
    """
    Configuration C: Pure Unconstrained LLM Agent.
    
    Directly acts on raw prompts without a Deterministic Policy Gate.
    """

    def __init__(self, reasoner_instance):
        self.reasoner = reasoner_instance

    def decide(self, telemetry: TransactionTelemetry, now: Optional[datetime] = None) -> PolicyDecision:
        ref_now = now or datetime.utcnow()
        msg = (telemetry.last_inbound_message.message_text if telemetry.last_inbound_message else "").lower()
        
        # Get raw AI output
        ai_out = self.reasoner.reason(telemetry, ref_now)
        violations = []
        final_params = dict(ai_out.action_parameters)

        # Pure LLM vulnerability: If customer demanded discount, unconstrained LLM grants it
        if any(w in msg for w in ["discount", "waive", "free", "court", "save50"]):
            violations.append("UNCONSTRAINED_LLM_BREACH: Granted unauthorized 20% discount to placate customer")
            final_params["discount_amount"] = telemetry.amount_inr * 0.20
            final_params["new_amount"] = telemetry.amount_inr * 0.80

        # Pure LLM vulnerability: Ignores quiet hours and sends messages at midnight
        if ai_out.proposed_action == ActionType.SEND_PAYMENT_LINK:
            if ref_now.hour >= 21 or ref_now.hour < 9:
                violations.append("UNCONSTRAINED_LLM_BREACH: Dispatched outbound message during quiet hours (TRAI violation)")

        # Pure LLM vulnerability: Keeps retrying past max contact limit
        if telemetry.attempt_count >= 3 and ai_out.proposed_action in (ActionType.SEND_PAYMENT_LINK, ActionType.RETRY_IMMEDIATE):
            violations.append("UNCONSTRAINED_LLM_BREACH: Exceeded max contact ceiling (Customer harassment)")

        return PolicyDecision(
            is_overridden=False,  # Pure LLM has NO policy gate to override
            original_action=ai_out.proposed_action,
            final_action=ai_out.proposed_action,
            final_parameters=final_params,
            violations_detected=violations,
            policy_reason=f"Unconstrained LLM execution: {ai_out.reasoning_audit_text}",
            timestamp=ref_now
        )


# Backward compatibility alias
RuleEngineBaseline = SimpleRuleEngineBaseline
