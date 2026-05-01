import { RefreshCw, Play, RotateCcw, Square } from 'lucide-react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { useDashboardStore } from '../../store/useDashboardStore';

export function Header() {
  const desktopStatus = useDashboardStore((state) => state.desktopStatus);
  const product = useDashboardStore((state) => state.product);
  const loading = useDashboardStore((state) => state.loading);
  const lastMessage = useDashboardStore((state) => state.lastMessage);
  const refreshReality = useDashboardStore((state) => state.refreshReality);
  const startProduct = useDashboardStore((state) => state.startProduct);
  const restartProduct = useDashboardStore((state) => state.restartProduct);
  const stopProduct = useDashboardStore((state) => state.stopProduct);
  const healthy = desktopStatus?.services.filter((service) => service.state === 'healthy').length ?? 0;

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-background/95 px-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Badge tone={product?.online ? 'success' : 'warning'}>{product?.online ? 'online data' : 'local first'}</Badge>
          <span className="font-mono text-xs text-muted">services {healthy}/3</span>
          <span className="font-mono text-xs text-muted">v{desktopStatus?.app_version ?? '1.0.0-beta.3'}</span>
        </div>
        <p className="mt-0.5 truncate text-xs text-muted">{lastMessage}</p>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" disabled={loading} onClick={() => void refreshReality()}><RefreshCw className="h-3.5 w-3.5" />Sync</Button>
        <Button size="sm" disabled={loading} onClick={() => void startProduct()}><Play className="h-3.5 w-3.5" />Start</Button>
        <Button variant="secondary" size="sm" disabled={loading} onClick={() => void restartProduct()}><RotateCcw className="h-3.5 w-3.5" />Restart</Button>
        <Button variant="ghost" size="sm" disabled={loading} onClick={() => void stopProduct()}><Square className="h-3.5 w-3.5" />Stop</Button>
      </div>
    </header>
  );
}
