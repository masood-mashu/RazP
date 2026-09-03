import React, { useEffect, useState } from 'react';
import {
  Search,
  RefreshCw,
  ArrowUpRight,
  AlertCircle
} from 'lucide-react';
import { api } from '../api/client';
import type { PaymentCase } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

interface RecoveryQueueProps {
  onSelectCase: (paymentId: string) => void;
}

const FILTER_TABS = [
  { id: 'ALL', label: 'All Cases' },
  { id: 'AWAITING_CUSTOMER_ACTION', label: 'Needs Action' },
  { id: 'PTP_SCHEDULED', label: 'PTP Scheduled' },
  { id: 'PAUSE_RECON_VERIFY', label: 'Recon Lock' },
  { id: 'RECOVERED', label: 'Recovered' },
  { id: 'ESCALATED_HUMAN_OPS', label: 'Escalations' },
];

export const RecoveryQueue: React.FC<RecoveryQueueProps> = ({ onSelectCase }) => {
  const [cases, setCases] = useState<PaymentCase[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [sortField, setSortField] = useState<'amount' | 'updated_at' | 'attempts'>('updated_at');

  const fetchCases = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getCases({
        search: searchTerm || undefined,
        status: statusFilter !== 'ALL' ? statusFilter : undefined,
        limit: 100,
      });
      setCases(res.cases);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch recovery cases from PostgreSQL.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [statusFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchCases();
  };

  const sortedCases = [...cases].sort((a, b) => {
    if (sortField === 'amount') {
      return b.amount_inr - a.amount_inr;
    }
    if (sortField === 'attempts') {
      return b.attempt_count - a.attempt_count;
    }
    const dateA = new Date(a.updated_at).getTime();
    const dateB = new Date(b.updated_at).getTime();
    return dateB - dateA;
  });

  const formatCurrency = (amt: number) =>
    new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(amt);

  const formatDate = (iso: string) => {
    if (!iso) return '—';
    return new Intl.DateTimeFormat('en-IN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso));
  };

  return (
    <div className="p-5 lg:p-7 space-y-5 overflow-y-auto h-full revive-scroll bg-[#070B14]">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-2 border-b border-border">
        <div>
          <span className="eyebrow text-[#0C83FF]">Workflow Management</span>
          <h1 className="page-title text-2xl font-bold text-white tracking-tight">Recovery Queue</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Ranked worklist of failed Autopay mandates. Select any transaction to trigger live Gemini reasoning, audit trail, and policy gate checks.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={fetchCases}
            disabled={loading}
            className="revive-button revive-button-outline"
            data-testid="button-refresh-queue"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh Queue</span>
          </button>
        </div>
      </div>

      {/* Filter Chips & Search Bar */}
      <div className="panel p-3.5 space-y-3">
        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 revive-scroll">
          {FILTER_TABS.map((tab) => {
            const isSelected = statusFilter === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-all ${
                  isSelected
                    ? 'bg-[#0C83FF] text-white shadow-sm'
                    : 'bg-[#080D1A] text-muted-foreground hover:text-white hover:bg-secondary border border-border/80'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Search & Sort Controls */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2 border-t border-border/60">
          <form onSubmit={handleSearchSubmit} className="search-box w-full sm:w-auto">
            <Search size={14} className="text-muted-foreground" />
            <input
              type="text"
              placeholder="Search payment ID or invoice..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="text-xs"
              data-testid="input-search-queue"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => {
                  setSearchTerm('');
                  fetchCases();
                }}
                className="text-[10px] text-muted-foreground hover:text-white"
              >
                Clear
              </button>
            )}
          </form>

          <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground w-full sm:w-auto justify-end">
            <span>Sort by:</span>
            <div className="select-wrap">
              <select
                value={sortField}
                onChange={(e) => setSortField(e.target.value as any)}
                data-testid="select-sort-queue"
              >
                <option value="updated_at">Last Updated</option>
                <option value="amount">Amount (High &rarr; Low)</option>
                <option value="attempts">Attempts</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Cases Table */}
      <div className="panel p-0 overflow-hidden">
        {loading && cases.length === 0 ? (
          <div className="p-8 text-center text-xs text-muted-foreground">
            <RefreshCw size={18} className="animate-spin text-[#0C83FF] mx-auto mb-2" />
            <span>Loading recovery queue from PostgreSQL...</span>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-xs text-rose-400">
            <AlertCircle size={18} className="mx-auto mb-2 text-rose-400" />
            <span>{error}</span>
          </div>
        ) : sortedCases.length === 0 ? (
          <div className="p-12 text-center text-xs text-muted-foreground space-y-2">
            <p className="font-semibold text-white">No recovery cases found.</p>
            <p>Try clearing your search or filter parameters.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Payment ID</th>
                  <th>Invoice ID</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Attempts</th>
                  <th>Last Updated</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedCases.map((c) => (
                  <tr
                    key={c.payment_id}
                    onClick={() => onSelectCase(c.payment_id)}
                    className="data-row"
                    data-testid={`row-case-${c.payment_id}`}
                  >
                    <td>
                      <span className="font-mono font-bold text-white text-xs hover:text-[#0C83FF] transition-colors">
                        {c.payment_id}
                      </span>
                    </td>
                    <td>
                      <span className="font-mono text-muted-foreground text-xs">{c.invoice_id}</span>
                    </td>
                    <td>
                      <span className="mono-number font-bold text-white text-xs">
                        {formatCurrency(c.amount_inr)}
                      </span>
                    </td>
                    <td>
                      <StatusBadge state={c.current_state} size="sm" />
                    </td>
                    <td>
                      <span className="font-mono text-muted-foreground text-xs">
                        {c.attempt_count}
                      </span>
                    </td>
                    <td>
                      <span className="font-mono text-muted-foreground text-xs">
                        {formatDate(c.updated_at)}
                      </span>
                    </td>
                    <td className="text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectCase(c.payment_id);
                        }}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-[#0C83FF]/15 hover:bg-[#0C83FF]/30 text-[#0C83FF] text-[11px] font-semibold transition-all border border-[#0C83FF]/30"
                      >
                        <span>Workspace</span>
                        <ArrowUpRight size={12} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="p-3 border-t border-border bg-[#080D1A] flex items-center justify-between text-xs text-muted-foreground font-mono">
          <span>Showing {sortedCases.length} case{sortedCases.length === 1 ? '' : 's'}</span>
          <span>PostgreSQL Active Persistence</span>
        </div>
      </div>
    </div>
  );
};
