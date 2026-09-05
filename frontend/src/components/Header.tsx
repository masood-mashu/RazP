import React, { useEffect, useState } from 'react';
import { Database, Cpu, RefreshCw, Key, Menu, X, Zap } from 'lucide-react';
import { api, getAuthToken, setAuthToken } from '../api/client';
import type { SystemStatus } from '../api/types';

interface HeaderProps {
  onRefresh?: () => void;
  isRefreshing?: boolean;
  onToggleMobileMenu?: () => void;
  mobileMenuOpen?: boolean;
  onRunDemo?: () => void;
  isDemoRunning?: boolean;
}

const DEMO_ROLES = [
  { label: 'Admin (Root)', key: 'razp_master_admin_demo', roleText: 'ADMIN', color: 'text-blue-400' },
  { label: 'Operator', key: 'razp_op_key_demo', roleText: 'OPERATOR', color: 'text-emerald-400' },
  { label: 'Policy Admin', key: 'razp_admin_key_demo', roleText: 'POLICY_ADMIN', color: 'text-amber-400' },
  { label: 'Auditor', key: 'razp_audit_key_demo', roleText: 'AUDITOR', color: 'text-sky-400' },
];

export const Header: React.FC<HeaderProps> = ({
  onRefresh,
  isRefreshing,
  onToggleMobileMenu,
  mobileMenuOpen = false,
  onRunDemo,
  isDemoRunning,
}) => {
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

  const currentRole = DEMO_ROLES.find((r) => r.key === activeToken) || DEMO_ROLES[0];

  return (
    <header className="h-14 border-b border-border bg-[#080D1A]/95 backdrop-blur-md px-4 lg:px-6 flex items-center justify-between z-30 select-none">
      {/* Left: Mobile Toggle & Brand */}
      <div className="flex items-center gap-3">
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            className="lg:hidden p-1.5 rounded hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors focus:outline-none"
            title={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-label={mobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileMenuOpen}
            data-testid="button-open-mobile-menu"
          >
            {mobileMenuOpen ? <X size={18} className="text-white" /> : <Menu size={18} />}
          </button>
        )}

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#0C83FF]/15 border border-[#0C83FF]/30 flex items-center justify-center text-[#0C83FF]">
            <Zap size={18} className="fill-[#0C83FF]" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-bold tracking-tight text-white">RazP</span>
              <span className="text-xs font-semibold text-[#0C83FF]">Sentinel</span>
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
                v1.0.0
              </span>
            </div>
            <p className="hidden md:block text-[10px] text-muted-foreground leading-tight">
              Razorpay Autonomous Zero-Loss Payment Recovery Engine
            </p>
          </div>
        </div>

        <span className="topbar-divider hidden sm:block mx-1" />

        {/* Health pill */}
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-mono font-medium">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>{status?.status === 'OPERATIONAL' ? 'Systems Operational' : 'Ready'}</span>
        </div>
      </div>

      {/* Right: Environment & Role Switcher */}
      <div className="flex items-center gap-2.5 text-xs font-mono">
        {/* Persistence Indicator */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#0F182A] border border-border text-muted-foreground text-[11px]">
          <Database size={13} className="text-[#0C83FF]" />
          <span className="text-foreground/90 font-medium">PostgreSQL 16</span>
        </div>

        {/* AI Provider Indicator */}
        <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#0F182A] border border-border text-muted-foreground text-[11px]">
          <Cpu size={13} className="text-[#8B5CF6]" />
          <span className="text-foreground/90 font-medium">Gemini 2.5 Flash-Lite</span>
        </div>

        {/* Role Switcher */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#0F182A] border border-border text-[11px]">
          <Key size={12} className="text-muted-foreground" />
          <span className="text-muted-foreground text-[10px] uppercase font-semibold hidden sm:inline">Role:</span>
          <select
            value={activeToken}
            onChange={(e) => handleRoleChange(e.target.value)}
            className={`bg-transparent font-semibold cursor-pointer outline-none border-0 text-[11px] uppercase tracking-wider ${currentRole.color}`}
            title="Switch demo RBAC role token"
            data-testid="select-auth-role"
          >
            {DEMO_ROLES.map((role) => (
              <option key={role.key} value={role.key} className="bg-[#0F182A] text-white font-mono normal-case">
                {role.label}
              </option>
            ))}
          </select>
        </div>

        {/* Run Reviewer Demo Trigger */}
        {onRunDemo && (
          <button
            onClick={onRunDemo}
            disabled={isDemoRunning}
            className="revive-button revive-button-primary hidden sm:inline-flex"
            title="Run End-to-End Multi-Event Recovery Demo"
            data-testid="button-header-demo"
          >
            <Zap size={13} className={isDemoRunning ? 'animate-spin' : 'fill-white'} />
            <span>{isDemoRunning ? 'Simulating...' : 'Run Demo'}</span>
          </button>
        )}

        {/* Global Refresh */}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="p-1.5 rounded-md bg-[#0F182A] hover:bg-secondary border border-border text-muted-foreground hover:text-foreground transition-all disabled:opacity-50"
            title="Refresh dashboard data"
            data-testid="button-refresh-global"
          >
            <RefreshCw size={14} className={isRefreshing ? 'animate-spin text-[#0C83FF]' : ''} />
          </button>
        )}
      </div>
    </header>
  );
};
