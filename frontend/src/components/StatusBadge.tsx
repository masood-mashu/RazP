import React from 'react';
import type { PaymentState } from '../api/types';

interface StatusBadgeProps {
  state: PaymentState | string;
  size?: 'sm' | 'md';
}

const statusClassMap: Record<string, string> = {
  RECOVERED: 'status-recovered',
  PAUSE_RECON_VERIFY: 'status-waiting',
  DEDUCTION_SUSPECTED: 'status-waiting',
  PTP_SCHEDULED: 'status-ptp_scheduled',
  RETRY_SCHEDULED: 'status-retry_scheduled',
  AWAITING_CUSTOMER_ACTION: 'status-needs_action',
  TELEMETRY_ANALYSIS: 'status-active',
  POLICY_GATED: 'status-active',
  ESCALATED_HUMAN_OPS: 'status-escalated',
  DEAD_LETTER: 'status-stopped',
  PAYMENT_FAILED: 'status-payment_failed',
  REVOKED_TERMINAL: 'status-stopped',
  FAILED_TERMINAL: 'status-stopped',
  DISPUTE_LOCKED: 'status-waiting',
};

const statusLabelMap: Record<string, string> = {
  RECOVERED: 'Recovered',
  PAUSE_RECON_VERIFY: 'Recon verify',
  DEDUCTION_SUSPECTED: 'Deduction hold',
  PTP_SCHEDULED: 'PTP scheduled',
  RETRY_SCHEDULED: 'Retry queued',
  AWAITING_CUSTOMER_ACTION: 'Needs action',
  TELEMETRY_ANALYSIS: 'Analyzing',
  POLICY_GATED: 'Policy gated',
  ESCALATED_HUMAN_OPS: 'Human escalation',
  DEAD_LETTER: 'Stopped',
  PAYMENT_FAILED: 'Failed',
  REVOKED_TERMINAL: 'Mandate revoked',
  FAILED_TERMINAL: 'Terminal fail',
  DISPUTE_LOCKED: 'Dispute locked',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({ state, size = 'sm' }) => {
  const className = statusClassMap[state] || 'status-active';
  const label = statusLabelMap[state] || state.replace(/_/g, ' ');

  return (
    <span
      data-testid={`status-${state.toLowerCase()}`}
      className={`status-badge ${className} ${size === 'md' ? 'text-[10px] px-2 py-1' : 'text-[9px] px-1.5 py-0.5'}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      <span>{label}</span>
    </span>
  );
};
