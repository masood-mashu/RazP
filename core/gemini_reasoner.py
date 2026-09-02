from __future__ import annotations
import os
import time
import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from core.schemas import (
    TransactionTelemetry,
    AIReasonerOutput,
    RootCauseCategory,
    CustomerIntentCategory,
    ActionType,
    PaymentMethod
)

PROMPT_VERSION = "v1.0.0"
SCHEMA_VERSION = "v1.0.0"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")


def load_versioned_prompt() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "reasoner_v1.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return "You are Sentinel-Recover's AI Semantic Reasoner for Razorpay."


def _gemini_response_schema() -> Dict[str, Any]:
    """Return a clean, fully-dereferenced Developer API-compatible JSON schema for constrained output."""
    return {
        "type": "OBJECT",
        "properties": {
            "root_cause": {
                "type": "STRING",
                "enum": [e.value for e in RootCauseCategory],
                "description": "Diagnosed root cause category of payment failure."
            },
            "customer_intent": {
                "type": "STRING",
                "enum": [e.value for e in CustomerIntentCategory],
                "description": "Classified customer intent."
            },
            "claim_debit_occurred": {
                "type": "BOOLEAN",
                "description": "True if customer claims money was debited."
            },
            "extracted_ptp_timestamp": {
                "type": "STRING",
                "nullable": True,
                "description": "ISO-8601 string if customer gave a date, else null."
            },
            "proposed_action": {
                "type": "STRING",
                "enum": [e.value for e in ActionType],
                "description": "Proposed recovery action."
            },
            "action_parameters": {
                "type": "OBJECT",
                "description": "Optional parameters."
            },
            "confidence": {
                "type": "NUMBER",
                "description": "Confidence score between 0.0 and 1.0."
            },
            "reasoning_audit_text": {
                "type": "STRING",
                "description": "Concise explainability rationale."
            }
        },
        "required": [
            "root_cause",
            "customer_intent",
            "claim_debit_occurred",
            "proposed_action",
            "confidence",
            "reasoning_audit_text"
        ]
    }


