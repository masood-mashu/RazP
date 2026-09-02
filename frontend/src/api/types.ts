export type PaymentState =
  | 'PAYMENT_FAILED'
  | 'TELEMETRY_ANALYSIS'
  | 'POLICY_GATED'
  | 'DEDUCTION_SUSPECTED'
  | 'PAUSE_RECON_VERIFY'
  | 'RETRY_SCHEDULED'
  | 'AWAITING_CUSTOMER_ACTION'
  | 'PTP_SCHEDULED'
  | 'RECOVERED'
  | 'DEAD_LETTER'
  | 'ESCALATED_HUMAN_OPS';

export type ActionType =
  | 'RETRY_IMMEDIATE'
  | 'SCHEDULE_RETRY'
  | 'SEND_PAYMENT_LINK'
  | 'REQUEST_PTP_EXTENSION'
  | 'PAUSE_RECON_VERIFY'
  | 'SUPPRESS_MANDATE_REVOKED'
  | 'ESCALATE_HUMAN_OPS'
  | 'NO_OP';

export interface StateTransition {
  from_state: PaymentState;
  to_state: PaymentState;
  reason: string;
  transition_order?: number;
  created_at?: string;
  timestamp?: string;
}

export interface PaymentCase {
  payment_id: string;
  invoice_id: string;
  amount_inr: number;
  current_state: PaymentState;
  attempt_count: number;
  contact_count: number;
  is_terminal: boolean;
  created_at: string;
  updated_at: string;
  payment_method?: string;
  transitions?: StateTransition[];
}

export interface DashboardStats {
  total_cases: number;
  active_cases: number;
  recovered_cases: number;
  escalated_cases: number;
  dead_letter_cases: number;
  stopped_cases?: number;
  revenue_at_risk: number;
  recovered_revenue: number;
  total_exposure: number;
  total_ingested_exposure?: number;
  recovery_yield_pct: number;
}

export interface SystemStatus {
  status: string;
  service: string;
  persistence_layer: string;
  ai_provider: string;
  model: string;
  prompt_version: string;
  schema_version: string;
  is_live_gemini: boolean;
  fallback_active: boolean;
  active_policy_merchant_id: string;
  invariants_verified: string[];
}

export interface PolicyDecision {
  is_overridden: boolean;
  original_action: ActionType;
  final_action: ActionType;
  authorized_action?: string;
  override_reason?: string;
  final_parameters: Record<string, any>;
  violations_detected: string[];
  policy_reason: string;
  ai_root_cause?: string;
  timestamp: string;
}

export interface AIReasonerOutput {
  root_cause: string;
  customer_intent: string;
  extracted_ptp_timestamp?: string;
  claim_debit_occurred: boolean;
  customer_claims_money_debited?: boolean;
  proposed_action: ActionType;
  proposed_parameters: Record<string, any>;
  confidence: number;
  reasoning_audit_text: string;
  action_rationale?: string;
}

export interface AuditBlock {
  index: number;
  block_index?: number;
  timestamp: string;
  payment_id: string;
  telemetry_hash: string;
  payload_hash?: string;
  actor_id?: string;
  correlation_id?: string;
  ai_reasoning?: AIReasonerOutput | null;
  policy_decision: PolicyDecision;
  action_executed: string;
  resulting_state: string;
  previous_hash: string;
  current_hash: string;
}

export interface LedgerResponse {
  persistence_source: string;
  is_integrity_valid: boolean;
  integrity_error?: string | null;
  total_blocks: number;
  blocks: AuditBlock[];
}

export interface MerchantPolicy {
  merchant_id: string;
  quiet_hours_start: string;
  quiet_hours_end: string;
  max_contact_attempts: number;
  max_ptp_extension_days: number;
  allow_discounts: boolean;
  circuit_breaker_bank_failure_rate_threshold: number;
  cost_per_sms: number;
  cost_per_whatsapp: number;
  cost_per_llm_inference: number;
  cost_per_failed_bank_retry: number;
  chargeback_dispute_fee: number;
}

export interface SingleEvalRequest {
  payment_id: string;
  invoice_id: string;
  amount_inr: number;
  gateway_error_code: string;
  bank_raw_response_code: string;
  payment_method: string;
  latency_ms: number;
  bank_switch_degradation_score: number;
  attempt_count: number;
  inbound_message?: string;
  channel: string;
}

export interface SingleEvalResponse {
  payment_id?: string;
  final_state?: string;
  telemetry?: any;
  ai_reasoning: AIReasonerOutput;
  ai_provenance?: {
    model: string;
    prompt_version?: string;
    schema_version?: string;
    latency_ms: number;
    is_live_gemini?: boolean;
    fallback_used?: boolean;
    error?: string | null;
  };
  reasoner_meta?: {
    model: string;
    is_fallback: boolean;
    correlation_id: string;
    actor_id: string;
  };
  policy_decision: PolicyDecision;
  state_transitions: any[];
  execution_result: any;
  audit_block?: AuditBlock;
}

export interface AblationSystemResult {
  system_name: string;
  total_cases: number;
  total_amount_at_risk_inr: number;
  total_amount_recovered_inr: number;
  net_recovered_amount_inr: number;
  recovery_rate_pct: number;
  net_money_recovered_ratio_pct: number;
  unsafe_actions_attempted: number;
  unsafe_actions_executed: number;
  guardrail_interventions: number;
  wasted_interventions: number;
  chargebacks_triggered: number;
  total_operational_cost_inr: number;
  action_accuracy_pct: number;
  root_cause_macro_f1: number;
  ptp_extraction_accuracy_pct: number;
  debit_claim_misses: number;
  abstention_precision_pct: number;
  case_results?: any[];
}

export interface BenchmarkSummary {
  dataset_metadata?: {
    total_held_out_cases: number;
    dataset_file: string;
    sha256_checksum: string;
    total_exposure_at_risk_inr: number;
    provenance_description: string;
  };
  evaluation_dataset?: {
    total_held_out_cases: number;
    dataset_file: string;
    dataset_sha256: string;
    split?: string;
  };
  six_way_ablation: {
    eval_mode: string;
    eval_mode_label: string;
    total_cases: number;
    timestamp: string;
    systems: Record<string, AblationSystemResult>;
  };
  live_gemini_evaluation: {
    eval_mode: string;
    eval_mode_label: string;
    total_cases: number;
    live_calls: number;
    fallback_calls: number;
    model_configured: string;
    action_accuracy_pct: number;
    recovery_rate_pct: number;
    root_cause_macro_f1: number;
    customer_intent_macro_f1: number;
    ptp_extraction_accuracy_pct: number;
    ptp_date_mae_days: number;
    total_amount_at_risk_inr: number;
    gross_recovered_inr: number;
    net_recovered_inr: number;
    net_money_recovered_ratio_pct: number;
    unsafe_actions_proposed: number;
    unsafe_actions_executed: number;
    guardrail_interventions: number;
    chargebacks_triggered: number;
    latency_ms: {
      mean: number;
      median: number;
      p95: number;
    };
  };
  metric_definitions: Record<string, string>;
}
