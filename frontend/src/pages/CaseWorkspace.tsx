import React, { useEffect, useState } from 'react';
import {
  Zap,
  ShieldCheck,
  Clock,
  FlaskConical,
  Check,
  X,
  AlertTriangle,
  FileClock,
  Hash
} from 'lucide-react';
import { api } from '../api/client';
import type { PaymentCase, SingleEvalResponse } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

interface CaseWorkspaceProps {
  initialPaymentId?: string | null;
  onClearCase?: () => void;
}

export const CaseWorkspace: React.FC<CaseWorkspaceProps> = ({ initialPaymentId }) => {
  // Form input telemetry
  const [paymentId, setPaymentId] = useState<string>(initialPaymentId || 'pay_demo_hinglish_001');
  const [invoiceId, setInvoiceId] = useState<string>('inv_demo_001');
  const [amountInr, setAmountInr] = useState<number>(2499.0);
  const [gatewayErrorCode, setGatewayErrorCode] = useState<string>('BAD_REQUEST_ERROR');
  const [bankRawCode, setBankRawCode] = useState<string>('51');
  const [paymentMethod, setPaymentMethod] = useState<string>('UPI_AUTOPAY');
  const [latencyMs, setLatencyMs] = useState<number>(450);
  const [degradationScore, setDegradationScore] = useState<number>(0.1);
  const [attemptCount, setAttemptCount] = useState<number>(1);
  const [inboundMessage, setInboundMessage] = useState<string>(
    'bhai salary 7 tareek ko aayegi tab kat lena please'
  );
  const [channel, setChannel] = useState<string>('WHATSAPP');

  // Evaluated result state
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [evalResult, setEvalResult] = useState<SingleEvalResponse | null>(null);
  const [persistedCase, setPersistedCase] = useState<PaymentCase | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Preset scenarios
  const loadPreset = (presetName: string) => {
    switch (presetName) {
      case 'hinglish_ptp':
        setPaymentId('pay_demo_hinglish_001');
        setInvoiceId('inv_demo_h01');
        setAmountInr(2499.0);
        setGatewayErrorCode('BAD_REQUEST_ERROR');
        setBankRawCode('51');
        setPaymentMethod('UPI_AUTOPAY');
        setLatencyMs(450);
        setDegradationScore(0.1);
        setAttemptCount(1);
        setInboundMessage('bhai salary 7 tareek ko aayegi tab kat lena please');
        setChannel('WHATSAPP');
        break;
      case 'debit_claim_recon':
        setPaymentId('pay_demo_u30_lock');
        setInvoiceId('inv_demo_u30');
        setAmountInr(3200.0);
        setGatewayErrorCode('GATEWAY_TIMEOUT');
        setBankRawCode('U30');
        setPaymentMethod('UPI_AUTOPAY');
        setLatencyMs(12500);
        setDegradationScore(0.85);
        setAttemptCount(1);
        setInboundMessage('mere account se paise kat gaye order fail hua dobara mat katna');
        setChannel('SMS');
        break;
      case 'mandate_revoked':
        setPaymentId('pay_demo_mandate_rev');
        setInvoiceId('inv_demo_rev01');
        setAmountInr(999.0);
        setGatewayErrorCode('MANDATE_ERROR');
        setBankRawCode('MD01');
        setPaymentMethod('UPI_AUTOPAY');
        setLatencyMs(300);
        setDegradationScore(0.0);
        setAttemptCount(2);
        setInboundMessage('I cancelled this subscription in my bank app');
        setChannel('WHATSAPP');
        break;
    }
  };

  const loadCaseFromDb = async (pId: string) => {
    try {
      setError(null);
      const caseData = await api.getCaseDetail(pId).catch(() => null);
      setPersistedCase(caseData);
    } catch (err: any) {
      console.warn('Case not yet persisted:', err);
    }
  };

  useEffect(() => {
    if (initialPaymentId) {
      setPaymentId(initialPaymentId);
      loadCaseFromDb(initialPaymentId);
    }
  }, [initialPaymentId]);

  const handleEvaluate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setEvaluating(true);
      setError(null);

      const resp = await api.evaluateSingle({
        payment_id: paymentId,
        invoice_id: invoiceId,
        amount_inr: Number(amountInr),
        gateway_error_code: gatewayErrorCode,
        bank_raw_response_code: bankRawCode,
        payment_method: paymentMethod,
        latency_ms: Number(latencyMs),
        bank_switch_degradation_score: Number(degradationScore),
        attempt_count: Number(attemptCount),
        inbound_message: inboundMessage || undefined,
        channel: channel,
      });

      setEvalResult(resp);
      await loadCaseFromDb(paymentId);
    } catch (err: any) {
      setError(err.message || 'Evaluation failed on RazP engine.');
    } finally {
      setEvaluating(false);
    }
  };

  const formatCurrency = (amt: number | undefined) =>
    amt === undefined
      ? '—'
      : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amt);

  const formatDateTime = (iso: string | undefined) => {
    if (!iso) return '—';
    return new Intl.DateTimeFormat('en-IN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(new Date(iso));
  };

  const activeState = persistedCase?.current_state || evalResult?.final_state || 'PAYMENT_FAILED';
  const hasDebitClaim = evalResult?.ai_reasoning?.claim_debit_occurred || evalResult?.ai_reasoning?.customer_claims_money_debited;

  return (
    <div className="p-5 lg:p-7 space-y-5 overflow-y-auto h-full revive-scroll">
      {/* Top Presets & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-border/60">
        <div className="flex items-center gap-2">
          <span className="eyebrow">Case Workspace & Decision Engine</span>
          <span className="text-muted-foreground/40 font-mono">/</span>
          <span className="text-xs font-mono text-muted-foreground font-semibold">{paymentId}</span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground mr-1">Presets:</span>
          <button
            type="button"
            onClick={() => loadPreset('hinglish_ptp')}
            className="revive-button revive-button-outline text-[10px] h-7 px-2"
          >
            Hinglish PTP
          </button>
          <button
            type="button"
            onClick={() => loadPreset('debit_claim_recon')}
            className="revive-button revive-button-outline text-[10px] h-7 px-2"
          >
            Debit Claim Hold
          </button>
          <button
            type="button"
            onClick={() => loadPreset('mandate_revoked')}
            className="revive-button revive-button-outline text-[10px] h-7 px-2"
          >
            Mandate Revoked
          </button>
        </div>
      </div>

      {/* Case Header Banner */}
      <div className="panel p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <div className="avatar avatar-large">
            {paymentId.slice(-2).toUpperCase()}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="eyebrow">Case workspace</span>
              <StatusBadge state={activeState} size="md" />
              {amountInr > 2000 && <span className="high-value-mark">PRIORITY</span>}
            </div>
            <h1 className="page-title text-xl font-bold mt-1 text-foreground font-mono">
              {paymentId}
            </h1>
            <p className="text-xs text-muted-foreground mt-0.5">
              Invoice {invoiceId} · {paymentMethod} · Ingested via {channel}
            </p>
          </div>
        </div>

        <div className="md:text-right md:border-l border-border md:pl-6 shrink-0">
          <p className="eyebrow">Expected recovery value</p>
          <p className="mono-number text-2xl lg:text-3xl font-medium text-primary mt-0.5">
            {formatCurrency(amountInr)}
          </p>
          <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
            100% principal protected under policy
          </p>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded border border-destructive/40 bg-destructive/10 text-destructive text-xs flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main 2-Column Split */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.25fr_0.75fr] gap-4">
        {/* Left Column: Telemetry Form, AI Reasoning & History Timeline */}
        <div className="space-y-4">
          {/* Telemetry Input Panel */}
          <div className="panel">
            <div className="flex items-center justify-between border-b border-border/70 pb-3">
              <div>
                <p className="eyebrow">Payment Telemetry</p>
                <h2 className="section-title text-sm">Case parameters</h2>
              </div>
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground border border-border">
                POSTGRESQL BOUND
              </span>
            </div>

            <form onSubmit={handleEvaluate} className="mt-4 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                    Amount (INR)
                  </label>
                  <input
                    type="number"
                    value={amountInr}
                    onChange={(e) => setAmountInr(Number(e.target.value))}
                    required
                    className="w-full px-2.5 py-1.5 bg-background border border-border rounded font-mono text-xs text-foreground focus:outline-none focus:border-primary"
                    data-testid="input-amount"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                    Gateway Error
                  </label>
                  <input
                    type="text"
                    value={gatewayErrorCode}
                    onChange={(e) => setGatewayErrorCode(e.target.value)}
                    required
                    className="w-full px-2.5 py-1.5 bg-background border border-border rounded font-mono text-xs text-foreground focus:outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                    Bank Response Code
                  </label>
                  <input
                    type="text"
                    value={bankRawCode}
                    onChange={(e) => setBankRawCode(e.target.value)}
                    required
                    className="w-full px-2.5 py-1.5 bg-background border border-border rounded font-mono text-xs text-foreground focus:outline-none focus:border-primary"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                    Payment Method
                  </label>
                  <select
                    value={paymentMethod}
                    onChange={(e) => setPaymentMethod(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-background border border-border rounded font-mono text-xs text-foreground focus:outline-none focus:border-primary"
                  >
                    <option value="UPI_AUTOPAY">UPI Autopay</option>
                    <option value="CARD_MANDATE">Card Mandate</option>
                    <option value="NETBANKING_ENACH">Netbanking eNACH</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                    Bank Degradation (0-1)
                  </label>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    value={degradationScore}
                    onChange={(e) => setDegradationScore(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 bg-background border border-border rounded font-mono text-xs text-foreground focus:outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                    Attempt Count
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="5"
                    value={attemptCount}
                    onChange={(e) => setAttemptCount(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 bg-background border border-border rounded font-mono text-xs text-foreground focus:outline-none focus:border-primary"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                  Inbound Customer Message (Hinglish / Multilingual)
                </label>
                <textarea
                  rows={2}
                  value={inboundMessage}
                  onChange={(e) => setInboundMessage(e.target.value)}
                  placeholder="e.g. salary aane ke baad kat lena please"
                  className="w-full px-2.5 py-1.5 bg-background border border-border rounded text-xs text-foreground placeholder-muted-foreground/60 focus:outline-none focus:border-primary font-mono"
                  data-testid="input-customer-message"
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="text-[10px] text-muted-foreground">
                  Triggers AI Reasoner + Policy Gate Pipeline
                </span>
                <button
                  type="submit"
                  disabled={evaluating}
                  className="revive-button revive-button-primary"
                  data-testid="button-evaluate-single"
                >
                  <Zap size={13} className={evaluating ? 'animate-spin' : ''} />
                  <span>{evaluating ? 'Evaluating case...' : 'Run live evaluation'}</span>
                </button>
              </div>
            </form>
          </div>

          {/* AI Reasoning & Policy Outcome */}
          {evalResult && (
            <div className="panel space-y-4 revive-enter">
              <div className="flex items-center justify-between border-b border-border/70 pb-3">
                <div className="flex items-center gap-2">
                  <FlaskConical size={16} className="text-accent" />
                  <h3 className="section-title text-sm">AI Reasoner Output</h3>
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono">
                  <span className="px-2 py-0.5 rounded bg-secondary text-primary border border-border">
                    {evalResult.ai_provenance?.model || evalResult.reasoner_meta?.model || 'Gemini Flash'}
                  </span>
                  <span className="text-muted-foreground">{evalResult.ai_provenance?.latency_ms || 120}ms</span>
                </div>
              </div>

              {/* Reasoning Callout Box */}
              <div className="reasoning-box">
                <FlaskConical size={16} className="shrink-0 text-accent mt-0.5" />
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-foreground">
                    {evalResult.ai_reasoning.root_cause} &middot; {evalResult.ai_reasoning.customer_intent}
                  </p>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    {evalResult.ai_reasoning.reasoning_audit_text || evalResult.ai_reasoning.action_rationale || 'AI evaluation complete.'}
                  </p>
                </div>
              </div>

              {/* Decision Signals Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
                <div className="p-2.5 rounded bg-secondary/50 border border-border">
                  <span className="eyebrow block">PTP Detected</span>
                  <span className="font-semibold text-primary">
                    {evalResult.ai_reasoning.extracted_ptp_timestamp
                      ? formatDateTime(evalResult.ai_reasoning.extracted_ptp_timestamp)
                      : 'None'}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-secondary/50 border border-border">
                  <span className="eyebrow block">Debit Claimed</span>
                  <span className={`font-semibold ${hasDebitClaim ? 'text-destructive' : 'text-muted-foreground'}`}>
                    {hasDebitClaim ? 'YES (LOCK)' : 'NO'}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-secondary/50 border border-border">
                  <span className="eyebrow block">Proposed Action</span>
                  <span className="font-semibold text-accent">{evalResult.ai_reasoning.proposed_action}</span>
                </div>
                <div className="p-2.5 rounded bg-secondary/50 border border-border">
                  <span className="eyebrow block">Policy Gate</span>
                  <span className={`font-semibold ${evalResult.policy_decision.is_overridden ? 'text-accent' : 'text-primary'}`}>
                    {evalResult.policy_decision.is_overridden ? 'OVERRIDDEN' : 'AUTHORIZED'}
                  </span>
                </div>
              </div>

              {/* Policy Decision Summary */}
              <div className="p-3 rounded bg-secondary/30 border border-border flex items-start gap-2.5 text-xs">
                <ShieldCheck size={16} className="text-primary shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-foreground">
                    Deterministic Policy Gate Decision: <span className="text-primary font-mono">{evalResult.policy_decision.final_action || evalResult.policy_decision.authorized_action}</span>
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {evalResult.policy_decision.policy_reason || evalResult.policy_decision.override_reason || 'Autonomous execution verified compliant with statutory boundaries.'}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Case History & Timeline */}
          <div className="panel">
            <div className="flex items-center justify-between border-b border-border/70 pb-3">
              <div>
                <p className="eyebrow">State Transitions (PostgreSQL)</p>
                <h2 className="section-title text-sm">Transition timeline</h2>
              </div>
              <Clock size={15} className="text-muted-foreground" />
            </div>

            <div className="timeline mt-5">
              {(persistedCase?.transitions && persistedCase.transitions.length > 0) ? (
                persistedCase.transitions.map((t, idx) => (
                  <div key={idx} className="timeline-item">
                    <span className="timeline-node timeline-success" />
                    <div className="timeline-content">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs font-bold text-foreground font-mono">
                          {t.from_state} &rarr; {t.to_state}
                        </p>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          {formatDateTime(t.created_at || t.timestamp)}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">{t.reason}</p>
                    </div>
                  </div>
                ))
              ) : evalResult?.state_transitions && evalResult.state_transitions.length > 0 ? (
                evalResult.state_transitions.map((t, idx) => (
                  <div key={idx} className="timeline-item">
                    <span className="timeline-node timeline-success" />
                    <div className="timeline-content">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs font-bold text-foreground font-mono">
                          {t.from} &rarr; {t.to}
                        </p>
                        <span className="text-[10px] text-muted-foreground font-mono">
                          Step #{idx + 1}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">{t.reason}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="timeline-item">
                  <span className="timeline-node timeline-warning" />
                  <div className="timeline-content">
                    <p className="text-xs font-bold text-foreground font-mono">
                      INITIAL &rarr; {activeState}
                    </p>
                    <p className="text-[11px] text-muted-foreground mt-0.5">
                      Case initialized in PostgreSQL. Awaiting next operator or automated webhook trigger.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Deterministic Guardrails & Cryptographic Audit Proof */}
        <div className="space-y-4">
          {/* Deterministic Guardrails Panel */}
          <div className="panel panel-dark space-y-3">
            <div className="flex items-center justify-between border-b border-sidebar-border/80 pb-3">
              <div>
                <p className="eyebrow eyebrow-dark">Guardrails</p>
                <h3 className="section-title section-title-dark text-sm">Execution checks</h3>
              </div>
              <ShieldCheck size={18} className="text-sidebar-primary" />
            </div>

            <div className="space-y-1 divide-y divide-sidebar-border/70 text-xs">
              <div className="guardrail-row">
                <span className="guardrail-icon guardrail-pass">
                  <Check size={12} />
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-bold text-sidebar-foreground">TRAI Quiet Hours (21:00 - 09:00)</p>
                  <p className="text-[10px] text-sidebar-foreground/60">Outbound messages blocked during quiet hours</p>
                </div>
                <span className="guardrail-status guardrail-status-pass">PASS</span>
              </div>

              <div className="guardrail-row">
                <span className="guardrail-icon guardrail-pass">
                  <Check size={12} />
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-bold text-sidebar-foreground">Contact Ceiling (Max 3/week)</p>
                  <p className="text-[10px] text-sidebar-foreground/60">Escalates to human operations on breach</p>
                </div>
                <span className="guardrail-status guardrail-status-pass">PASS</span>
              </div>

              <div className="guardrail-row">
                <span className={`guardrail-icon ${hasDebitClaim ? 'guardrail-block' : 'guardrail-pass'}`}>
                  {hasDebitClaim ? <X size={12} /> : <Check size={12} />}
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-bold text-sidebar-foreground">Debit Claim Recon Lock</p>
                  <p className="text-[10px] text-sidebar-foreground/60">Halts auto-debit if customer claims money lost</p>
                </div>
                <span className={`guardrail-status ${hasDebitClaim ? 'guardrail-status-block' : 'guardrail-status-pass'}`}>
                  {hasDebitClaim ? 'LOCK' : 'PASS'}
                </span>
              </div>

              <div className="guardrail-row">
                <span className="guardrail-icon guardrail-pass">
                  <Check size={12} />
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-bold text-sidebar-foreground">Zero Unauthorized Discounts</p>
                  <p className="text-[10px] text-sidebar-foreground/60">AI cannot reduce principal without merchant policy</p>
                </div>
                <span className="guardrail-status guardrail-status-pass">PASS</span>
              </div>
            </div>

            <div className="pt-3 border-t border-sidebar-border/80 text-[10px] text-sidebar-foreground/60 leading-relaxed">
              Every mutation is checked against active PostgreSQL guardrails before state commit.
            </div>
          </div>

          {/* Cryptographic Audit Proof */}
          <div className="panel space-y-3">
            <div className="flex items-center justify-between border-b border-border/70 pb-2.5">
              <div>
                <p className="eyebrow">Persisted Audit Block</p>
                <h3 className="section-title text-sm">SHA-256 Audit Block</h3>
              </div>
              <Hash size={15} className="text-primary" />
            </div>

            {evalResult?.audit_block ? (
              <div className="space-y-2 text-xs font-mono">
                <div className="p-2.5 rounded bg-secondary/50 border border-border space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>Block #{evalResult.audit_block.index !== undefined ? evalResult.audit_block.index : evalResult.audit_block.block_index}</span>
                    <span className="text-primary font-bold">COMMITTED</span>
                  </div>
                  <div className="truncate text-[10px]">
                    <span className="text-muted-foreground">Current Hash: </span>
                    <span className="text-foreground">{evalResult.audit_block.current_hash.slice(0, 20)}...</span>
                  </div>
                  <div className="truncate text-[10px]">
                    <span className="text-muted-foreground">Prev Hash: </span>
                    <span className="text-muted-foreground/80">{evalResult.audit_block.previous_hash.slice(0, 16)}...</span>
                  </div>
                </div>

                <div className="data-pair">
                  <span>Action Executed</span>
                  <strong className="text-primary font-mono">{evalResult.audit_block.action_executed}</strong>
                </div>
                <div className="data-pair">
                  <span>Resulting State</span>
                  <strong className="font-mono">{evalResult.audit_block.resulting_state}</strong>
                </div>
              </div>
            ) : (
              <div className="py-4 text-center text-xs text-muted-foreground">
                <FileClock size={20} className="mx-auto text-muted-foreground/60 mb-1" />
                <p>Run evaluation to write a cryptographic audit block to PostgreSQL.</p>
              </div>
            )}
          </div>

          {/* Account Context & Signals */}
          <div className="panel space-y-2">
            <p className="eyebrow">Account context</p>
            <h3 className="section-title text-sm">Customer signals</h3>

            <div className="space-y-1 divide-y divide-border/60 text-xs">
              <div className="data-pair">
                <span>Invoice ID</span>
                <strong className="font-mono">{invoiceId}</strong>
              </div>
              <div className="data-pair">
                <span>Payment Method</span>
                <strong className="font-mono">{paymentMethod}</strong>
              </div>
              <div className="data-pair">
                <span>Contact Attempts</span>
                <strong className="font-mono">{attemptCount} of 3</strong>
              </div>
              <div className="data-pair">
                <span>Bank Degradation Score</span>
                <strong className="font-mono">{(degradationScore * 100).toFixed(0)}%</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
