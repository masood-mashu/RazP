from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, time
from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# ENUMS & CONSTANTS
# =============================================================================

class PolicyClassification(str, Enum):
    VERIFIED_REGULATORY = "VERIFIED_REGULATORY"    # e.g., TRAI TCCCPR, RBI e-Mandate
    MERCHANT_SAFETY_POLICY = "MERCHANT_SAFETY_POLICY" # e.g., Max 3 retries, Zero discounts
    BENCHMARK_ASSUMPTION = "BENCHMARK_ASSUMPTION"   # e.g., Cost modeling, simulated customer response


class PaymentMethod(str, Enum):
    UPI_AUTOPAY = "UPI_AUTOPAY"
    CARD_MANDATE = "CARD_MANDATE"
    NETBANKING = "NETBANKING"
    UPI_COLLECT = "UPI_COLLECT"
    CARD_ONE_TIME = "CARD_ONE_TIME"


class PaymentState(str, Enum):
    PAYMENT_FAILED = "PAYMENT_FAILED"
    TELEMETRY_ANALYSIS = "TELEMETRY_ANALYSIS"
    DEDUCTION_SUSPECTED = "DEDUCTION_SUSPECTED"
    PAUSE_RECON_VERIFY = "PAUSE_RECON_VERIFY"
    POLICY_GATED = "POLICY_GATED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    PTP_SCHEDULED = "PTP_SCHEDULED"
    AWAITING_CUSTOMER_ACTION = "AWAITING_CUSTOMER_ACTION"
    RECOVERED = "RECOVERED"
    DEAD_LETTER = "DEAD_LETTER"
    ESCALATED_HUMAN_OPS = "ESCALATED_HUMAN_OPS"


class ActionType(str, Enum):
    RETRY_IMMEDIATE = "RETRY_IMMEDIATE"          # a1
    RETRY_BACKOFF = "RETRY_BACKOFF"              # a2
    SEND_PAYMENT_LINK = "SEND_PAYMENT_LINK"      # a3
    SCHEDULE_PTP = "SCHEDULE_PTP"                # a4
    PAUSE_RECON_VERIFY = "PAUSE_RECON_VERIFY"    # a5
    ESCALATE_HUMAN_OPS = "ESCALATE_HUMAN_OPS"    # a6
    ABSTAIN_DO_NOTHING = "ABSTAIN_DO_NOTHING"    # a7


class RootCauseCategory(str, Enum):
    TRANSIENT_NETWORK_GLITCH = "TRANSIENT_NETWORK_GLITCH"
    BANK_SWITCH_DEGRADATION = "BANK_SWITCH_DEGRADATION"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    USER_LIMIT_EXCEEDED = "USER_LIMIT_EXCEEDED"
    MANDATE_EXPIRED_OR_REVOKED = "MANDATE_EXPIRED_OR_REVOKED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    PERMANENT_ACCOUNT_FAILURE = "PERMANENT_ACCOUNT_FAILURE"
    SUSPECTED_DEEMED_SUCCESS = "SUSPECTED_DEEMED_SUCCESS"
    UNKNOWN_AMBIGUOUS = "UNKNOWN_AMBIGUOUS"


class CustomerIntentCategory(str, Enum):
    COOPERATIVE_WILL_PAY = "COOPERATIVE_WILL_PAY"
    DELAY_REQUESTED_PTP = "DELAY_REQUESTED_PTP"
    DISPUTE_CLAIMED = "DISPUTE_CLAIMED"
    HOSTILE_OR_CHURNED = "HOSTILE_OR_CHURNED"
    EXPLOITATIVE_ADVERSARIAL = "EXPLOITATIVE_ADVERSARIAL"
    NO_COMMUNICATION = "NO_COMMUNICATION"


class CommunicationChannel(str, Enum):
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    EMAIL = "EMAIL"
    PORTAL = "PORTAL"
    NONE = "NONE"


# =============================================================================
# INPUT TELEMETRY & POLICIES
# =============================================================================

