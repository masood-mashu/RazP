import React, { useEffect, useState } from 'react';
import {
  SlidersHorizontal,
  Lock,
  Save,
  RefreshCw,
  AlertTriangle,
  Clock,
  CheckCircle2
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
    <div className="p-5 lg:p-7 space-y-5 overflow-y-auto h-full revive-scroll">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 pb-2 border-b border-border/60">
        <div>
          <p className="eyebrow">Deterministic Policy & Compliance Gate</p>
          <h1 className="page-title">Recovery policy</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Tune operating boundaries and statutory compliance rules enforced deterministically on every recovery mutation.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={fetchPolicy}
            disabled={loading}
            className="revive-button revive-button-outline"
            data-testid="button-refresh-policy"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh policy</span>
          </button>
        </div>
      </div>

      {successMessage && (
        <div className="p-3.5 rounded border border-primary/40 bg-primary/10 text-primary text-xs flex items-center gap-2">
          <CheckCircle2 size={15} className="shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {error && (
        <div className="p-3.5 rounded border border-destructive/40 bg-destructive/10 text-destructive text-xs flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main 2-Column Split */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr] gap-4">
        {/* Left Form: Configurable Merchant Policy */}
        <div className="panel space-y-4">
          <div className="flex items-center justify-between border-b border-border/70 pb-3">
            <div>
              <p className="eyebrow">Merchant Configurable Parameters</p>
              <h2 className="section-title text-sm">Policy parameters</h2>
            </div>
            <SlidersHorizontal size={15} className="text-muted-foreground" />
          </div>

          <form onSubmit={handleSavePolicy} className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                  Max Contact Attempts
                </label>
                <div className="flex items-center gap-2 bg-background border border-border rounded px-2.5 py-1.5 focus-within:border-primary">
                  <input
                    type="number"
                    min="1"
                    max="5"
                    value={maxAttempts}
                    onChange={(e) => setMaxAttempts(Number(e.target.value))}
                    required
                    className="w-full bg-transparent font-mono text-xs text-foreground focus:outline-none"
                    data-testid="input-max-attempts"
                  />
                  <span className="text-[10px] text-muted-foreground font-mono">attempts</span>
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                  Max PTP Horizon
                </label>
                <div className="flex items-center gap-2 bg-background border border-border rounded px-2.5 py-1.5 focus-within:border-primary">
                  <input
                    type="number"
                    min="1"
                    max="30"
                    value={maxPtpDays}
                    onChange={(e) => setMaxPtpDays(Number(e.target.value))}
                    required
                    className="w-full bg-transparent font-mono text-xs text-foreground focus:outline-none"
                    data-testid="input-max-ptp-days"
                  />
                  <span className="text-[10px] text-muted-foreground font-mono">days</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                  TRAI Quiet Hours Start (21:00 - 09:00)
                </label>
                <div className="flex items-center gap-2 bg-background border border-border rounded px-2.5 py-1.5 focus-within:border-primary">
                  <Clock size={13} className="text-muted-foreground shrink-0" />
                  <input
                    type="time"
                    value={quietHoursStart}
                    onChange={(e) => setQuietHoursStart(e.target.value)}
                    required
                    className="w-full bg-transparent font-mono text-xs text-foreground focus:outline-none"
                    data-testid="input-quiet-hours-start"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                  TRAI Quiet Hours End
                </label>
                <div className="flex items-center gap-2 bg-background border border-border rounded px-2.5 py-1.5 focus-within:border-primary">
                  <Clock size={13} className="text-muted-foreground shrink-0" />
                  <input
                    type="time"
                    value={quietHoursEnd}
                    onChange={(e) => setQuietHoursEnd(e.target.value)}
                    required
                    className="w-full bg-transparent font-mono text-xs text-foreground focus:outline-none"
                    data-testid="input-quiet-hours-end"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                  Bank Circuit Breaker
                </label>
                <div className="flex items-center gap-2 bg-background border border-border rounded px-2.5 py-1.5 focus-within:border-primary">
                  <input
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="0.9"
                    value={circuitBreakerThreshold}
                    onChange={(e) => setCircuitBreakerThreshold(Number(e.target.value))}
                    required
                    className="w-full bg-transparent font-mono text-xs text-foreground focus:outline-none"
                  />
                  <span className="text-[10px] text-muted-foreground font-mono">failure rate</span>
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-muted-foreground uppercase mb-1">
                  Settlement Discounts
                </label>
                <div className="flex items-center justify-between bg-background border border-border rounded px-2.5 py-1.5">
                  <span className="text-[11px] text-muted-foreground">Allow AI discounts</span>
                  <input
                    type="checkbox"
                    checked={allowDiscounts}
                    onChange={(e) => setAllowDiscounts(e.target.checked)}
                    className="w-4 h-4 rounded text-primary focus:ring-primary border-border bg-secondary"
                  />
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-border/70 flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground font-mono">
                Persists to table: merchant_policies
              </span>
              <button
                type="submit"
                disabled={saving}
                className="revive-button revive-button-primary"
                data-testid="button-save-policy"
              >
                <Save size={13} className={saving ? 'animate-spin' : ''} />
                <span>{saving ? 'Saving policy...' : 'Save as active policy'}</span>
              </button>
            </div>
          </form>
        </div>

        {/* Right Panel: Live Guardrail State & Statutory Regulations */}
        <div className="space-y-4">
          {/* Active Policy Summary */}
          <div className="panel panel-quiet space-y-3">
            <div className="flex items-center justify-between border-b border-border/70 pb-2.5">
              <div>
                <p className="eyebrow">Active policy</p>
                <h3 className="section-title text-sm">Live guardrail set</h3>
              </div>
              <span className="policy-id">LIVE</span>
            </div>

            <div className="space-y-1 divide-y divide-border/60 text-xs">
              <div className="data-pair">
                <span>Merchant ID</span>
                <strong className="font-mono">rzp_merchant_prod</strong>
              </div>
              <div className="data-pair">
                <span>Max Retries</span>
                <strong className="font-mono">{maxAttempts} attempts</strong>
              </div>
              <div className="data-pair">
                <span>Quiet Hours Window</span>
                <strong className="font-mono">{quietHoursStart} &ndash; {quietHoursEnd} IST</strong>
              </div>
              <div className="data-pair">
                <span>PTP Extension Limit</span>
                <strong className="font-mono">{maxPtpDays} days</strong>
              </div>
              <div className="data-pair">
                <span>Discount Authority</span>
                <strong className={allowDiscounts ? 'text-accent' : 'text-primary'}>
                  {allowDiscounts ? 'ENABLED' : 'DISABLED (0% DISCOUNT)'}
                </strong>
              </div>
            </div>
          </div>

          {/* Statutory Regulatory Boundaries */}
          <div className="panel panel-dark space-y-3">
            <div className="flex items-center justify-between border-b border-sidebar-border/80 pb-2.5">
              <div>
                <p className="eyebrow eyebrow-dark">Compliance rules</p>
                <h3 className="section-title section-title-dark text-sm">TRAI Quiet Hours & Statutory boundaries</h3>
              </div>
              <Lock size={15} className="text-sidebar-primary" />
            </div>

            <div className="space-y-2 text-[11px] text-sidebar-foreground/80">
              <div className="p-2 rounded bg-sidebar-accent/50 border border-sidebar-border space-y-0.5">
                <span className="font-bold text-sidebar-foreground">TRAI Telecom Regulations</span>
                <p className="text-sidebar-foreground/60 text-[10px]">
                  Commercial communications between 21:00 and 09:00 IST are strictly prohibited. The policy gate strips outbound messaging during quiet hours.
                </p>
              </div>

              <div className="p-2 rounded bg-sidebar-accent/50 border border-sidebar-border space-y-0.5">
                <span className="font-bold text-sidebar-foreground">RBI Fair Practice Code</span>
                <p className="text-sidebar-foreground/60 text-[10px]">
                  Customer harassment prevention caps contact frequency. Cases exceeding contact ceiling escalate to human ops.
                </p>
              </div>

              <div className="p-2 rounded bg-sidebar-accent/50 border border-sidebar-border space-y-0.5">
                <span className="font-bold text-sidebar-foreground">Zero-Discounts Financial Invariant</span>
                <p className="text-sidebar-foreground/60 text-[10px]">
                  AI reasoners have zero authority to alter payable principal or waive fees.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