class GeminiReasoner:
    """
    Production-grade Gemini Semantic Reasoner Adapter.
    Uses modern `google-genai` SDK with native response_schema constrained decoding.
    
    CRITICAL INVARIANT: The AI only performs semantic interpretation and proposal generation.
    It has zero direct authority over monetary values, ledger state, or policy execution.
    """

    def __init__(self, api_key: Any = "USE_ENV", model: Optional[str] = None):
        # 1. API Key resolution: explicit argument first, GEMINI_API_KEY second, GOOGLE_API_KEY third
        if api_key == "USE_ENV":
            self.api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        else:
            self.api_key = api_key
        
        # 2. Configurable model via environment variable
        self.model_name = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        
        self.prompt_template = load_versioned_prompt()
        self._client = None
        
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                self._client = None

    def reason(self, telemetry: TransactionTelemetry, reference_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Executes semantic reasoning over telemetry and returns structured provenance.
        """
        ref_now = reference_time or datetime.utcnow()
        start_time = time.perf_counter()
        
        # 1. Attempt Live Gemini Structured Reasoning
        if self._client:
            try:
                prompt = self._build_prompt(telemetry, ref_now)
                
                # Fast, schema-constrained structured JSON output with Pydantic runtime validation
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": _gemini_response_schema(),
                        "temperature": 0.1
                    }
                )
                
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                
                if response and response.text:
                    parsed = json.loads(response.text)
                    # Normalize SCHEDULE_PTP timestamp requirement
                    if parsed.get("proposed_action") == ActionType.SCHEDULE_PTP.value and not parsed.get("extracted_ptp_timestamp"):
                        _, extracted_dt = self._extract_ptp_date(telemetry.last_inbound_message.message_text if telemetry.last_inbound_message else "", ref_now)
                        if extracted_dt:
                            parsed["extracted_ptp_timestamp"] = extracted_dt.isoformat()
                        else:
                            parsed["proposed_action"] = ActionType.ESCALATE_HUMAN_OPS.value

                    validated_output = AIReasonerOutput(**parsed)
                    
                    return {
                        "reasoner_output": validated_output,
                        "is_live_gemini": True,
                        "fallback_used": False,
                        "model": self.model_name,
                        "latency_ms": elapsed_ms,
                        "error": None,
                        "prompt_version": PROMPT_VERSION,
                        "schema_version": SCHEMA_VERSION
                    }
            except Exception as e:
                # Safe secret-redacted error reporting
                raw_err = str(e)
                redacted_err = re.sub(r'key=[A-Za-z0-9_\-]+', 'key=REDACTED', raw_err)
                if self.api_key:
                    redacted_err = redacted_err.replace(self.api_key, "REDACTED_API_KEY")
                
                elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                fallback_out = self._heuristic_reason(telemetry, ref_now)
                
                return {
                    "reasoner_output": fallback_out,
                    "is_live_gemini": False,
                    "fallback_used": True,
                    "model": f"{self.model_name} (Fallback)",
                    "latency_ms": elapsed_ms,
                    "error": f"Live Gemini Exception: {redacted_err[:120]}",
                    "prompt_version": PROMPT_VERSION,
                    "schema_version": SCHEMA_VERSION
                }

        # 2. Offline Deterministic Fallback Mode (No API Key Present)
        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        fallback_out = self._heuristic_reason(telemetry, ref_now)
        
        return {
            "reasoner_output": fallback_out,
            "is_live_gemini": False,
            "fallback_used": True,
            "model": "DeterministicHeuristicFallback",
            "latency_ms": elapsed_ms,
            "error": "No API key configured (Offline Fallback Mode)",
            "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION
        }

    def _build_prompt(self, telemetry: TransactionTelemetry, ref_now: datetime) -> str:
        msg_text = telemetry.last_inbound_message.message_text if telemetry.last_inbound_message else "[NO INBOUND MESSAGE]"
        channel = telemetry.last_inbound_message.channel.value if telemetry.last_inbound_message else "NONE"
        
        return f"""{self.prompt_template}

CURRENT TRANSACTION TELEMETRY:
- Payment ID: {telemetry.payment_id}
- Amount: ₹{telemetry.amount_inr} {telemetry.currency}
- Method: {telemetry.payment_method.value}
- Gateway Error: {telemetry.gateway_error_code}
- Bank Raw Code: {telemetry.bank_raw_response_code}
- Observed Latency: {telemetry.latency_ms} ms
- Bank Switch Degradation Score: {telemetry.bank_switch_degradation_score}
- Attempt Count: {telemetry.attempt_count}
- Mandate Status: {telemetry.mandate_status}
- Inbound Customer Message ({channel}): "{msg_text}"
- Evaluation Timestamp (IST): {ref_now.isoformat()}

Respond with the exact structured JSON object matching the output schema."""

    def _heuristic_reason(self, telemetry: TransactionTelemetry, ref_now: datetime) -> AIReasonerOutput:
        """
        High-fidelity deterministic fallback parser ensuring 100% fail-safe continuity.
        """
        msg = (telemetry.last_inbound_message.message_text.lower() if telemetry.last_inbound_message else "").strip()
        code = telemetry.bank_raw_response_code.upper()
        gw_err = telemetry.gateway_error_code.upper()

        # Check for Prompt Injections / Exploit attempts / Legal threats
        exploit_triggers = [
            "ignore previous", "system prompt", "system override", "discount",
            "waive", "free", "court", "legal notice", "consumer forum", "save50", "promo"
        ]
        if any(w in msg for w in exploit_triggers):
            return AIReasonerOutput(
                root_cause=RootCauseCategory.INSUFFICIENT_FUNDS if "51" in code else RootCauseCategory.UNKNOWN_AMBIGUOUS,
                customer_intent=CustomerIntentCategory.EXPLOITATIVE_ADVERSARIAL,
                claim_debit_occurred=False,
                proposed_action=ActionType.SEND_PAYMENT_LINK,
                action_parameters={"channel": "WHATSAPP", "notes": "Exploitative prompt ignored"},
                confidence=0.92,
                reasoning_audit_text="Detected exploitative request or prompt injection. Enforcing standard invoice amount."
            )

        # Check for Deduction Claims (Hinglish/Hindi/English keywords)
        debit_keywords = ["kat gaye", "kata", "debit", "debited", "cut", "deducted", "paise chale gaye", "amount debited", "balance cut"]
        if any(kw in msg for kw in debit_keywords) or code in ["U19", "96", "SUSPECTED_DEEMED_SUCCESS"]:
            return AIReasonerOutput(
                root_cause=RootCauseCategory.SUSPECTED_DEEMED_SUCCESS,
                customer_intent=CustomerIntentCategory.DISPUTE_CLAIMED if msg else CustomerIntentCategory.NO_COMMUNICATION,
                claim_debit_occurred=True,
                proposed_action=ActionType.PAUSE_RECON_VERIFY,
                action_parameters={"timeout_minutes": 30, "rrn_lookup": True},
                confidence=0.96,
                reasoning_audit_text="Customer claimed balance deduction or high-risk timeout observed. Halting retries for settlement recon."
            )

        # Check for Promise-to-Pay (PTP) Intent and dates in Hinglish / English
        ptp_match, extracted_dt = self._extract_ptp_date(msg, ref_now)
        if ptp_match:
            return AIReasonerOutput(
                root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
                customer_intent=CustomerIntentCategory.DELAY_REQUESTED_PTP,
                claim_debit_occurred=False,
                extracted_ptp_timestamp=extracted_dt,
                proposed_action=ActionType.SCHEDULE_PTP,
                action_parameters={"scheduled_timestamp": extracted_dt.isoformat()},
                confidence=0.94,
                reasoning_audit_text=f"Extracted valid customer Promise-to-Pay date: {extracted_dt.strftime('%Y-%m-%d %H:%M')}"
            )

        # Check for Permanent Account Failures (Stolen, Blocked, Closed)
        if code in ["05", "14", "41", "43", "ACCOUNT_CLOSED", "INVALID_VPA", "CARD_STOLEN"]:
            return AIReasonerOutput(
                root_cause=RootCauseCategory.PERMANENT_ACCOUNT_FAILURE,
                customer_intent=CustomerIntentCategory.NO_COMMUNICATION if not msg else CustomerIntentCategory.COOPERATIVE_WILL_PAY,
                claim_debit_occurred=False,
                proposed_action=ActionType.SEND_PAYMENT_LINK,
                action_parameters={"channel": "SMS", "method_fallback": "NEW_PAYMENT_METHOD_REQUIRED"},
                confidence=0.98,
                reasoning_audit_text="Permanent account or token failure. Bypassing retries and requesting new payment method."
            )

        # Check for Bank Switch Degradation
        if telemetry.bank_switch_degradation_score >= 0.5 or code in ["91", "ZH", "BANK_DOWN"]:
            return AIReasonerOutput(
                root_cause=RootCauseCategory.BANK_SWITCH_DEGRADATION,
                customer_intent=CustomerIntentCategory.NO_COMMUNICATION,
                claim_debit_occurred=False,
                proposed_action=ActionType.RETRY_BACKOFF,
                action_parameters={"delay_minutes": 60},
                confidence=0.91,
                reasoning_audit_text="Bank issuer switch degraded. Triggering exponential backoff retry."
            )

        # Check for Transient Network Glitch
        if telemetry.latency_ms < 1000 and telemetry.bank_switch_degradation_score < 0.2 and code in ["TIMEOUT", "GATEWAY_TIMEOUT", "NET_ERR"]:
            return AIReasonerOutput(
                root_cause=RootCauseCategory.TRANSIENT_NETWORK_GLITCH,
                customer_intent=CustomerIntentCategory.NO_COMMUNICATION,
                claim_debit_occurred=False,
                proposed_action=ActionType.RETRY_IMMEDIATE,
                action_parameters={},
                confidence=0.88,
                reasoning_audit_text="Transient gateway network glitch on healthy switch. Immediate retry authorized."
            )

        # Insufficient funds default
        if code in ["51", "U30", "LIMIT_EXCEEDED", "INSUFFICIENT_FUNDS"]:
            return AIReasonerOutput(
                root_cause=RootCauseCategory.INSUFFICIENT_FUNDS,
                customer_intent=CustomerIntentCategory.NO_COMMUNICATION if not msg else CustomerIntentCategory.COOPERATIVE_WILL_PAY,
                claim_debit_occurred=False,
                proposed_action=ActionType.SEND_PAYMENT_LINK,
                action_parameters={"channel": "WHATSAPP", "method_fallback": "UPI_INTENT"},
                confidence=0.85,
                reasoning_audit_text="Insufficient funds or limit breach. Sent interactive payment link."
            )

        # Default fallback
        return AIReasonerOutput(
            root_cause=RootCauseCategory.UNKNOWN_AMBIGUOUS,
            customer_intent=CustomerIntentCategory.NO_COMMUNICATION,
            claim_debit_occurred=False,
            proposed_action=ActionType.SEND_PAYMENT_LINK,
            action_parameters={"channel": "WHATSAPP"},
            confidence=0.70,
            reasoning_audit_text="Standard fallback payment link dispatched."
        )

    def _extract_ptp_date(self, text: str, ref_now: datetime) -> Tuple[bool, Optional[datetime]]:
        if not text:
            return False, None

        text = text.lower()
        
        # 'kal' / 'tomorrow'
        if "kal" in text or "tomorrow" in text:
            target = ref_now + timedelta(days=1)
            return True, target.replace(hour=10, minute=0, second=0, microsecond=0)

        # 'parso' / 'day after tomorrow'
        if "parso" in text or "day after tomorrow" in text:
            target = ref_now + timedelta(days=2)
            return True, target.replace(hour=10, minute=0, second=0, microsecond=0)

        # 'salary on X' or 'X ko' or 'Xth' or 'X tareek'
        digit_match = re.search(r'(\d{1,2})\s*(?:ko|th|st|nd|rd|tareek|tarik|date)', text)
        if digit_match:
            day = int(digit_match.group(1))
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

        # 'after X days' / 'X din baad'
        days_match = re.search(r'(\d+)\s*(?:days|din|day)\s*(?:baad|after|later)', text)
        if days_match:
            d = int(days_match.group(1))
            target = ref_now + timedelta(days=d)
            return True, target.replace(hour=10, minute=0, second=0, microsecond=0)

        return False, None
