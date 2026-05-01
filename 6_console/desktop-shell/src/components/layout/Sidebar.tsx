import { Activity, Bot, Bug, ChevronLeft, ChevronRight, Gauge, LineChart, Settings, Shield, SlidersHorizontal } from 'lucide-react';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';
import { useDashboardStore, type PageKey } from '../../store/useDashboardStore';
import { copy } from '../../lib/i18n';

const items: Array<{ key: PageKey; labelKey: keyof typeof copy.en.nav; icon: React.ComponentType<{ className?: string }> }> = [
  { key: 'overview', labelKey: 'overview', icon: Gauge },
  { key: 'live-flow', labelKey: 'liveFlow', icon: Activity },
  { key: 'agents', labelKey: 'agents', icon: Bot },
  { key: 'policies', labelKey: 'policies', icon: Shield },
  { key: 'context-debug', labelKey: 'contextDebug', icon: Bug },
  { key: 'savings', labelKey: 'savings', icon: LineChart },
  { key: 'settings', labelKey: 'settings', icon: SlidersHorizontal },
];

export function Sidebar() {
  const language = useDashboardStore((state) => state.language);
  const page = useDashboardStore((state) => state.page);
  const collapsed = useDashboardStore((state) => state.sidebarCollapsed);
  const setPage = useDashboardStore((state) => state.setPage);
  const toggleSidebar = useDashboardStore((state) => state.toggleSidebar);
  const t = copy[language].nav;

  return (
    <aside className={cn('flex h-screen shrink-0 flex-col border-r border-border bg-background transition-all duration-200', collapsed ? 'w-[62px]' : 'w-[228px]')}>
      <div className="flex h-14 items-center gap-2 border-b border-border px-3">
        <div className="grid h-8 w-8 place-items-center rounded-md border border-accent/40 bg-accent/10 text-accent">
          <Settings className="h-4 w-4" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">OmniMemora</p>
            <p className="text-[11px] text-muted">{t.product}</p>
          </div>
        )}
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {items.map((item) => {
          const Icon = item.icon;
          const active = page === item.key;
          return (
            <button
              key={item.key}
              className={cn('flex h-9 w-full items-center gap-2 rounded-md px-2 text-sm transition', active ? 'bg-panel text-foreground shadow-focus' : 'text-muted hover:bg-panel/70 hover:text-foreground')}
              onClick={() => setPage(item.key)}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span className="truncate">{t[item.labelKey]}</span>}
            </button>
          );
        })}
      </nav>
      <div className="border-t border-border p-2">
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={toggleSidebar}>
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          {!collapsed && t.collapse}
        </Button>
      </div>
    </aside>
  );
}
