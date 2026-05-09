import { useEffect } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { ScrollArea } from './components/ui/scroll-area';
import { OverviewPage } from './pages/OverviewPage';
import { LiveFlowPage } from './pages/LiveFlowPage';
import { AgentsPage } from './pages/AgentsPage';
import { PoliciesPage } from './pages/PoliciesPage';
import { ContextDebugPage } from './pages/ContextDebugPage';
import { SavingsPage } from './pages/SavingsPage';
import { SettingsPage } from './pages/SettingsPage';
import { useDashboardStore } from './store/useDashboardStore';
import { pageMeta } from './lib/i18n';

function Page() {
  const page = useDashboardStore((state) => state.page);
  switch (page) {
    case 'live-flow': return <LiveFlowPage />;
    case 'agents': return <AgentsPage />;
    case 'policies': return <PoliciesPage />;
    case 'context-debug': return <ContextDebugPage />;
    case 'savings': return <SavingsPage />;
    case 'settings': return <SettingsPage />;
    default: return <OverviewPage />;
  }
}

export default function App() {
  const page = useDashboardStore((state) => state.page);
  const language = useDashboardStore((state) => state.language);
  const refreshReality = useDashboardStore((state) => state.refreshReality);
  const checkForUpdates = useDashboardStore((state) => state.checkForUpdates);
  const [title, subtitle] = pageMeta[language][page];

  useEffect(() => {
    void refreshReality();
    void checkForUpdates();
  }, [refreshReality, checkForUpdates]);

  return (
    <div className="flex h-screen bg-background text-foreground">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header />
        <ScrollArea className="min-h-0 flex-1 panel-grid">
          <main className="mx-auto w-full max-w-[1680px] p-4">
            <div className="mb-4 flex items-end justify-between gap-4">
              <div>
                <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
                <p className="mt-1 text-sm text-muted">{subtitle}</p>
              </div>
            </div>
            <Page />
          </main>
        </ScrollArea>
      </div>
    </div>
  );
}
