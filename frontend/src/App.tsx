import React, { useState } from 'react';
import { Header } from './components/Header';
import { Sidebar, TabType } from './components/Sidebar';
import { CommandCenter } from './pages/CommandCenter';
import { RecoveryQueue } from './pages/RecoveryQueue';
import { CaseWorkspace } from './pages/CaseWorkspace';
import { AuditLedgerPage } from './pages/AuditLedgerPage';
import { PolicyPage } from './pages/PolicyPage';
import { BenchmarkPage } from './pages/BenchmarkPage';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabType>('command-center');
  const [activePaymentId, setActivePaymentId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [refreshKey, setRefreshKey] = useState<number>(0);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState<boolean>(false);

  const handleSelectCase = (paymentId: string) => {
    setActivePaymentId(paymentId);
    setCurrentTab('workspace');
    setMobileSidebarOpen(false);
  };

  const handleGlobalRefresh = () => {
    setIsRefreshing(true);
    setRefreshKey((prev) => prev + 1);
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const renderContent = () => {
    switch (currentTab) {
      case 'command-center':
        return <CommandCenter key={refreshKey} onSelectCase={handleSelectCase} onNavigate={setCurrentTab} />;
      case 'queue':
        return <RecoveryQueue key={refreshKey} onSelectCase={handleSelectCase} />;
      case 'workspace':
        return (
          <CaseWorkspace
            key={refreshKey}
            initialPaymentId={activePaymentId}
            onClearCase={() => setActivePaymentId(null)}
            onNavigateToLedger={() => setCurrentTab('ledger')}
          />
        );
      case 'ledger':
        return <AuditLedgerPage key={refreshKey} onSelectCase={handleSelectCase} />;
      case 'policy':
        return <PolicyPage key={refreshKey} />;
      case 'benchmark':
        return <BenchmarkPage key={refreshKey} />;
      default:
        return <CommandCenter key={refreshKey} onSelectCase={handleSelectCase} onNavigate={setCurrentTab} />;
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-[#070B14] text-foreground overflow-hidden">
      <Header
        onRefresh={handleGlobalRefresh}
        isRefreshing={isRefreshing}
        onToggleMobileMenu={() => setMobileSidebarOpen((prev) => !prev)}
        mobileMenuOpen={mobileSidebarOpen}
      />
      <div className="flex-1 flex overflow-hidden relative">
        {/* Mobile Backdrop - strictly below Sidebar (z-40) */}
        {mobileSidebarOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm lg:hidden transition-opacity duration-200"
            onClick={() => setMobileSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
        <Sidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          activeCaseId={activePaymentId}
          mobileOpen={mobileSidebarOpen}
          onCloseMobile={() => setMobileSidebarOpen(false)}
        />
        <main className="flex-1 overflow-hidden bg-[#070B14]">
          {renderContent()}
        </main>
      </div>
    </div>
  );
};

export default App;
