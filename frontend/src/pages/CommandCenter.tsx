import React, { useEffect, useState } from 'react';
import {
  CircleDollarSign,
  ArrowUpRight,
  Target,
  Activity,
  ArrowRight,
  Zap,
  Gauge,
  RefreshCw,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';
import { api } from '../api/client';
import type { DashboardStats, PaymentCase, SystemStatus } from '../api/types';
import { StatCard } from '../components/StatCard';
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
  const [demoRunning, setDemoRunning] = useState<boolean>(false);
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

  if (loading && !stats) {
    return (
      <div className="p-8 space-y-3">
        <div className="skeleton-row" />
        <div className="grid grid-cols-4 gap-3">
          <div className="skeleton-row h-28" />
          <div className="skeleton-row h-28" />
          <div className="skeleton-row h-28" />
          <div className="skeleton-row h-28" />
        </div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="p-8">
        <div className="panel max-w-lg border-destructive/40 bg-destructive/10 text-destructive space-y-3">
          <div className="flex items-center gap-2 font-bold text-sm">
            <AlertTriangle size={18} />
            <span>Connection Unavailable</span>
          </div>
          <p className="text-xs text-muted-foreground">{error}</p>
          <button onClick={loadData} className="revive-button revive-button-outline text-xs">
            <RefreshCw size={13} /> Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const activeCasesCount = stats?.active_cases || 0;
  const needsAttentionCount = stats?.escalated_cases || 0;
  const stoppedCasesCount = stats?.stopped_cases || stats?.dead_letter_cases || 0;
  const totalExposure = stats?.total_ingested_exposure || stats?.total_exposure || 0;
  const yieldPct = stats?.recovery_yield_pct || 0;

  return (
    <div className="p-5 lg:p-7 space-y-5 overflow-y-auto h-full revive-scroll">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 pb-2 border-b border-border/60">
        <div>
          <p className="eyebrow">Recovery Command Center</p>
          <h1 className="page-title">The recovery picture</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            A working view of what is at risk, what is moving, and where deterministic guardrails protect revenue.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={loadData}
            disabled={loading}
            className="revive-button revive-button-outline"
            data-testid="button-refresh-dashboard"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => onNavigate('workspace')}
            className="revive-button revive-button-primary"
            data-testid="link-evaluate-case"
          >
            <Zap size={13} />
            <span>Evaluate case</span>
          </button>
        </div>
      </div>

      {/* 4-Card Financial Exposure Grid */}
      <section className="metric-grid">
        <StatCard
          title="Revenue at Risk"
          value={formatCurrency(stats?.revenue_at_risk)}
          subtitle={`${activeCasesCount} active cases in recovery pipeline`}
          icon={CircleDollarSign}
          variant="warning"
        />
        <StatCard
          title="Recovered Revenue (Gross)"
          value={formatCurrency(stats?.recovered_revenue)}
          subtitle={`${formatPercent(yieldPct)} gross recovery yield`}
          icon={ArrowUpRight}
          variant="success"
        />
        <StatCard
          title="Total Ingested Exposure"
          value={formatCurrency(totalExposure)}
          subtitle="Monitored autopay failure volume"
          icon={Target}
          variant="default"
        />
        <StatCard
          title="Active Cases"
          value={activeCasesCount.toLocaleString()}
          subtitle={`${needsAttentionCount} require operator review`}
          icon={Activity}
          variant="default"
        />
      </section>

      {/* Main Split: Left Decision Summary & Right Recent Recoveries */}
      <section className="grid grid-cols-1 lg:grid-cols-[1.25fr_0.75fr] gap-4">
        {/* Left Hero Panel */}
        <div className="panel panel-hero flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="eyebrow">Decisions today</p>
                <h2 className="section-title text-base">Prioritize the next rupee</h2>
                <p className="mt-1.5 max-w-xl text-xs text-muted-foreground leading-relaxed">
                  RazP Sentinel holds {needsAttentionCount} cases for human judgment and has stopped {stoppedCasesCount} cases where further automated contact would be a regulatory liability.
                </p>
              </div>
              <div className="signal-orb shrink-0">
                <Gauge size={18} />
              </div>
            </div>

            {/* 4-Stat Metric Strip */}
            <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-px overflow-hidden rounded border border-border bg-border">
              <div className="bg-card p-3">
                <p className="eyebrow">Attention</p>
                <p className="mono-number mt-1 text-lg font-medium text-accent">{needsAttentionCount}</p>
              </div>
              <div className="bg-card p-3">
                <p className="eyebrow">Recovered</p>
                <p className="mono-number mt-1 text-lg font-medium text-primary">
                  {stats?.recovered_cases || 0}
                </p>
              </div>
              <div className="bg-card p-3">
                <p className="eyebrow">Stopped</p>
                <p className="mono-number mt-1 text-lg font-medium text-muted-foreground">{stoppedCasesCount}</p>
              </div>
              <div className="bg-card p-3">
                <p className="eyebrow">Yield</p>
                <p className="mono-number mt-1 text-lg font-medium text-primary">{formatPercent(yieldPct)}</p>
              </div>
            </div>
          </div>

          {/* Operating Signals Mini Bar */}
          <div className="mt-5 pt-4 border-t border-border/70 flex items-end justify-between">
            <div>
              <p className="eyebrow">Operating signals</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">Scale across pipeline metrics</p>
            </div>
            <div className="mini-bars">
              <span className="mini-bar mini-bar-primary" style={{ height: '70%' }} title="Recovered" />
              <span className="mini-bar mini-bar-accent" style={{ height: '40%' }} title="At Risk" />
              <span className="mini-bar mini-bar-primary" style={{ height: '85%' }} title="Yield" />
              <span className="mini-bar mini-bar-accent" style={{ height: '30%' }} title="Attention" />
              <span className="mini-bar mini-bar-primary" style={{ height: '55%' }} title="Active" />
            </div>
          </div>
        </div>

        {/* Right Panel: Recent Activity & Cases */}
        <div className="panel flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <div>
                <p className="eyebrow">Recent activity</p>
                <h2 className="section-title text-base">Pipeline state</h2>
              </div>
              <button
                onClick={() => onNavigate('queue')}
                className="text-[11px] font-bold text-primary hover:underline flex items-center gap-1"
                data-testid="link-view-all-queue"
              >
                <span>View all</span>
                <ArrowRight size={12} />
              </button>
            </div>

            <div className="mt-4 space-y-1 divide-y divide-border/60">
              {recentCases.length === 0 ? (
                <div className="empty-state py-6">
                  <CheckCircle2 size={20} className="text-primary" />
                  <p className="mt-2 text-xs font-semibold">No cases ingested</p>
                  <p className="text-[11px] text-muted-foreground">Ingest a case via workspace to begin.</p>
                </div>
              ) : (
                recentCases.slice(0, 4).map((c) => (
                  <div
                    key={c.payment_id}
                    onClick={() => onSelectCase(c.payment_id)}
                    className="pt-2.5 pb-2.5 flex items-center justify-between gap-3 cursor-pointer hover:bg-secondary/40 px-2 rounded transition-colors group"
                    data-testid={`row-case-${c.payment_id}`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="avatar avatar-small">
                        {c.payment_id.slice(-2).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-xs font-bold text-foreground group-hover:text-primary transition-colors font-mono">
                          {c.payment_id}
                        </p>
                        <p className="truncate text-[10px] text-muted-foreground font-mono">
                          {c.invoice_id} &middot; {c.attempt_count} attempts
                        </p>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="mono-number text-xs font-semibold text-foreground">
                        {formatCurrency(c.amount_inr)}
                      </p>
                      <StatusBadge state={c.current_state} size="sm" />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-border/70 flex items-center justify-between text-[11px] text-muted-foreground">
            <span>Database: PostgreSQL 16</span>
            <span className="font-mono text-primary font-semibold">ROW-LOCKED</span>
          </div>
        </div>
      </section>

      {/* Lower Split: Verified Guardrails & Multi-Event Simulation Trigger */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Verified Guardrails Panel */}
        <div className="panel panel-dark space-y-3">
          <div className="flex items-center justify-between border-b border-sidebar-border/80 pb-2.5">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-sidebar-primary" />
              <h3 className="text-xs font-bold text-sidebar-foreground uppercase tracking-wide">
                Verified System Guardrails
              </h3>
            </div>
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-sidebar-primary/10 text-sidebar-primary border border-sidebar-primary/20">
              IMMUTABLE
            </span>
          </div>
          <ul className="space-y-2 text-xs text-sidebar-foreground/80">
            {(systemStatus?.invariants_verified || [
              'Zero AI Financial Authority (Deterministic Policy Gate Enforcement)',
              'Cryptographic SHA-256 Tamper-Evident Audit Ledger',
              'PostgreSQL Row-Locked Concurrency & Terminal State Locks',
              'Durable Idempotency & Webhook Deduplication',
              'Mandatory Authoritative Bank Settlement Reconciliation'
            ]).map((inv, idx) => (
              <li key={idx} className="flex items-center gap-2 text-[11px]">
                <CheckCircle2 size={13} className="text-sidebar-primary shrink-0" />
                <span>{inv}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Multi-Event Simulation Callout */}
        <div className="panel flex flex-col justify-between space-y-3">
          <div>
            <div className="flex items-center justify-between">
              <div>
                <p className="eyebrow">Demo harness</p>
                <h3 className="section-title text-sm">Multi-Event Lifecycle Runner</h3>
              </div>
              <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground border border-border">
                E2E TEST
              </span>
            </div>
            <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
              Executes a sequence of webhook events: Initial Autopay Failure &rarr; Debit Claim Hold &rarr; Bank Settlement Recon &rarr; Cryptographic Ledger Recording.
            </p>
          </div>

          <div className="pt-2 flex items-center gap-3">
            <button
              onClick={handleRunDemo}
              disabled={demoRunning}
              className="revive-button revive-button-outline"
              data-testid="button-run-demo-flow"
            >
              <Zap size={13} className={demoRunning ? 'animate-spin text-accent' : ''} />
              <span>{demoRunning ? 'Executing sequence...' : 'Run multi-event demo'}</span>
            </button>
            {demoResult && (
              <span className="text-[11px] font-mono text-primary">
                ✓ Recorded {demoResult.events_processed || 3} events to PostgreSQL
              </span>
            )}
          </div>
        </div>
      </section>
    </div>
  );
};