class CustomerMessage(BaseModel):
    message_text: str = Field(..., min_length=1)
    channel: CommunicationChannel = CommunicationChannel.WHATSAPP
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TransactionTelemetry(BaseModel):
    payment_id: str = Field(..., min_length=1)
    invoice_id: str = Field(..., min_length=1)
    amount_inr: float = Field(gt=0, description="Amount in INR, strictly positive")
    currency: str = "INR"
    gateway_error_code: str = Field(..., description="e.g. BAD_REQUEST_ERROR, GATEWAY_ERROR")
    bank_raw_response_code: str = Field(..., description="e.g. NPCI U30, U19, ZM, Card 51, 05, 96")
    payment_method: PaymentMethod
    latency_ms: int = Field(ge=0, description="Observed gateway/bank roundtrip latency")
    bank_switch_degradation_score: float = Field(ge=0.0, le=1.0, description="Degradation level [0, 1]")
    attempt_count: int = Field(default=1, ge=1)
    historical_success_rate_user: float = Field(default=0.8, ge=0.0, le=1.0)
    mandate_status: str = Field(default="ACTIVE")
    last_inbound_message: Optional[CustomerMessage] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("amount_inr")
    def validate_positive_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Transaction amount must be strictly positive")
        return round(v, 2)


class MerchantPolicy(BaseModel):
    merchant_id: str = "rzp_merchant_prod"
    
    # Category A: Verified External Regulations
    quiet_hours_start: time = Field(default=time(21, 0), description="TRAI TCCCPR 2018 Regulation (9:00 PM IST)")
    quiet_hours_end: time = Field(default=time(9, 0), description="TRAI TCCCPR 2018 Regulation (9:00 AM IST)")
    
    # Category B: Merchant / Product Safety Policies
    max_contact_attempts: int = Field(default=3, ge=1, description="Merchant Anti-Harassment Policy")
    max_ptp_extension_days: int = Field(default=14, ge=1, description="Merchant Credit Extension Horizon Policy")
    allow_discounts: bool = Field(default=False, description="Strict Financial Invariant: Automated discounts forbidden")
    circuit_breaker_bank_failure_rate_threshold: float = Field(default=0.65, ge=0.0, le=1.0, description="Merchant Circuit Breaker Policy")
    
    # Category C: Benchmark & Economic Cost Assumptions
    cost_per_sms: float = Field(default=0.15, description="Benchmark Assumption: SMS dispatch cost")
    cost_per_whatsapp: float = Field(default=0.50, description="Benchmark Assumption: WhatsApp interactive message cost")
    cost_per_llm_inference: float = Field(default=0.10, description="Benchmark Assumption: Gemini Flash inference cost")
    cost_per_failed_bank_retry: float = Field(default=5.00, description="Benchmark Assumption: Bank bounce penalty")
    chargeback_dispute_fee: float = Field(default=50.00, description="Benchmark Assumption: Customer chargeback filing fee")


# =============================================================================
# REASONER SCHEMAS & POLICIES
# =============================================================================

class AIReasonerOutput(BaseModel):
    """
    Rigidly schema-validated AI output from Gemini Reasoner.
    Invariant: AI output CANNOT directly mutate ledger or declare payment recovered.
    """
    root_cause: RootCauseCategory
    customer_intent: CustomerIntentCategory
    claim_debit_occurred: bool = Field(default=False, description="True if customer claims money was deducted")
    extracted_ptp_timestamp: Optional[datetime] = Field(default=None, description="ISO timestamp if customer committed a date")
    proposed_action: ActionType
    action_parameters: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_audit_text: str = Field(..., min_length=5, description="Concise explainability rationale")

    @model_validator(mode="after")
    def validate_action_consistency(self) -> AIReasonerOutput:
        if self.proposed_action == ActionType.SCHEDULE_PTP and not self.extracted_ptp_timestamp:
            raise ValueError("SCHEDULE_PTP requires a valid extracted_ptp_timestamp")
        return self


class PolicyDecision(BaseModel):
    """The result of passing AIReasonerOutput through the Deterministic Policy Gate."""
    is_overridden: bool
    original_action: ActionType
    final_action: ActionType
    final_parameters: Dict[str, Any]
    violations_detected: List[str] = Field(default_factory=list)
    policy_reason: str
    ai_root_cause: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExecutionResult(BaseModel):
    success: bool
    action_executed: ActionType
    resulting_state: PaymentState
    details: Dict[str, Any] = Field(default_factory=dict)
    financial_cost_incurred: float = 0.0
    recovered_amount: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AuditBlock(BaseModel):
    index: int
    timestamp: str
    payment_id: str
    telemetry_hash: str
    ai_reasoning: Optional[Dict[str, Any]]
    policy_decision: Dict[str, Any]
    action_executed: str
    resulting_state: str
    previous_hash: str
    current_hash: str
