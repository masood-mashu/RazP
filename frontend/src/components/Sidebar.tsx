import React from 'react';
import {
  LayoutDashboard,
  Inbox,
  FileSpreadsheet,
  SlidersHorizontal,
  BarChart3,
  FileClock,
  ShieldCheck,
  ChevronRight
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
    { id: 'command-center' as TabType, label: 'Command Center', icon: LayoutDashboard },
    { id: 'queue' as TabType, label: 'Recovery Queue', icon: Inbox },
    { id: 'workspace' as TabType, label: 'Case Workspace', icon: FileSpreadsheet, badge: activeCaseId ? 'Active' : null },
  ];

  const assuranceNav = [
    { id: 'ledger' as TabType, label: 'Cryptographic Ledger', icon: FileClock, badge: 'SHA-256' },
    { id: 'policy' as TabType, label: 'Policy Engine', icon: SlidersHorizontal },
    { id: 'benchmark' as TabType, label: 'Evaluation & Ablation', icon: BarChart3, badge: '68 Cases' },
  ];

  const handleNavClick = (tab: TabType) => {
    onSelectTab(tab);
    if (onCloseMobile) onCloseMobile();
  };

  return (
    <aside
      className={`fixed lg:static inset-y-0 left-0 z-40 w-64 flex flex-col bg-[#080D1A] text-sidebar-foreground border-r border-border transition-transform duration-200 ${
        mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      }`}
    >
      {/* Navigation Links */}
      <div className="flex-1 overflow-y-auto px-3.5 py-4 space-y-6 revive-scroll">
        {/* Operations Section */}
        <div>
          <div className="px-3 pb-2 text-[10px] font-mono font-bold tracking-wider text-muted-foreground uppercase flex items-center justify-between">
            <span>Recovery Operations</span>
          </div>
          <nav className="space-y-1">
            {operationsNav.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  data-testid={`link-${item.id}`}
                  className={`w-full group flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-[#0C83FF]/15 text-white font-semibold border border-[#0C83FF]/30 shadow-sm'
                      : 'text-muted-foreground hover:text-white hover:bg-secondary/60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      size={16}
                      className={isActive ? 'text-[#0C83FF]' : 'text-muted-foreground group-hover:text-white'}
                    />
                    <span>{item.label}</span>
                  </div>
                  {item.badge ? (
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-blue-500/20 text-[#0C83FF] font-semibold">
                      {item.badge}
                    </span>
                  ) : isActive ? (
                    <ChevronRight size={14} className="text-[#0C83FF]" />
                  ) : null}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Governance & Assurance Section */}
        <div>
          <div className="px-3 pb-2 text-[10px] font-mono font-bold tracking-wider text-muted-foreground uppercase flex items-center justify-between">
            <span>Governance & Verification</span>
          </div>
          <nav className="space-y-1">
            {assuranceNav.map((item) => {
              const Icon = item.icon;
              const isActive = currentTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  data-testid={`link-${item.id}`}
                  className={`w-full group flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? 'bg-[#0C83FF]/15 text-white font-semibold border border-[#0C83FF]/30 shadow-sm'
                      : 'text-muted-foreground hover:text-white hover:bg-secondary/60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      size={16}
                      className={isActive ? 'text-[#0C83FF]' : 'text-muted-foreground group-hover:text-white'}
                    />
                    <span>{item.label}</span>
                  </div>
                  {item.badge ? (
                    <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-secondary text-muted-foreground border border-border">
                      {item.badge}
                    </span>
                  ) : isActive ? (
                    <ChevronRight size={14} className="text-[#0C83FF]" />
                  ) : null}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Invariant Footer Badge */}
      <div className="p-3.5 border-t border-border bg-[#0B1222]/60">
        <div className="p-3 rounded-lg border border-border/80 bg-[#0E172A] space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-white">
            <ShieldCheck size={14} className="text-[#10B981]" />
            <span>Deterministic Spine</span>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Zero AI financial authority. State transitions, quiet hours, and idempotency enforced deterministically.
          </p>
        </div>
      </div>
    </aside>
  );
};
