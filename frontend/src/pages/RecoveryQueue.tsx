import React, { useEffect, useState } from 'react';
import {
  Search,
  SlidersHorizontal,
  RefreshCw,
  ChevronRight,
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import { api } from '../api/client';
import type { PaymentCase } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

interface RecoveryQueueProps {
  onSelectCase: (paymentId: string) => void;
}

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
    <div className="p-5 lg:p-7 space-y-5 overflow-y-auto h-full revive-scroll">
      {/* Page Heading */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 pb-2 border-b border-border/60">
        <div>
          <p className="eyebrow">Recovery operations</p>
          <h1 className="page-title">Recovery queue</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            A ranked worklist of autopay failures. Every row carries sufficient context to make decisions without opening separate reports.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={fetchCases}
            disabled={loading}
            className="revive-button revive-button-outline"
            data-testid="button-refresh-queue"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh queue</span>
          </button>
        </div>
      </div>

      {/* Main Table Panel */}
      <div className="panel p-0 overflow-hidden">
        {/* Toolbar */}
        <div className="queue-toolbar">
          <form onSubmit={handleSearchSubmit} className="search-box">
            <Search size={15} className="text-muted-foreground shrink-0" />
            <input
              type="text"
              placeholder="Search payment ID, invoice, or gateway code..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              data-testid="input-search-cases"
            />
          </form>

          <div className="queue-actions">
            {/* Status Filter */}
            <div className="select-wrap">
              <SlidersHorizontal size={13} className="text-muted-foreground shrink-0" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                data-testid="select-case-status"
              >
                <option value="ALL">All statuses</option>
                <option value="PAYMENT_FAILED">Payment failed</option>
                <option value="PAUSE_RECON_VERIFY">Recon verify</option>
                <option value="PTP_SCHEDULED">PTP scheduled</option>
                <option value="RETRY_SCHEDULED">Retry queued</option>
                <option value="RECOVERED">Recovered</option>
                <option value="ESCALATED_HUMAN_OPS">Escalated</option>
                <option value="DEAD_LETTER">Stopped</option>
              </select>
            </div>

            {/* Rank Sort */}
            <div className="select-wrap hidden sm:flex">
              <span className="text-[10px] text-muted-foreground">Rank</span>
              <select
                value={sortField}
                onChange={(e) => setSortField(e.target.value as any)}
                data-testid="select-case-sort"
              >
                <option value="updated_at">Last updated</option>
                <option value="amount">Amount at risk</option>
                <option value="attempts">Attempt count</option>
              </select>
            </div>
          </div>
        </div>

        {/* Queue Metadata Line */}
        <div className="queue-meta">
          <span>{loading ? 'Loading queue from PostgreSQL…' : `${sortedCases.length} cases in view`}</span>
          <div className="queue-meta-right">
            <span className="legend-dot legend-dot-copper" />
            <span>Needs decision</span>
            <span className="legend-dot legend-dot-green" />
            <span>Active recovery</span>
          </div>
        </div>

        {/* Error or Empty State or Table */}
        {loading && cases.length === 0 ? (
          <div className="p-6 space-y-2">
            <div className="skeleton-row" />
            <div className="skeleton-row" />
            <div className="skeleton-row" />
            <div className="skeleton-row" />
          </div>
        ) : error ? (
          <div className="empty-state py-8">
            <AlertCircle size={22} className="text-destructive" />
            <p className="mt-2 text-xs font-bold">Failed to load queue</p>
            <p className="text-[11px] text-muted-foreground">{error}</p>
            <button onClick={fetchCases} className="revive-button revive-button-outline text-xs mt-3">
              <RefreshCw size={13} /> Retry
            </button>
          </div>
        ) : sortedCases.length === 0 ? (
          <div className="empty-state py-12">
            <CheckCircle2 size={24} className="text-primary" />
            <p className="mt-3 text-sm font-bold">Clear for now</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {searchTerm ? 'No cases match your search term.' : 'No recovery cases found matching active filter.'}
            </p>
          </div>
        ) : (
          <div className="table-scroll revive-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Case / Payment</th>
                  <th>Amount at risk</th>
                  <th>Payment method</th>
                  <th>Attempts</th>
                  <th>Last updated</th>
                  <th>Status</th>
                  <th className="text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedCases.map((item) => (
                  <tr
                    key={item.payment_id}
                    className="data-row cursor-pointer"
                    onClick={() => onSelectCase(item.payment_id)}
                    data-testid={`row-case-${item.payment_id}`}
                  >
                    <td>
                      <div className="flex items-center gap-3">
                        <div className="avatar">
                          {item.payment_id.slice(-2).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-foreground font-mono">
                            {item.payment_id}
                          </p>
                          <p className="text-[10px] text-muted-foreground font-mono">
                            {item.invoice_id}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="mono-number text-xs font-semibold text-foreground">
                        {formatCurrency(item.amount_inr)}
                      </span>
                    </td>
                    <td>
                      <span className="action-badge">
                        {item.payment_method || 'UPI_AUTOPAY'}
                      </span>
                    </td>
                    <td>
                      <span className="text-xs font-mono text-muted-foreground">
                        {item.attempt_count} / 3
                      </span>
                    </td>
                    <td>
                      <span className="text-[11px] font-mono text-muted-foreground">
                        {formatDate(item.updated_at)}
                      </span>
                    </td>
                    <td>
                      <StatusBadge state={item.current_state} size="sm" />
                    </td>
                    <td className="text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectCase(item.payment_id);
                        }}
                        className="revive-button revive-button-quiet text-xs"
                        title="Open in Case Workspace"
                      >
                        <span>Inspect</span>
                        <ChevronRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
