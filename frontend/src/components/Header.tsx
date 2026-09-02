import React, { useEffect, useState } from 'react';
import { Database, Cpu, RefreshCw, Key, Menu } from 'lucide-react';
import { api, getAuthToken, setAuthToken } from '../api/client';
import type { SystemStatus } from '../api/types';

interface HeaderProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
  onToggleMobileMenu?: () => void;
}

const DEMO_ROLES = [
  { label: 'Admin (Root)', key: 'razp_master_admin_demo', roleText: 'ADMIN', color: 'text-amber-400' },
  { label: 'Operator', key: 'razp_op_key_demo', roleText: 'OPERATOR', color: 'text-emerald-400' },
  { label: 'Policy Admin', key: 'razp_admin_key_demo', roleText: 'POLICY_ADMIN', color: 'text-purple-400' },
  { label: 'Auditor', key: 'razp_audit_key_demo', roleText: 'AUDITOR', color: 'text-sky-400' },
];

export const Header: React.FC<HeaderProps> = ({ onRefresh, isRefreshing, onToggleMobileMenu }) => {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [activeToken, setActiveToken] = useState<string>(getAuthToken());

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await api.getSystemStatus();
        setStatus(res);
      } catch (err) {
        console.error('Failed to fetch system status:', err);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRoleChange = (key: string) => {
    setActiveToken(key);
    setAuthToken(key);
    if (onRefresh) onRefresh();
  };

  const currentRole = DEMO_ROLES.find(r => r.key === activeToken) || DEMO_ROLES[0];

  return (
    <header className="h-14 border-b border-border bg-card/80 backdrop-blur-md px-4 lg:px-6 flex items-center justify-between z-20 select-none">
      {/* Left: Mobile Menu Toggle & Health Indicator */}
      <div className="flex items-center gap-3">
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            className="lg:hidden p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-foreground"
            title="Open navigation menu"
            data-testid="button-open-mobile-menu"
          >
            <Menu size={18} />
          </button>
        )}

        <div className="flex items-center gap-2 health-mark" data-testid="button-check-health">
          <span className="health-dot" />
          <span className="text-[11px] font-mono text-muted-foreground font-medium">
            {status?.status === 'OPERATIONAL' ? 'Systems operational' : 'System standby'}
          </span>
        </div>

        <span className="topbar-divider hidden sm:block" />

        <span className="hidden sm:inline-block text-[11px] text-muted-foreground/80 font-medium">
          Autonomous Recovery Engine · INR Autopay
        </span>
      </div>

      {/* Right: Telemetry Badges, Role Switcher & Refresh */}
      <div className="flex items-center gap-2 text-xs font-mono">
        {/* Persistence Indicator */}
        <div className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded bg-secondary/60 border border-border text-muted-foreground text-[10px]">
          <Database size={12} className="text-primary" />
          <span>{status?.persistence_layer === 'POSTGRESQL_DURABLE' ? 'PostgreSQL 16' : 'In-Memory Fallback'}</span>
        </div>

        {/* AI Provider Indicator */}
        <div className="hidden md:flex items-center gap-1.5 px-2 py-1 rounded bg-secondary/60 border border-border text-muted-foreground text-[10px]">
          <Cpu size={12} className="text-accent" />
          <span>{status?.is_live_gemini ? `Live ${status.model}` : 'Deterministic Engine'}</span>
        </div>

        {/* Role Switcher */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-secondary border border-border text-[11px]">
          <Key size={12} className="text-muted-foreground" />
          <select
            value={activeToken}
            onChange={(e) => handleRoleChange(e.target.value)}
            className={`bg-transparent font-semibold cursor-pointer outline-none border-0 text-[10px] uppercase tracking-wide ${currentRole.color}`}
            title="Switch demo RBAC role token"
            data-testid="select-auth-role"
          >
            {DEMO_ROLES.map((role) => (
              <option key={role.key} value={role.key} className="bg-card text-foreground font-mono normal-case">
                {role.label}
              </option>
            ))}
          </select>
        </div>

        {/* Refresh button */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-1.5 rounded bg-secondary hover:bg-secondary/80 border border-border text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            title="Refresh dashboard data"
            data-testid="button-refresh-global"
          >
            <RefreshCw size={13} className={isRefreshing ? 'animate-spin text-primary' : ''} />
          </button>
        )}
      </div>
    </header>
  );
};
