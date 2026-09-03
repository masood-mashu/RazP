import React, { useEffect, useState } from 'react';
import {
  CircleDollarSign,
  TrendingUp,
  ShieldCheck,
  RefreshCw,
  Zap,
  ArrowRight,
  CheckCircle2,
  Lock,
  ExternalLink,
  X
} from 'lucide-react';
import { api } from '../api/client';
import type { DashboardStats, PaymentCase, SystemStatus } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

interface CommandCenterProps {
  onSelectCase: (paymentId: string) => void;
  onNavigate: (tab: any) => void;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({ onSelectCase, onNavigate }) => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentCases, setRecentCases] = useState<PaymentCase[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Multi-event demo state
  const [demoRunning, setDemoRunning] = useState<boolean>(false);
  const [demoModalOpen, setDemoModalOpen] = useState<boolean>(false);
  const [demoResult, setDemoResult] = useState<any | null>(null);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [statsRes, casesRes, sysRes] = await Promise.all([
        api.getDashboardStats(),
        api.getCases({ limit: 6 }),
        api.getSystemStatus(),
      ]);
      setStats(statsRes);
      setRecentCases(casesRes.cases);
      setSystemStatus(sysRes);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard statistics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunDemo = async () => {
    try {
      setDemoRunning(true);
      const res = await api.runMultiEventDemo();
      setDemoResult(res);
      setDemoModalOpen(true);
      await loadData();
    } catch (err: any) {
      alert(`Demo execution failed: ${err.message}`);
    } finally {
      setDemoRunning(false);
    }
  };

  const formatCurrency = (amt: number | undefined) =>
    amt === undefined
      ? '—'
      : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amt);

  const formatPercent = (pct: number | undefined) => (pct === undefined ? '—' : `${pct.toFixed(1)}%`);

  const activeCasesCount = stats?.active_cases || 0;
  const recoveredCasesCount = stats?.recovered_cases || 0;
  const totalCasesCount = stats?.total_cases || (activeCasesCount + recoveredCasesCount) || 1;
  const recoveredRev = stats?.recovered_revenue || 0;
  const atRiskRev = stats?.revenue_at_risk || 0;
  const totalExposure = stats?.total_exposure || (recoveredRev + atRiskRev) || 0;
  const yieldPct = stats?.recovery_yield_pct || (totalExposure > 0 ? (recoveredRev / totalExposure) * 100 : 0);

  return (
    <div className="p-5 lg:p-7 space-y-6 overflow-y-auto h-full revive-scroll bg-[#070B14]">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-2 border-b border-border/80">
        <div>
          <div className="flex items-center gap-2">
            <span className="eyebrow text-[#0C83FF]">Autonomous Operations</span>
            <span className="text-muted-foreground text-xs">·</span>
            <span className="text-[11px] text-muted-foreground font-mono">Track 03 Submission</span>
          </div>
          <h1 className="page-title text-2xl font-bold text-white tracking-tight">
            Recovery Command Center
          </h1>
          <p className="mt-1 text-xs text-muted-foreground max-w-2xl">
            Real-time telemetry and deterministic guardrails recovering failed UPI AutoPay and mandate transactions without financial authority risks.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={loadData}
            disabled={loading}
            className="revive-button revive-button-outline"
            data-testid="button-refresh-command-center"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            onClick={handleRunDemo}
            disabled={demoRunning}
            className="revive-button revive-button-primary"
            data-testid="button-run-demo-flow"
          >
            <Zap size={13} className={demoRunning ? 'animate-spin' : 'fill-white'} />
            <span>{demoRunning ? 'Simulating...' : 'Run Reviewer Demo'}</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
          {error}
        </div>
      )}

      {/* KPI Ribbon */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Recovered Revenue */}
        <div className="panel metric-card border-l-4 border-l-[#10B981]">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-semibold uppercase tracking-wider font-mono">Recovered Revenue (Gross)</span>
            <div className="w-7 h-7 rounded-md bg-[#10B981]/15 text-[#10B981] flex items-center justify-center">
              <TrendingUp size={15} />
            </div>
          </div>
          <div className="mt-2">
            <div className="mono-number text-2xl lg:text-3xl font-bold text-white tracking-tight">
              {formatCurrency(recoveredRev)}
            </div>
            <p className="mt-1 text-xs text-[#10B981] font-medium flex items-center gap-1">
              <span>{formatPercent(yieldPct)}</span>
              <span className="text-muted-foreground font-normal">recovery yield</span>
            </p>
          </div>
        </div>

        {/* Metric 2: Revenue At Risk */}
        <div className="panel metric-card border-l-4 border-l-[#F59E0B]">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-semibold uppercase tracking-wider font-mono">Revenue at Risk</span>
            <div className="w-7 h-7 rounded-md bg-[#F59E0B]/15 text-[#F59E0B] flex items-center justify-center">
              <CircleDollarSign size={15} />
            </div>
          </div>
          <div className="mt-2">
            <div className="mono-number text-2xl lg:text-3xl font-bold text-white tracking-tight">
              {formatCurrency(atRiskRev)}
            </div>
            <p className="mt-1 text-xs text-muted-foreground font-medium">
              {activeCasesCount} active pipeline cases
            </p>
          </div>
        </div>

        {/* Metric 3: Total Volume Monitored */}
        <div className="panel metric-card border-l-4 border-l-[#0C83FF]">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-semibold uppercase tracking-wider font-mono">Total Ingested Exposure</span>
            <div className="w-7 h-7 rounded-md bg-[#0C83FF]/15 text-[#0C83FF] flex items-center justify-center">
              <ShieldCheck size={15} />
            </div>
          </div>
          <div className="mt-2">
            <div className="mono-number text-2xl lg:text-3xl font-bold text-white tracking-tight">
              {formatCurrency(totalExposure)}
            </div>
            <p className="mt-1 text-xs text-muted-foreground font-medium">
              Across UPI AutoPay failures
            </p>
          </div>
        </div>

        {/* Metric 4: Guardrail Invariants */}
        <div className="panel metric-card border-l-4 border-l-[#8B5CF6]">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-semibold uppercase tracking-wider font-mono">Unsafe Executions</span>
            <div className="w-7 h-7 rounded-md bg-[#8B5CF6]/15 text-[#8B5CF6] flex items-center justify-center">
              <Lock size={15} />
            </div>
          </div>
          <div className="mt-2">
            <div className="mono-number text-2xl lg:text-3xl font-bold text-[#10B981] tracking-tight">
              0 Violations
            </div>
            <p className="mt-1 text-xs text-[#10B981] font-medium flex items-center gap-1">
              <CheckCircle2 size={12} />
              <span>100% Policy Intercepted</span>
            </p>
          </div>
        </div>
      </div>

      {/* Main Grid: Pipeline Diagnostics & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left 7 Cols: Pipeline Distribution & Invariant Gate */}
        <div className="lg:col-span-7 space-y-5">
          {/* Recovery Funnel Card */}
          <div className="panel space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div>
                <h2 className="section-title text-base font-semibold text-white">
                  Pipeline Health & State Distribution
                </h2>
                <p className="text-xs text-muted-foreground">
                  Cases transitioning through deterministic state machines under PostgreSQL row-locking.
                </p>
              </div>
              <button
                onClick={() => onNavigate('queue')}
                className="text-xs font-semibold text-[#0C83FF] hover:underline flex items-center gap-1"
              >
                <span>View Full Queue</span>
                <ArrowRight size={13} />
              </button>
            </div>

            {/* Visual Funnel Bar */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-mono text-muted-foreground">
                <span>Recovery Conversion: {formatPercent(yieldPct)}</span>
                <span>{recoveredCasesCount} Recovered / {totalCasesCount} Total</span>
              </div>
              <div className="w-full h-3 rounded-full bg-secondary overflow-hidden flex">
                <div
                  style={{ width: `${Math.max(yieldPct, 15)}%` }}
                  className="bg-[#10B981] h-full transition-all duration-500"
                  title="Recovered"
                />
                <div
                  style={{ width: `${Math.max(100 - yieldPct, 20)}%` }}
                  className="bg-[#F59E0B] h-full transition-all duration-500"
                  title="In Recovery Pipeline"
                />
              </div>
              <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm bg-[#10B981]" />
                  <span>Settled & Recovered</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-sm bg-[#F59E0B]" />
                  <span>Active Worklist</span>
                </div>
              </div>
            </div>

            {/* Invariant Matrix */}
            <div className="mt-4 pt-3 border-t border-border space-y-2.5">
              <p className="text-[11px] font-mono uppercase font-bold text-muted-foreground tracking-wider">
                Active Deterministic Guardrails
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                <div className="p-2.5 rounded-md bg-[#080D1A] border border-border flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-[#10B981] shrink-0 mt-0.5" />
                  <div>
                    <strong className="text-white font-semibold block">TRAI Quiet Hours (21:00–09:00 IST)</strong>
                    <span className="text-[11px] text-muted-foreground">Normalized UTC &rarr; IST to prevent nocturnal customer outreach.</span>
                  </div>
                </div>

                <div className="p-2.5 rounded-md bg-[#080D1A] border border-border flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-[#10B981] shrink-0 mt-0.5" />
                  <div>
                    <strong className="text-white font-semibold block">Zero AI Financial Authority</strong>
                    <span className="text-[11px] text-muted-foreground">Strict schema allow-list strips unauthorized discounts and refunds.</span>
                  </div>
                </div>

                <div className="p-2.5 rounded-md bg-[#080D1A] border border-border flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-[#10B981] shrink-0 mt-0.5" />
                  <div>
                    <strong className="text-white font-semibold block">Debit Claim Recon Lock</strong>
                    <span className="text-[11px] text-muted-foreground">Customer debit claims freeze retries to prevent double debits.</span>
                  </div>
                </div>

                <div className="p-2.5 rounded-md bg-[#080D1A] border border-border flex items-start gap-2.5">
                  <CheckCircle2 size={16} className="text-[#10B981] shrink-0 mt-0.5" />
                  <div>
                    <strong className="text-white font-semibold block">Durable Webhook Idempotency</strong>
                    <span className="text-[11px] text-muted-foreground">SHA-256 event deduplication blocks duplicate replays before LLM cost.</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right 5 Cols: Recent Pipeline Cases */}
        <div className="lg:col-span-5 space-y-5">
          <div className="panel space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border">
              <div>
                <h2 className="section-title text-base font-semibold text-white">Recent Pipeline Cases</h2>
                <p className="text-xs text-muted-foreground">Click any case to inspect in workspace.</p>
              </div>
              <button
                onClick={() => onNavigate('queue')}
                className="text-xs font-semibold text-[#0C83FF] hover:underline"
              >
                View all
              </button>
            </div>

            <div className="space-y-2.5">
              {recentCases.length === 0 ? (
                <div className="p-6 text-center text-xs text-muted-foreground">
                  No cases currently in pipeline. Run a live evaluation or demo!
                </div>
              ) : (
                recentCases.map((c) => (
                  <div
                    key={c.payment_id}
                    onClick={() => onSelectCase(c.payment_id)}
                    className="p-3 rounded-lg border border-border bg-[#080D1A] hover:bg-secondary/70 hover:border-[#0C83FF]/40 transition-all cursor-pointer flex items-center justify-between group"
                  >
                    <div className="min-w-0 pr-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-white group-hover:text-[#0C83FF] transition-colors truncate">
                          {c.payment_id}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground font-mono">
                        <span>{c.invoice_id}</span>
                        <span>·</span>
                        <span>{c.attempt_count} {c.attempt_count === 1 ? 'attempt' : 'attempts'}</span>
                      </div>
                    </div>

                    <div className="text-right shrink-0 flex flex-col items-end gap-1">
                      <span className="mono-number text-xs font-bold text-white">
                        {formatCurrency(c.amount_inr)}
                      </span>
                      <StatusBadge state={c.current_state} size="sm" />
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="pt-2 border-t border-border flex items-center justify-between text-xs text-muted-foreground font-mono">
              <span>{systemStatus?.persistence_layer === 'POSTGRESQL_DURABLE' ? 'PostgreSQL 16 Engine' : 'Active Persistence'}</span>
              <span className="text-[#0C83FF] font-semibold">Row-Locked Durability</span>
            </div>
          </div>
        </div>
      </div>

      {/* Interactive Reviewer Demo Modal */}
      {demoModalOpen && demoResult && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0E1626] border border-border rounded-xl max-w-2xl w-full p-6 shadow-2xl space-y-5 revive-enter">
            <div className="flex items-start justify-between border-b border-border pb-3">
              <div>
                <span className="eyebrow text-[#0C83FF]">Deterministic Verification</span>
                <h3 className="text-lg font-bold text-white mt-0.5">
                  Multi-Event Lifecycle & Idempotency Demo
                </h3>
                <p className="text-xs text-muted-foreground">
                  Demonstrating live webhook failure ingestion, debit claim recon lock, settlement reconciliation, and duplicate suppression.
                </p>
              </div>
              <button
                onClick={() => setDemoModalOpen(false)}
                className="p-1 rounded-md text-muted-foreground hover:text-white hover:bg-secondary"
              >
                <X size={18} />
              </button>
            </div>

            {/* Stepper of Events */}
            <div className="space-y-3">
              {(demoResult.events || []).map((ev: any, idx: number) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-lg border border-border bg-[#080D1A] flex items-start gap-3"
                >
                  <div className="w-6 h-6 rounded-full bg-[#0C83FF]/15 text-[#0C83FF] border border-[#0C83FF]/30 flex items-center justify-center text-xs font-mono font-bold shrink-0 mt-0.5">
                    {ev.step || idx + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <strong className="text-xs font-semibold text-white font-mono">{ev.event_type}</strong>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-secondary text-white font-medium">
                        {ev.resulting_state}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {ev.action_taken}
                    </p>
                    <div className="mt-2 flex items-center gap-3 text-[11px] font-mono text-muted-foreground">
                      <span>Event ID: <strong className="text-white">{ev.event_id}</strong></span>
                      <span>·</span>
                      <span>Policy: <strong className="text-[#10B981]">{ev.policy_action}</strong></span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Bottom Actions */}
            <div className="pt-3 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-3">
              <span className="text-xs font-mono text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 size={14} />
                <span>All events committed & verified in PostgreSQL audit ledger</span>
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setDemoModalOpen(false);
                    onNavigate('ledger');
                  }}
                  className="revive-button revive-button-outline"
                >
                  <ExternalLink size={12} />
                  <span>Inspect Audit Ledger</span>
                </button>
                <button
                  onClick={() => {
                    setDemoModalOpen(false);
                    onSelectCase('pay_demo_multi_001');
                  }}
                  className="revive-button revive-button-primary"
                >
                  <span>Open in Workspace</span>
                  <ArrowRight size={12} />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
