import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  RefreshCw,
  RotateCcw,
  Hash,
  CheckCircle2,
  Search,
  ArrowUpRight,
  ShieldCheck,
  Cpu
} from 'lucide-react';
import { api } from '../api/client';
import type { LedgerResponse, AuditBlock } from '../api/types';
import { StatusBadge } from '../components/StatusBadge';

interface AuditLedgerPageProps {
  onSelectCase?: (paymentId: string) => void;
}

export const AuditLedgerPage: React.FC<AuditLedgerPageProps> = ({ onSelectCase }) => {
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
      'DEMO-ONLY TAMPER SIMULATION:\n\nThis will execute an out-of-band SQL UPDATE on block 0 in PostgreSQL to simulate malicious database tampering and verify cryptographic chain failure detection.\n\nProceed?'
    );
    if (!ok) return;

    try {
      const res = await api.tamperTestLedger();
      setActionMessage(
        `[TAMPER SIMULATION] Block 0 payload mutated: Detection ${
          res.cryptographic_detection_successful ? 'SUCCESSFUL (Broken Hash Intercepted)' : 'FAILED'
        }`
      );
      await fetchLedger();
    } catch (err: any) {
      alert(`Tamper test failed: ${err.message}`);
    }
  };

  const handleRestore = async () => {
    try {
      await api.restoreLedger();
      setActionMessage('[RESTORED] Audit ledger integrity restored to authentic SHA-256 state.');
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

  const isValid = ledgerData?.is_integrity_valid ?? true;

  return (
    <div className="p-5 lg:p-7 space-y-6 overflow-y-auto h-full revive-scroll bg-[#070B14]">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-2 border-b border-border">
        <div>
          <div className="flex items-center gap-2">
            <span className="eyebrow text-[#0C83FF]">Cryptographic SHA-256 Audit Ledger</span>
            <span className="text-muted-foreground text-xs">·</span>
            <span className="text-[11px] text-muted-foreground font-mono">Non-Repudiation Spine</span>
          </div>
          <h1 className="page-title text-2xl font-bold text-white tracking-tight">Audit Ledger</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Tamper-evident SHA-256 hash-chained sequence recording every decision, policy check, and mutation in PostgreSQL.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <button
            onClick={fetchLedger}
            disabled={loading}
            className="revive-button revive-button-outline"
            data-testid="button-refresh-ledger"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
          <button
            onClick={handleTamperTest}
            className="revive-button revive-button-outline border-amber-500/40 text-amber-400 hover:bg-amber-500/10"
            title="Simulate out-of-band database row modification"
            data-testid="button-tamper-ledger"
          >
            <AlertTriangle size={13} />
            <span>Simulate DB Tamper</span>
          </button>
          {!isValid && (
            <button
              onClick={handleRestore}
              className="revive-button revive-button-primary"
              title="Restore genuine block hashes"
              data-testid="button-restore-ledger"
            >
              <RotateCcw size={13} />
              <span>Restore Integrity</span>
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2.5">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Integrity Banner */}
      <div
        className={`p-4 rounded-lg border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs ${
          isValid
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
            : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
        }`}
      >
        <div className="flex items-center gap-2.5">
          {isValid ? (
            <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />
          ) : (
            <AlertTriangle size={18} className="text-rose-400 shrink-0" />
          )}
          <div>
            <strong className="font-semibold block text-white text-sm">
              {isValid
                ? 'CRYPTOGRAPHIC INTEGRITY VERIFIED · Non-Repudiation Guaranteed'
                : 'Tamper Detected · Cryptographic Hash Chain Broken'}
            </strong>
            <span className="text-muted-foreground text-xs">
              {isValid
                ? `All ${ledgerData?.total_blocks || 0} blocks successfully validated against previous SHA-256 hashes.`
                : ledgerData?.integrity_error || 'Calculated SHA-256 hash does not match block header.'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 font-mono text-xs">
          <span>Source: <strong className="text-white">PostgreSQL 16</strong></span>
          <span>·</span>
          <span>Blocks: <strong className="text-white">{ledgerData?.total_blocks || 0}</strong></span>
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 rounded-md bg-secondary border border-border text-xs font-mono text-[#0C83FF]">
          {actionMessage}
        </div>
      )}

      {/* Search Toolbar */}
      <div className="panel p-3 flex items-center justify-between gap-3">
        <div className="search-box max-w-md w-full">
          <Search size={14} className="text-muted-foreground" />
          <input
            type="text"
            placeholder="Search by Payment ID, Action, Hash, or Actor..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="text-xs"
            data-testid="input-search-ledger"
          />
        </div>
        <span className="text-xs font-mono text-muted-foreground hidden sm:block">
          Showing {filteredBlocks.length} of {ledgerData?.total_blocks || 0} blocks
        </span>
      </div>

      {/* Split View: Block List & Block Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Block List (5 cols) */}
        <div className="lg:col-span-5 panel p-0 overflow-hidden space-y-0">
          <div className="p-3 border-b border-border bg-[#080D1A] flex items-center justify-between">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-muted-foreground">
              Block Sequence
            </span>
            <span className="text-[10px] font-mono text-muted-foreground">Latest to Oldest</span>
          </div>

          <div className="max-h-[550px] overflow-y-auto divide-y divide-border/60 revive-scroll">
            {filteredBlocks.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground">
                No matching audit blocks found.
              </div>
            ) : (
              [...filteredBlocks].reverse().map((b) => {
                const isSelected = selectedBlock?.current_hash === b.current_hash;
                const bNum = getBlockNum(b);
                return (
                  <div
                    key={b.current_hash || bNum}
                    onClick={() => setSelectedBlock(b)}
                    className={`p-3.5 transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-[#0C83FF]/10 border-l-4 border-l-[#0C83FF]'
                        : 'hover:bg-secondary/60'
                    }`}
                    data-testid={`block-item-${bNum}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-white flex items-center gap-1.5">
                        <Hash size={12} className="text-[#0C83FF]" />
                        <span>Block #{bNum}</span>
                      </span>
                      <StatusBadge state={b.resulting_state} size="sm" />
                    </div>

                    <div className="mt-1 flex items-center justify-between text-xs font-mono">
                      <span className="text-[#0C83FF] font-semibold truncate max-w-[180px]">
                        {b.payment_id}
                      </span>
                      <span className="text-muted-foreground text-[11px]">
                        {formatDateTime(b.timestamp)}
                      </span>
                    </div>

                    <div className="mt-1.5 flex items-center justify-between text-[11px] font-mono text-muted-foreground">
                      <span>Action: <strong className="text-white">{b.action_executed}</strong></span>
                      <span className="text-[10px] truncate max-w-[120px]">
                        {b.current_hash.slice(0, 10)}...
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Deep Block Inspector (7 cols) */}
        <div className="lg:col-span-7">
          {!selectedBlock ? (
            <div className="panel p-12 text-center text-xs text-muted-foreground">
              Select a block on the left to inspect its cryptographic payload.
            </div>
          ) : (
            <div className="panel space-y-4 revive-enter">
              <div className="flex items-start justify-between pb-3 border-b border-border">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="eyebrow text-[#0C83FF]">Block #{getBlockNum(selectedBlock)}</span>
                    <span className="text-muted-foreground text-xs">·</span>
                    <span className="text-xs font-mono text-muted-foreground">
                      {formatDateTime(selectedBlock.timestamp)}
                    </span>
                  </div>
                  <h2 className="text-base font-bold text-white mt-1 flex items-center gap-2">
                    <span>Payment:</span>
                    <span className="font-mono text-[#0C83FF]">{selectedBlock.payment_id}</span>
                  </h2>
                </div>

                {onSelectCase && (
                  <button
                    onClick={() => onSelectCase(selectedBlock.payment_id)}
                    className="revive-button revive-button-primary text-xs"
                    data-testid="button-inspect-workspace"
                  >
                    <span>Inspect in Workspace</span>
                    <ArrowUpRight size={12} />
                  </button>
                )}
              </div>

              {/* Hashes Section */}
              <div className="p-3 rounded-lg bg-[#080D1A] border border-border space-y-2 text-xs font-mono">
                <div>
                  <span className="text-muted-foreground text-[10px] uppercase font-bold block">
                    Current Block SHA-256 Hash
                  </span>
                  <span className="text-[#10B981] font-semibold break-all text-[11px]">
                    {selectedBlock.current_hash}
                  </span>
                </div>
                <div className="pt-2 border-t border-border/60">
                  <span className="text-muted-foreground text-[10px] uppercase font-bold block">
                    Previous Block Hash (Linked Anchor)
                  </span>
                  <span className="text-muted-foreground break-all text-[11px]">
                    {selectedBlock.previous_hash}
                  </span>
                </div>
                {selectedBlock.telemetry_hash && (
                  <div className="pt-2 border-t border-border/60">
                    <span className="text-muted-foreground text-[10px] uppercase font-bold block">
                      Telemetry Payload SHA-256
                    </span>
                    <span className="text-white break-all text-[11px]">
                      {selectedBlock.telemetry_hash}
                    </span>
                  </div>
                )}
              </div>

              {/* Execution Summary */}
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-[#080D1A] border border-border">
                  <span className="text-muted-foreground text-[10px] font-mono uppercase block">
                    Action Executed
                  </span>
                  <strong className="text-white text-xs block mt-1 font-mono">
                    {selectedBlock.action_executed}
                  </strong>
                </div>

                <div className="p-3 rounded-lg bg-[#080D1A] border border-border">
                  <span className="text-muted-foreground text-[10px] font-mono uppercase block">
                    Resulting State
                  </span>
                  <div className="mt-1">
                    <StatusBadge state={selectedBlock.resulting_state} size="sm" />
                  </div>
                </div>
              </div>

              {/* AI Reasoning Snapshot */}
              {selectedBlock.ai_reasoning && (
                <div className="p-3 rounded-lg bg-[#080D1A] border border-[#8B5CF6]/30 space-y-2 text-xs">
                  <div className="flex items-center justify-between text-[#8B5CF6] font-mono font-bold text-[11px]">
                    <span className="flex items-center gap-1.5">
                      <Cpu size={13} />
                      <span>Gemini Reasoner Audit Snapshot</span>
                    </span>
                    <span>Confidence: {((selectedBlock.ai_reasoning.confidence || 0.95) * 100).toFixed(0)}%</span>
                  </div>
                  <p className="text-muted-foreground font-mono text-[11px] leading-relaxed">
                    {selectedBlock.ai_reasoning.reasoning_audit_text ||
                      selectedBlock.ai_reasoning.action_rationale ||
                      'Semantic interpretation recorded.'}
                  </p>
                </div>
              )}

              {/* Policy Decision Snapshot */}
              {selectedBlock.policy_decision && (
                <div className="p-3 rounded-lg bg-[#080D1A] border border-border space-y-1.5 text-xs">
                  <div className="flex items-center justify-between font-mono font-bold text-[11px]">
                    <span className="text-white flex items-center gap-1.5">
                      <ShieldCheck size={13} className="text-[#10B981]" />
                      <span>Policy Gate Verdict</span>
                    </span>
                    <span className={selectedBlock.policy_decision.is_overridden ? 'text-rose-400' : 'text-[#10B981]'}>
                      {selectedBlock.policy_decision.is_overridden ? 'OVERRIDDEN' : 'APPROVED'}
                    </span>
                  </div>
                  <p className="text-muted-foreground text-[11px]">
                    {selectedBlock.policy_decision.policy_reason}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
