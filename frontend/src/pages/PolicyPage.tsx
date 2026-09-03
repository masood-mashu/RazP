import React, { useEffect, useState } from 'react';
import {
  Lock,
  Save,
  RefreshCw,
  AlertTriangle,
  Clock,
  CheckCircle2,
  ShieldCheck
} from 'lucide-react';
import { api } from '../api/client';

export const PolicyPage: React.FC = () => {
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Form fields
  const [maxAttempts, setMaxAttempts] = useState<number>(3);
  const [maxPtpDays, setMaxPtpDays] = useState<number>(14);
  const [allowDiscounts, setAllowDiscounts] = useState<boolean>(false);
  const [circuitBreakerThreshold, setCircuitBreakerThreshold] = useState<number>(0.65);
  const [quietHoursStart, setQuietHoursStart] = useState<string>('21:00');
  const [quietHoursEnd, setQuietHoursEnd] = useState<string>('09:00');

  const fetchPolicy = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getPolicy();
      setMaxAttempts(res.max_contact_attempts);
      setMaxPtpDays(res.max_ptp_extension_days);
      setAllowDiscounts(res.allow_discounts);
      setCircuitBreakerThreshold(res.circuit_breaker_bank_failure_rate_threshold);
      setQuietHoursStart(res.quiet_hours_start?.slice(0, 5) || '21:00');
      setQuietHoursEnd(res.quiet_hours_end?.slice(0, 5) || '09:00');
    } catch (err: any) {
      setError(err.message || 'Failed to fetch policy from PostgreSQL.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPolicy();
  }, []);

  const handleSavePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setError(null);
      setSuccessMessage(null);

      const res = await api.updatePolicy({
        merchant_id: 'rzp_merchant_prod',
        max_contact_attempts: Number(maxAttempts),
        max_ptp_extension_days: Number(maxPtpDays),
        allow_discounts: allowDiscounts,
        circuit_breaker_bank_failure_rate_threshold: Number(circuitBreakerThreshold),
        quiet_hours_start: quietHoursStart,
        quiet_hours_end: quietHoursEnd,
      });

      setSuccessMessage(`Policy updated & activated in PostgreSQL (Policy ID: ${res.policy_id || 'active'})`);
      await fetchPolicy();
    } catch (err: any) {
      setError(err.message || 'Failed to update merchant policy in PostgreSQL.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-5 lg:p-7 space-y-6 overflow-y-auto h-full revive-scroll bg-[#070B14]">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-2 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <span className="eyebrow text-[#0C83FF]">Deterministic Policy &amp; Compliance Gate</span>
            <span className="text-muted-foreground text-xs">·</span>
            <span className="text-[11px] text-muted-foreground font-mono">TRAI Compliance & Safety</span>
          </div>
          <h1 className="page-title text-2xl font-bold text-white tracking-tight">Recovery Policy Engine</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Configure merchant recovery thresholds and inspect statutory constraints enforced deterministically on every state transition.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={fetchPolicy}
            disabled={loading}
            className="revive-button revive-button-outline"
            data-testid="button-refresh-policy"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {successMessage && (
        <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2.5">
          <CheckCircle2 size={16} />
          <span>{successMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2.5">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Statutory Invariants (Non-negotiable regulations) (5 cols) */}
        <div className="lg:col-span-5 space-y-5">
          <div className="panel space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <Lock size={15} className="text-[#10B981]" />
                <h2 className="section-title text-sm font-semibold text-white">
                  Statutory Invariants (Hardcoded Law)
                </h2>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-[#10B981] font-semibold border border-emerald-500/25">
                IMMUTABLE
              </span>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">
              These constraints are enforced in the deterministic spine and cannot be overridden by merchant policy or LLM proposals:
            </p>

            <div className="space-y-3 pt-1">
              <div className="p-3 rounded-lg bg-[#080D1A] border border-border space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold text-white">
                  <span className="flex items-center gap-2">
                    <Clock size={13} className="text-[#F59E0B]" />
                    <span>TRAI Quiet Hours (21:00–09:00 IST)</span>
                  </span>
                  <span className="text-[10px] font-mono text-[#10B981]">ENFORCED</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Indian Telecom Regulatory Authority mandates no commercial communication between 9 PM and 9 AM. Timezone conversion normalizes UTC into IST.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-[#080D1A] border border-border space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold text-white">
                  <span className="flex items-center gap-2">
                    <ShieldCheck size={13} className="text-[#0C83FF]" />
                    <span>Zero AI Financial Authority</span>
                  </span>
                  <span className="text-[10px] font-mono text-[#10B981]">ENFORCED</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  AI models cannot grant unauthorized discounts, alter invoice amounts, or execute balance refunds without deterministic merchant approval.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-[#080D1A] border border-border space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold text-white">
                  <span className="flex items-center gap-2">
                    <Lock size={13} className="text-[#8B5CF6]" />
                    <span>Debit Claim Reconciliation Lock</span>
                  </span>
                  <span className="text-[10px] font-mono text-[#10B981]">ENFORCED</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  If a customer reports an account debit, all retries freeze in <code>PAUSE_RECON_VERIFY</code> until authoritative bank settlement reconciliation.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Configurable Policy Form (7 cols) */}
        <div className="lg:col-span-7 space-y-5">
          <form onSubmit={handleSavePolicy} className="panel space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div>
                <h2 className="section-title text-sm font-semibold text-white">
                  Merchant Configurable Parameters
                </h2>
                <p className="text-xs text-muted-foreground">
                  Active policy record persisted in PostgreSQL and checked on every recovery step.
                </p>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/15 text-[#0C83FF] font-semibold border border-blue-500/25">
                rzp_merchant_prod
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="space-y-1.5">
                <label className="text-muted-foreground font-mono text-[11px] block">
                  Quiet Hours Start (IST)
                </label>
                <input
                  type="text"
                  value={quietHoursStart}
                  onChange={(e) => setQuietHoursStart(e.target.value)}
                  placeholder="21:00"
                  className="w-full px-3 py-2 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-quiet-hours-start"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-muted-foreground font-mono text-[11px] block">
                  Quiet Hours End (IST)
                </label>
                <input
                  type="text"
                  value={quietHoursEnd}
                  onChange={(e) => setQuietHoursEnd(e.target.value)}
                  placeholder="09:00"
                  className="w-full px-3 py-2 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-quiet-hours-end"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-muted-foreground font-mono text-[11px] block">
                  Max Contact Attempts (Ceiling &le; 3)
                </label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={maxAttempts}
                  onChange={(e) => setMaxAttempts(parseInt(e.target.value) || 3)}
                  className="w-full px-3 py-2 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-max-attempts"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-muted-foreground font-mono text-[11px] block">
                  Max PTP Horizon (Days &le; 14)
                </label>
                <input
                  type="number"
                  min="1"
                  max="30"
                  value={maxPtpDays}
                  onChange={(e) => setMaxPtpDays(parseInt(e.target.value) || 14)}
                  className="w-full px-3 py-2 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-max-ptp-days"
                />
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <label className="text-muted-foreground font-mono text-[11px] block">
                  Bank Switch Circuit Breaker Threshold (Degradation Score: 0.0 &ndash; 1.0)
                </label>
                <input
                  type="number"
                  step="0.05"
                  min="0.1"
                  max="0.95"
                  value={circuitBreakerThreshold}
                  onChange={(e) => setCircuitBreakerThreshold(parseFloat(e.target.value) || 0.65)}
                  className="w-full px-3 py-2 rounded-md bg-[#080D1A] border border-border text-white font-mono text-xs focus:border-[#0C83FF] outline-none"
                  data-testid="input-circuit-breaker-threshold"
                />
                <p className="text-[10px] text-muted-foreground font-mono">
                  If bank switch failure rate exceeds this score, automatic bank retries are rejected to prevent customer friction.
                </p>
              </div>

              <div className="space-y-1.5 sm:col-span-2 pt-2 border-t border-border">
                <label className="flex items-center gap-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={allowDiscounts}
                    onChange={(e) => setAllowDiscounts(e.target.checked)}
                    className="rounded bg-[#080D1A] border-border text-[#0C83FF] focus:ring-0 w-4 h-4"
                    data-testid="checkbox-allow-discounts"
                  />
                  <span className="text-xs text-white font-medium">
                    Allow Merchant Discount Authorization (Strict 0% by default)
                  </span>
                </label>
              </div>
            </div>

            <div className="pt-3 border-t border-border flex items-center justify-end">
              <button
                type="submit"
                disabled={saving}
                className="revive-button revive-button-primary"
                data-testid="button-save-policy"
              >
                <Save size={13} className={saving ? 'animate-spin' : ''} />
                <span>{saving ? 'Saving to PostgreSQL...' : 'Save & Persist Policy'}</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
