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

const titles = {
  overview: ['Overview', 'Operational value, product path health, and agent usage.'],
  'live-flow': ['Live Flow', 'Real-time request stream with compiled/bypass/fallback evidence.'],
  agents: ['Agents', 'Control every AI tool connection without terminal setup.'],
  policies: ['Policies', 'Candidate policy editing with explicit promotion boundaries.'],
  'context-debug': ['Context Debug', 'Compile simulation, packed context, token diff.'],
  savings: ['Savings', 'Token and cost savings over time.'],
  settings: ['Settings', 'Local service orchestration, update state, and feedback.'],
} as const;

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
  const refreshReality = useDashboardStore((state) => state.refreshReality);
  const tickMock = useDashboardStore((state) => state.tickMock);
  const [title, subtitle] = titles[page];

  useEffect(() => {
    void refreshReality();
    const realityTimer = window.setInterval(() => void refreshReality(), 8000);
    const mockTimer = window.setInterval(() => tickMock(), 3500);
    return () => {
      window.clearInterval(realityTimer);
      window.clearInterval(mockTimer);
    };
  }, [refreshReality, tickMock]);

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
