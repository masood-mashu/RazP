import React from 'react';
import {
  LayoutDashboard,
  Zap,
  FileSpreadsheet,
  SlidersHorizontal,
  BarChart3,
  FileClock,
  ShieldCheck,
  UserCheck
} from 'lucide-react';

export type TabType =
  | 'command-center'
  | 'queue'
  | 'workspace'
  | 'ledger'
  | 'policy'
  | 'benchmark';

interface SidebarProps {
  currentTab: TabType;
  onSelectTab: (tab: TabType) => void;
  activeCaseId?: string | null;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentTab,
  onSelectTab,
  activeCaseId,
  mobileOpen = false,
  onCloseMobile
}) => {
  const operationsNav = [
    { id: 'command-center' as TabType, label: 'Command Center', icon: LayoutDashboard, badge: null },
    { id: 'queue' as TabType, label: 'Recovery Queue', icon: Zap, badge: null },
    { id: 'workspace' as TabType, label: 'Case Workspace', icon: FileSpreadsheet, badge: activeCaseId ? 'Active' : null },
  ];

  const assuranceNav = [
    { id: 'ledger' as TabType, label: 'Cryptographic Ledger', icon: FileClock, badge: 'SHA-256' },
    { id: 'policy' as TabType, label: 'Policy Engine', icon: SlidersHorizontal, badge: 'TRAI Guard' },
    { id: 'benchmark' as TabType, label: 'Evaluation & Ablation', icon: BarChart3, badge: '6-Way' },
  ];

  const handleNavClick = (tab: TabType) => {
    onSelectTab(tab);
    if (onCloseMobile) onCloseMobile();
  };

  return (
    <aside
      className={`fixed lg:static inset-y-0 left-0 z-50 w-60 flex flex-col bg-sidebar text-sidebar-foreground border-r border-sidebar-border transition-transform duration-200 ${
        mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      }`}
    >
      {/* Brand Header */}
      <div className="h-14 px-5 flex items-center justify-between border-b border-sidebar-border/80">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-full border border-primary/60 flex items-center justify-center bg-primary/10">
            <div className="w-2.5 h-2.5 rounded-full bg-primary" />
          </div>
          <div>
            <span className="text-sm font-bold tracking-tight text-white uppercase">RazP Sentinel</span>
            <span className="ml-1.5 text-[9px] font-mono px-1 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
              TRK-3
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-5 revive-scroll">
        {/* Operations Section */}
        <div>
          <p className="eyebrow px-3 text-[8px] text-muted-foreground/70">Operations</p>
          <nav className="mt-2 space-y-1">
            {operationsNav.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  data-testid={`link-${item.id}`}
                  className={`w-full relative flex items-center justify-between px-3 py-2 rounded text-xs font-semibold transition-colors ${
                    isActive
                      ? 'bg-sidebar-accent text-white font-bold'
                      : 'text-sidebar-foreground/65 hover:text-white hover:bg-sidebar-accent/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon size={15} strokeWidth={isActive ? 2.2 : 1.8} className={isActive ? 'text-primary' : 'text-muted-foreground'} />
                    <span>{item.label}</span>
                  </div>
                  {isActive && <span className="w-1.5 h-1.5 rounded-full bg-primary" />}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Assurance & Governance Section */}
        <div>
          <p className="eyebrow px-3 text-[8px] text-muted-foreground/70">Decision Science</p>
          <nav className="mt-2 space-y-1">
            {assuranceNav.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  data-testid={`link-${item.id}`}
                  className={`w-full relative flex items-center justify-between px-3 py-2 rounded text-xs font-semibold transition-colors ${
                    isActive
                      ? 'bg-sidebar-accent text-white font-bold'
                      : 'text-sidebar-foreground/65 hover:text-white hover:bg-sidebar-accent/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon size={15} strokeWidth={isActive ? 2.2 : 1.8} className={isActive ? 'text-primary' : 'text-muted-foreground'} />
                    <span>{item.label}</span>
                  </div>
                  {isActive ? (
                    <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                  ) : item.badge ? (
                    <span className="text-[8px] font-mono px-1 py-0.2 rounded bg-secondary/80 text-muted-foreground border border-border/50">
                      {item.badge}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Decision Layer Card & Operator Profile */}
      <div className="p-3 border-t border-sidebar-border/80 space-y-3">
        <div className="p-3 rounded border border-sidebar-border bg-sidebar-accent/40 text-[11px] leading-relaxed text-sidebar-foreground/70">
          <div className="flex items-center justify-between font-mono text-[9px] uppercase tracking-wider text-sidebar-foreground/50">
            <span>Decision layer</span>
            <ShieldCheck size={14} className="text-primary" />
          </div>
          <p className="mt-1.5 text-[11px] text-muted-foreground">
            Zero AI financial authority. Every mutation is gated by deterministic policy & cryptographic audit.
          </p>
        </div>

        <div className="flex items-center gap-2.5 px-2 py-1 text-xs text-sidebar-foreground/80">
          <div className="avatar avatar-small">
            <UserCheck size={13} className="text-primary" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[11px] font-bold text-foreground">Razorpay Sentinel Ops</p>
            <p className="truncate text-[10px] text-muted-foreground font-mono">Autonomous Node</p>
          </div>
        </div>
      </div>
    </aside>
  );
};
