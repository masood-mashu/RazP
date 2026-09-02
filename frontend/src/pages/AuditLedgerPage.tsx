import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  RefreshCw,
  RotateCcw,
  Hash,
  ShieldCheck,
  CheckCircle2,
  Search,
  BookOpen
} from 'lucide-react';
import { api } from '../api/client';
import type { LedgerResponse, AuditBlock } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

export const AuditLedgerPage: React.FC = () => {
  const [ledgerData, setLedgerData] = useState<LedgerResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [selectedBlock, setSelectedBlock] = useState<AuditBlock | null>(null);
  const [searchTerm, setSearchTerm] = useState<string>('');

  const fetchLedger = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getLedger();
      setLedgerData(res);
      if (res.blocks.length > 0 && !selectedBlock) {
        setSelectedBlock(res.blocks[res.blocks.length - 1]);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to fetch audit ledger from PostgreSQL.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLedger();
  }, []);

  const handleTamperTest = async () => {
    const ok = window.confirm(
      'DEMO-ONLY DESTRUCTIVE SIMULATION:\n\nThis will execute an out-of-band SQL UPDATE on block 0 in PostgreSQL to simulate malicious database tampering and verify cryptographic chain failure detection.\n\nProceed?'
    );
    if (!ok) return;

    try {
      const res = await api.tamperTestLedger();
      setActionMessage(`[DEMO SIMULATION] SQL UPDATE executed on block 0: Cryptographic detection ${res.cryptographic_detection_successful ? 'SUCCESSFUL (BROKEN HASH DETECTED)' : 'FAILED'}`);
      await fetchLedger();
    } catch (err: any) {
      alert(`Tamper test failed: ${err.message}`);
    }
  };

  const handleRestore = async () => {
    try {
      await api.restoreLedger();
      setActionMessage('[DEMO RESTORE] Audit ledger integrity restored to valid SHA-256 state.');
      await fetchLedger();
    } catch (err: any) {
      alert(`Restore failed: ${err.message}`);
    }
  };

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

  const getBlockNum = (b: AuditBlock) => (b.block_index !== undefined ? b.block_index : b.index);

  const filteredBlocks = (ledgerData?.blocks || []).filter((b) =>
    `${b.payment_id} ${b.action_executed} ${b.resulting_state} ${b.current_hash} ${b.actor_id || ''}`
      .toLowerCase()
      .includes(searchTerm.toLowerCase())
  );

  return (
    <div className="p-5 lg:p-7 space-y-5 overflow-y-auto h-full revive-scroll">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3 pb-2 border-b border-border/60">
        <div>
          <p className="eyebrow">Cryptographic SHA-256 Audit Ledger</p>
          <h1 className="page-title">Audit ledger</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            A chronological, tamper-evident SHA-256 cryptographic chain recording every recommendation, guardrail check, and recovery mutation.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={fetchLedger}
            disabled={loading}
            className="revive-button revive-button-outline"
            data-testid="button-refresh-ledger"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh ledger</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded border border-destructive/40 bg-destructive/10 text-destructive text-xs flex items-center gap-2">
          <AlertTriangle size={15} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Integrity Summary Hero Card */}
      <div className={`panel ${ledgerData?.is_integrity_valid ? 'border-primary/40 bg-primary/5' : 'border-destructive/50 bg-destructive/10'}`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${ledgerData?.is_integrity_valid ? 'bg-primary/20 text-primary' : 'bg-destructive/20 text-destructive'}`}>
              {ledgerData?.is_integrity_valid ? <ShieldCheck size={20} /> : <AlertTriangle size={20} />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-foreground">
                  {ledgerData?.is_integrity_valid ? 'CRYPTOGRAPHIC INTEGRITY VERIFIED' : 'Ledger Integrity Compromised'}
                </h2>
                <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-bold ${ledgerData?.is_integrity_valid ? 'bg-primary/20 text-primary border border-primary/30' : 'bg-destructive/20 text-destructive border border-destructive/30'}`}>
                  {ledgerData?.is_integrity_valid ? 'SHA-256 VERIFIED' : 'TAMPER DETECTED'}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {ledgerData?.is_integrity_valid
                  ? `All ${ledgerData?.total_blocks || 0} blocks connected via continuous SHA-256 hashes in PostgreSQL.`
                  : ledgerData?.integrity_error || 'A block hash does not match canonical recomputation.'}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleTamperTest}
              className="revive-button revive-button-outline text-destructive hover:border-destructive/60"
              title="Simulate malicious database edit on Block 0"
              data-testid="button-tamper-test"
            >
              <AlertTriangle size={13} />
              <span>Simulate tamper</span>
            </button>
            <button
              onClick={handleRestore}
              className="revive-button revive-button-outline"
              title="Restore valid hash state"
              data-testid="button-restore-ledger"
            >
              <RotateCcw size={13} />
              <span>Restore chain</span>
            </button>
          </div>
        </div>

        {actionMessage && (
          <div className="mt-3 pt-3 border-t border-border/70 text-[11px] font-mono text-primary">
            {actionMessage}
          </div>
        )}
      </div>

      {/* Main Table Panel */}
      <div className="panel p-0 overflow-hidden">
        {/* Toolbar */}
        <div className="queue-toolbar">
          <div className="search-box">
            <Search size={15} className="text-muted-foreground shrink-0" />
            <input
              type="text"
              placeholder="Search block, case, action, actor, or hash..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              data-testid="input-search-ledger"
            />
          </div>
          <div className="ledger-count">
            <BookOpen size={13} />
            <span>{ledgerData?.total_blocks || 0} blocks retained</span>
          </div>
        </div>

        {/* Table */}
        {loading && !ledgerData ? (
          <div className="p-6 space-y-2">
            <div className="skeleton-row" />
            <div className="skeleton-row" />
            <div className="skeleton-row" />
          </div>
        ) : filteredBlocks.length === 0 ? (
          <div className="empty-state py-10">
            <CheckCircle2 size={22} className="text-primary" />
            <p className="mt-2 text-xs font-bold">No blocks found</p>
            <p className="text-[11px] text-muted-foreground">Run an evaluation in Case Workspace to write blocks.</p>
          </div>
        ) : (
          <div className="table-scroll revive-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Block #</th>
                  <th>Timestamp</th>
                  <th>Case / Payment</th>
                  <th>Action executed</th>
                  <th>Resulting state</th>
                  <th>SHA-256 Hash</th>
                </tr>
              </thead>
              <tbody>
                {filteredBlocks.map((block) => {
                  const blockNum = getBlockNum(block);
                  const isSel = selectedBlock && getBlockNum(selectedBlock) === blockNum;
                  return (
                    <tr
                      key={blockNum}
                      onClick={() => setSelectedBlock(block)}
                      className={`data-row cursor-pointer ${isSel ? 'bg-secondary/60' : ''}`}
                      data-testid={`row-block-${blockNum}`}
                    >
                      <td>
                        <span className="mono-number text-xs font-bold text-primary">
                          #{blockNum}
                        </span>
                      </td>
                      <td>
                        <span className="text-[11px] font-mono text-muted-foreground">
                          {formatDateTime(block.timestamp)}
                        </span>
                      </td>
                      <td>
                        <span className="text-xs font-bold font-mono text-foreground">
                          {block.payment_id}
                        </span>
                      </td>
                      <td>
                        <span className="action-badge">
                          {block.action_executed}
                        </span>
                      </td>
                      <td>
                        <StatusBadge state={block.resulting_state} size="sm" />
                      </td>
                      <td>
                        <span className="text-[10px] font-mono text-muted-foreground truncate max-w-xs block" title={block.current_hash}>
                          {block.current_hash.slice(0, 16)}...
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Selected Block Inspector Drawer */}
      {selectedBlock && (
        <div className="panel space-y-3 revive-enter">
          <div className="flex items-center justify-between border-b border-border/70 pb-2.5">
            <div className="flex items-center gap-2">
              <Hash size={15} className="text-primary" />
              <h3 className="section-title text-sm">
                Block #{getBlockNum(selectedBlock)} Cryptographic Inspector
              </h3>
            </div>
            <span className="text-[10px] font-mono text-muted-foreground">
              {formatDateTime(selectedBlock.timestamp)}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div className="space-y-1.5">
              <div className="p-2 rounded bg-secondary/50 border border-border">
                <span className="eyebrow block">Current Block Hash</span>
                <span className="text-[11px] text-primary break-all font-semibold">
                  {selectedBlock.current_hash}
                </span>
              </div>
              <div className="p-2 rounded bg-secondary/50 border border-border">
                <span className="eyebrow block">Previous Block Hash</span>
                <span className="text-[11px] text-muted-foreground break-all">
                  {selectedBlock.previous_hash}
                </span>
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="p-2 rounded bg-secondary/50 border border-border">
                <span className="eyebrow block">Canonical Payload Hash</span>
                <span className="text-[11px] text-muted-foreground break-all">
                  {selectedBlock.payload_hash || selectedBlock.telemetry_hash}
                </span>
              </div>
              <div className="p-2 rounded bg-secondary/50 border border-border">
                <span className="eyebrow block">Audit Metadata</span>
                <p className="text-[11px] text-foreground">
                  Action: <strong>{selectedBlock.action_executed}</strong> &rarr; State: <strong>{selectedBlock.resulting_state}</strong>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
