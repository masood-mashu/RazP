import React, { useEffect, useState } from 'react';
import { Database, Cpu, RefreshCw, Key, Menu, X, Zap, ShieldAlert, LogOut, Check } from 'lucide-react';
import { api, getAuthToken, setAuthToken, clearAuthToken } from '../api/client';
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
  const [showAuthModal, setShowAuthModal] = useState<boolean>(false);
  const [customKeyInput, setCustomKeyInput] = useState<string>('');

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

  const handleApplyToken = (key: string) => {
    setActiveToken(key);
    setAuthToken(key);
    setShowAuthModal(false);
    if (onRefresh) onRefresh();
  };

  const handleClearToken = () => {
    clearAuthToken();
    setActiveToken('');
    setShowAuthModal(false);
    if (onRefresh) onRefresh();
  };

  const matchedDemoRole = DEMO_ROLES.find((r) => r.key === activeToken);
  const isCustomKey = Boolean(activeToken && !matchedDemoRole);

  return (
    <>
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
                  v1.3.0
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
            <span className="text-foreground/90 font-medium">
              {status?.persistence_layer === 'POSTGRESQL_DURABLE' ? 'PostgreSQL Durable' : 'In-Memory Engine'}
            </span>
          </div>

          {/* AI Provider Indicator */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#0F182A] border border-border text-muted-foreground text-[11px]">
            <Cpu size={13} className="text-[#8B5CF6]" />
            <span className="text-foreground/90 font-medium">
              {status?.model || 'Gemini Flash-Lite'}
            </span>
          </div>

          {/* Auth / Key Badge Trigger */}
          <button
            onClick={() => setShowAuthModal(true)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] transition-all ${
              !activeToken
                ? 'bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20 animate-pulse'
                : isCustomKey
                ? 'bg-purple-500/10 border-purple-500/30 text-purple-300 hover:bg-purple-500/20'
                : 'bg-[#0F182A] border-border text-foreground/90 hover:bg-secondary'
            }`}
            title="Configure API credentials & authentication role"
            data-testid="button-auth-modal"
          >
            <Key size={12} className={!activeToken ? 'text-amber-400' : 'text-[#0C83FF]'} />
            <span className="font-semibold">
              {!activeToken
                ? 'Set API Key'
                : isCustomKey
                ? `Key: ${activeToken.slice(0, 6)}...`
                : matchedDemoRole?.label}
            </span>
          </button>

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

      {/* Explicit Authentication / Token Configuration Modal */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-[#0D1527] border border-border rounded-xl shadow-2xl max-w-md w-full p-6 space-y-5 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-lg bg-[#0C83FF]/15 text-[#0C83FF]">
                  <Key size={18} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">API Authentication</h3>
                  <p className="text-[11px] text-muted-foreground">Configure your RazP token or select a demo role</p>
                </div>
              </div>
              <button
                onClick={() => setShowAuthModal(false)}
                className="text-muted-foreground hover:text-white p-1 rounded-md"
              >
                <X size={18} />
              </button>
            </div>

            {/* Custom Key Entry */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 block">
                Custom API Key / Bearer Token
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  placeholder="Paste production or operator API key..."
                  value={customKeyInput}
                  onChange={(e) => setCustomKeyInput(e.target.value)}
                  className="flex-1 bg-[#080D1A] border border-border rounded-md px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-[#0C83FF]"
                />
                <button
                  onClick={() => {
                    if (customKeyInput.trim()) {
                      handleApplyToken(customKeyInput.trim());
                      setCustomKeyInput('');
                    }
                  }}
                  disabled={!customKeyInput.trim()}
                  className="px-3 py-1.5 rounded-md bg-[#0C83FF] hover:bg-[#0C83FF]/90 text-white text-xs font-medium transition-all disabled:opacity-40"
                >
                  Apply
                </button>
              </div>
            </div>

            {/* Demo Presets (Visible in non-production) */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-400">
                  Development Demo Presets
                </label>
                <span className="text-[10px] text-muted-foreground">RBAC Profiles</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {DEMO_ROLES.map((role) => (
                  <button
                    key={role.key}
                    onClick={() => handleApplyToken(role.key)}
                    className={`flex items-center justify-between p-2.5 rounded-lg border text-left text-xs transition-all ${
                      activeToken === role.key
                        ? 'bg-[#0C83FF]/15 border-[#0C83FF] text-white'
                        : 'bg-[#080D1A] border-border text-slate-300 hover:border-slate-600'
                    }`}
                  >
                    <div>
                      <div className="font-semibold">{role.label}</div>
                      <div className={`text-[10px] font-mono ${role.color}`}>{role.roleText}</div>
                    </div>
                    {activeToken === role.key && <Check size={14} className="text-[#0C83FF]" />}
                  </button>
                ))}
              </div>
            </div>

            {/* Current Active Status & Clear */}
            <div className="pt-3 border-t border-border flex items-center justify-between text-xs">
              <div className="text-muted-foreground text-[11px]">
                {activeToken ? (
                  <span>Active Token: <code className="text-white font-mono">{activeToken.slice(0, 10)}...</code></span>
                ) : (
                  <span className="text-amber-400 flex items-center gap-1 font-medium">
                    <ShieldAlert size={12} /> Currently Unauthenticated
                  </span>
                )}
              </div>
              {activeToken && (
                <button
                  onClick={handleClearToken}
                  className="flex items-center gap-1 text-red-400 hover:text-red-300 text-xs font-medium py-1 px-2 rounded hover:bg-red-500/10 transition-all"
                >
                  <LogOut size={12} /> Disconnect
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
