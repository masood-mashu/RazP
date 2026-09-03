import React, { useEffect, useState } from 'react';
import {
  Zap,
  ShieldCheck,
  AlertTriangle,
  Hash,
  Sparkles,
  ExternalLink,
  RotateCcw
} from 'lucide-react';
import { api } from '../api/client';
import type { PaymentCase, SingleEvalResponse } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

interface CaseWorkspaceProps {
  initialPaymentId?: string | null;
  onClearCase?: () => void;
  onNavigateToLedger?: () => void;
}

export const CaseWorkspace: React.FC<CaseWorkspaceProps> = ({
  initialPaymentId,
  onClearCase,
  onNavigateToLedger
}) => {
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
  const [caseTrace, setCaseTrace] = useState<any | null>(null);
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
      const [caseData, traceData] = await Promise.all([
        api.getCaseDetail(pId).catch(() => null),
        api.getCaseTrace(pId).catch(() => null)
      ]);

      if (caseData) {
        setPersistedCase(caseData);
        if (caseData.invoice_id) setInvoiceId(caseData.invoice_id);
        if (caseData.amount_inr) setAmountInr(caseData.amount_inr);
        if (caseData.attempt_count) setAttemptCount(caseData.attempt_count);
      }

      if (traceData) {
        setCaseTrace(traceData);
      }
    } catch (err: any) {
      console.warn('Case loading error:', err);
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

  const formatCurrency = (amt: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amt);

  return (
    <div className="p-5 lg:p-7 space-y-6 overflow-y-auto h-full revive-scroll bg-[#070B14]">
      {/* Page Header & Scenario Presets */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-2 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <span className="eyebrow text-[#0C83FF]">Decision Science Engine</span>
            <span className="text-muted-foreground text-xs">·</span>
            <span className="text-[11px] text-muted-foreground font-mono">Telemetry & Reasoning</span>
          </div>
          <h1 className="page-title text-2xl font-bold text-white tracking-tight flex items-center gap-3">
            <span>Case Workspace &amp; Decision Engine</span>
            <span className="mono-number text-lg text-[#0C83FF]">
              ({formatCurrency(amountInr)})
            </span>
            {persistedCase && (
              <StatusBadge state={persistedCase.current_state} size="md" />
            )}
          </h1>
        </div>

        {/* Quick Presets & Clear */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          {onClearCase && persistedCase && (
            <button
              type="button"
              onClick={onClearCase}
              className="px-2.5 py-1 rounded-md text-xs font-semibold bg-secondary hover:bg-secondary/80 border border-border text-muted-foreground hover:text-white flex items-center gap-1"
              title="Start with fresh case"
            >
              <RotateCcw size={11} />
              <span>Reset</span>
            </button>
          )}
          <span className="text-xs font-mono text-muted-foreground whitespace-nowrap">Load Preset:</span>
          <button
            type="button"
            onClick={() => loadPreset('hinglish_ptp')}
            className="px-3 py-1 rounded-md text-xs font-semibold bg-[#080D1A] hover:bg-secondary border border-border text-white whitespace-nowrap"
            data-testid="preset-hinglish-ptp"
          >
            Hinglish PTP
          </button>
          <button
            type="button"
            onClick={() => loadPreset('debit_claim_recon')}
            className="px-3 py-1 rounded-md text-xs font-semibold bg-[#080D1A] hover:bg-secondary border border-border text-white whitespace-nowrap"
            data-testid="preset-debit-claim-hold"
          >
            Debit Claim Hold
          </button>
          <button
            type="button"
            onClick={() => loadPreset('mandate_revoked')}
            className="px-3 py-1 rounded-md text-xs font-semibold bg-[#080D1A] hover:bg-secondary border border-border text-white whitespace-nowrap"
            data-testid="preset-mandate-revoked"
          >
            Mandate Revoked
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-3">
          <AlertTriangle size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Form Parameters (5 cols) */}
        <div className="lg:col-span-5 space-y-5">
          <form onSubmit={handleEvaluate} className="panel space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <h2 className="section-title text-sm font-semibold text-white">Payment Telemetry</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/15 text-[#0C83FF] border border-blue-500/20 font-semibold">
                POSTGRESQL BOUND
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="space-y-1">
                <label className="text-muted-foreground font-mono text-[11px]">Payment ID</label>
                <input
                  type="text"
                  value={paymentId}
                  onChange={(e) => setPaymentId(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-payment-id"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground font-mono text-[11px]">Invoice ID</label>
                <input
                  type="text"
                  value={invoiceId}
                  onChange={(e) => setInvoiceId(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-invoice-id"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground font-mono text-[11px]">Amount (INR)</label>
                <input
                  type="number"
                  step="0.01"
                  value={amountInr}
                  onChange={(e) => setAmountInr(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-1.5 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-amount-inr"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground font-mono text-[11px]">Payment Method</label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="select-payment-method"
                >
                  <option value="UPI_AUTOPAY">UPI AutoPay</option>
                  <option value="CARD_MANDATE">Card Mandate</option>
                  <option value="NETBANKING">NetBanking</option>
                  <option value="UPI_COLLECT">UPI Collect</option>
                  <option value="CARD_ONE_TIME">Card One-Time</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground font-mono text-[11px]">Gateway Error Code</label>
                <input
                  type="text"
                  value={gatewayErrorCode}
                  onChange={(e) => setGatewayErrorCode(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-gateway-error"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground font-mono text-[11px]">Bank Raw Code</label>
                <input
                  type="text"
                  value={bankRawCode}
                  onChange={(e) => setBankRawCode(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-bank-raw-code"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground font-mono text-[11px]">Bank Degradation (0-1)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  value={degradationScore}
                  onChange={(e) => setDegradationScore(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-1.5 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-degradation-score"
                />
              </div>

              <div className="space-y-1">
                <label className="text-muted-foreground font-mono text-[11px]">Attempt Count</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={attemptCount}
                  onChange={(e) => setAttemptCount(parseInt(e.target.value) || 1)}
                  className="w-full px-3 py-1.5 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-attempt-count"
                />
              </div>
            </div>

            {/* Customer Message */}
            <div className="space-y-1.5 pt-2 border-t border-border">
              <div className="flex items-center justify-between">
                <label className="text-muted-foreground font-mono text-[11px]">
                  Inbound Customer Message (Hinglish / Multilingual)
                </label>
                <span className="text-[10px] font-mono text-[#8B5CF6]">Gemini Semantic Zone</span>
              </div>
              <textarea
                rows={3}
                value={inboundMessage}
                onChange={(e) => setInboundMessage(e.target.value)}
                placeholder="Paste customer WhatsApp or SMS message..."
                className="w-full px-3 py-2 rounded-md bg-[#080D1A] border border-border text-white text-xs focus:border-[#0C83FF] outline-none font-mono resize-none"
                data-testid="input-inbound-message"
              />
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={evaluating}
                className="revive-button revive-button-primary w-full h-9"
                data-testid="button-run-evaluation"
              >
                <Zap size={14} className={evaluating ? 'animate-spin' : 'fill-white'} />
                <span>{evaluating ? 'Evaluating with Gemini & Policy Gate...' : 'Run Live Evaluation'}</span>
              </button>
            </div>
          </form>

          {/* Quick Context Card */}
          <div className="panel p-4 space-y-2 text-xs">
            <h3 className="font-semibold text-white">Execution Boundary</h3>
            <p className="text-muted-foreground text-[11px] leading-relaxed">
              Gemini Flash semantically parses multilingual customer intent and telemetry, then outputs a typed action proposal. The deterministic policy gate validates financial invariants, quiet hours, and rate limits before PostgreSQL state commit.
            </p>
          </div>
        </div>

        {/* Right Column: Reasoning & Policy Diagnostics (7 cols) */}
        <div className="lg:col-span-7 space-y-5">
          {!evalResult ? (
            <div className="panel p-12 text-center text-muted-foreground space-y-3">
              <div className="w-12 h-12 rounded-full bg-[#0C83FF]/15 border border-[#0C83FF]/30 flex items-center justify-center text-[#0C83FF] mx-auto">
                <Zap size={22} />
              </div>
              <h3 className="text-sm font-semibold text-white">Awaiting Evaluation</h3>
              <p className="text-xs max-w-sm mx-auto">
                Select a preset scenario on the top right or customize telemetry parameters and click &ldquo;Run Live Evaluation&rdquo;.
              </p>
            </div>
          ) : (
            <div className="space-y-5 revive-enter">
              {/* Card 1: Gemini AI Semantic Reasoner Card (Violet) */}
              <div className="panel border-l-4 border-l-[#8B5CF6] space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-border">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-md bg-[#8B5CF6]/15 text-[#8B5CF6] flex items-center justify-center">
                      <Sparkles size={14} />
                    </div>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                      AI Reasoner Output
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#8B5CF6]/15 text-[#8B5CF6] font-semibold border border-[#8B5CF6]/25">
                    {evalResult.ai_provenance?.model || 'gemini-flash-lite-latest'}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs font-mono pt-1">
                  <div className="p-2 rounded bg-[#080D1A] border border-border">
                    <span className="text-muted-foreground text-[10px] block">Root Cause</span>
                    <strong className="text-white text-xs truncate block mt-0.5">
                      {evalResult.ai_reasoning?.root_cause || evalResult.policy_decision?.ai_root_cause || 'TRANSIENT_NETWORK_GLITCH'}
                    </strong>
                  </div>
                  <div className="p-2 rounded bg-[#080D1A] border border-border">
                    <span className="text-muted-foreground text-[10px] block">Customer Intent</span>
                    <strong className="text-white text-xs truncate block mt-0.5">
                      {evalResult.ai_reasoning?.customer_intent || 'UNKNOWN'}
                    </strong>
                  </div>
                  <div className="p-2 rounded bg-[#080D1A] border border-border">
                    <span className="text-muted-foreground text-[10px] block">Extracted PTP</span>
                    <strong className="text-[#F59E0B] text-xs truncate block mt-0.5">
                      {evalResult.ai_reasoning?.extracted_ptp_timestamp
                        ? evalResult.ai_reasoning.extracted_ptp_timestamp.slice(0, 10)
                        : 'None'}
                    </strong>
                  </div>
                  <div className="p-2 rounded bg-[#080D1A] border border-border">
                    <span className="text-muted-foreground text-[10px] block">Confidence</span>
                    <strong className="text-[#10B981] text-xs truncate block mt-0.5">
                      {evalResult.ai_reasoning?.confidence ? `${(evalResult.ai_reasoning.confidence * 100).toFixed(0)}%` : '95%'}
                    </strong>
                  </div>
                </div>

                {/* AI Rationale Text */}
                <div className="reasoning-box text-xs font-mono text-muted-foreground leading-relaxed">
                  <p className="text-white font-sans text-xs">
                    {evalResult.ai_reasoning?.reasoning_audit_text || evalResult.ai_reasoning?.action_rationale || 'Customer provided commitment. Guardrailed action proposed.'}
                  </p>
                </div>
              </div>

              {/* Card 2: Deterministic Policy Gate Card */}
              <div className="panel border-l-4 border-l-[#10B981] space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-border">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-md bg-[#10B981]/15 text-[#10B981] flex items-center justify-center">
                      <ShieldCheck size={14} />
                    </div>
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                      Deterministic Policy Gate Decision
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#10B981]/15 text-[#10B981] font-semibold border border-[#10B981]/25">
                    {evalResult.policy_decision?.is_overridden ? 'GUARDRAIL OVERRIDE' : 'APPROVED SAFE'}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="p-2.5 rounded bg-[#080D1A] border border-border">
                    <span className="text-muted-foreground text-[10px] font-mono block">Proposed Action (AI)</span>
                    <strong className="text-muted-foreground font-mono text-xs block mt-0.5">
                      {evalResult.policy_decision?.original_action || 'N/A'}
                    </strong>
                  </div>
                  <div className="p-2.5 rounded bg-[#080D1A] border border-border">
                    <span className="text-muted-foreground text-[10px] font-mono block">Executed Action (Spine)</span>
                    <strong className="text-[#10B981] font-mono text-xs block mt-0.5">
                      {evalResult.policy_decision?.final_action || evalResult.execution_result?.action_executed || 'N/A'}
                    </strong>
                  </div>
                </div>

                <p className="text-xs text-muted-foreground font-mono pt-1">
                  Policy Reason: <strong className="text-white font-sans">{evalResult.policy_decision?.policy_reason || 'Compliant state transition'}</strong>
                </p>
              </div>

              {/* Card 3: State Transitions & Audit Block */}
              <div className="panel space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-border">
                  <h3 className="section-title text-sm font-semibold text-white">State Lifecycle & Audit Block</h3>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-muted-foreground">Final State:</span>
                    <StatusBadge state={evalResult.final_state || 'AWAITING_CUSTOMER_ACTION'} size="sm" />
                  </div>
                </div>

                {/* State timeline */}
                <div className="space-y-2">
                  <span className="text-[10px] font-mono uppercase text-muted-foreground font-semibold">
                    State Transitions (PostgreSQL)
                  </span>
                  <div className="timeline pt-1">
                    {(evalResult.state_transitions || []).map((tr: any, idx: number) => (
                      <div key={idx} className="timeline-item">
                        <div className="timeline-node timeline-success" />
                        <div className="timeline-content text-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-muted-foreground">{tr.from}</span>
                            <span className="text-muted-foreground">&rarr;</span>
                            <strong className="font-mono text-white">{tr.to}</strong>
                          </div>
                          <p className="text-[11px] text-muted-foreground mt-0.5">{tr.reason}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Audit Block Card */}
                {evalResult.audit_block && (
                  <div className="p-3 rounded-lg bg-[#080D1A] border border-border space-y-2 text-xs font-mono">
                    <div className="flex items-center justify-between">
                      <span className="text-[#0C83FF] font-semibold flex items-center gap-1.5">
                        <Hash size={13} />
                        <span>Persisted Audit Block</span>
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">
                          Block #{evalResult.audit_block.index !== undefined ? evalResult.audit_block.index : (evalResult.audit_block as any).block_index}
                          {caseTrace?.audit_blocks ? ` (${caseTrace.audit_blocks.length} on record)` : ''}
                        </span>
                        {onNavigateToLedger && (
                          <button
                            type="button"
                            onClick={onNavigateToLedger}
                            className="text-[10px] text-[#0C83FF] hover:underline flex items-center gap-0.5"
                          >
                            <span>Ledger</span>
                            <ExternalLink size={10} />
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="space-y-1 text-[11px]">
                      <div className="truncate text-muted-foreground">
                        Current Hash: <span className="text-white">{evalResult.audit_block.current_hash}</span>
                      </div>
                      <div className="truncate text-muted-foreground">
                        Previous Hash: <span className="text-white">{evalResult.audit_block.previous_hash}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
