import { Activity, Bot, Bug, ChevronLeft, ChevronRight, Gauge, LineChart, Settings, Shield, SlidersHorizontal } from 'lucide-react';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';
import { useDashboardStore, type PageKey } from '../../store/useDashboardStore';

const items: Array<{ key: PageKey; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { key: 'overview', label: 'Overview', icon: Gauge },
  { key: 'live-flow', label: 'Live Flow', icon: Activity },
  { key: 'agents', label: 'Agents', icon: Bot },
  { key: 'policies', label: 'Policies', icon: Shield },
  { key: 'context-debug', label: 'Context Debug', icon: Bug },
  { key: 'savings', label: 'Savings', icon: LineChart },
  { key: 'settings', label: 'Settings', icon: SlidersHorizontal },
];

export function Sidebar() {
  const page = useDashboardStore((state) => state.page);
  const collapsed = useDashboardStore((state) => state.sidebarCollapsed);
  const setPage = useDashboardStore((state) => state.setPage);
  const toggleSidebar = useDashboardStore((state) => state.toggleSidebar);

  return (
    <aside className={cn('flex h-screen shrink-0 flex-col border-r border-border bg-background transition-all duration-200', collapsed ? 'w-[62px]' : 'w-[228px]')}>
      <div className="flex h-14 items-center gap-2 border-b border-border px-3">
        <div className="grid h-8 w-8 place-items-center rounded-md border border-accent/40 bg-accent/10 text-accent">
          <Settings className="h-4 w-4" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-foreground">OmniMemora</p>
            <p className="text-[11px] text-muted">Memory Control Plane</p>
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
              {!collapsed && <span className="truncate">{item.label}</span>}
            </button>
          );
        })}
      </nav>
      <div className="border-t border-border p-2">
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={toggleSidebar}>
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          {!collapsed && 'Collapse'}
        </Button>
      </div>
    </aside>
  );
}
