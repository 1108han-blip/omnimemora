import { Activity, Bot } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { compactNumber, percent } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';

export function AgentsPage() {
  const language = useDashboardStore((state) => state.language);
  const product = useDashboardStore((state) => state.product);
  const desktopAgents = useDashboardStore((state) => state.desktopAgents);
  const agentBusy = useDashboardStore((state) => state.agentBusy);
  const attachAgent = useDashboardStore((state) => state.attachAgent);
  const detachAgent = useDashboardStore((state) => state.detachAgent);
  const enableRouting = useDashboardStore((state) => state.enableRouting);
  const disableRouting = useDashboardStore((state) => state.disableRouting);
  const t = copy[language].agents;
  const cards = product?.controls?.agents ?? [];

  return (
    <div className="grid grid-cols-[1fr_360px] gap-3 max-xl:grid-cols-1">
      <Card>
        <CardHeader><CardTitle>{t.title}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {!cards.length && <div className="rounded-md border border-border bg-background p-3 text-sm text-muted">{t.empty}</div>}
          {cards.map((agent) => {
            const busy = agentBusy === agent.family_id;
            const canRoute = agent.installed && agent.health_state === 'healthy';
            return (
              <div key={agent.family_id} className="grid grid-cols-[1fr_180px_230px] items-center gap-3 rounded-md border border-border bg-background p-3 max-xl:grid-cols-1">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="grid h-8 w-8 place-items-center rounded-md border border-border bg-panel"><Bot className="h-4 w-4 text-accent" /></div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-foreground">{agent.display_name}</p>
                      <Badge tone={agent.installed ? 'success' : 'neutral'}>{agent.installed ? t.attached : t.detached}</Badge>
                      <Badge tone={agent.routing_enabled ? 'accent' : 'neutral'}>{agent.routing_enabled ? t.routeOn : t.routeDisabled}</Badge>
                    </div>
                    <p className="text-xs text-muted">
                      {compactNumber(agent.requests_24h ?? agent.observed_requests_24h)} {t.requests} · {compactNumber(agent.saved_tokens_24h)} {t.saved} · {percent(agent.savings_ratio_24h)}
                    </p>
                    {!canRoute && <p className="mt-1 text-xs text-warning">{t.blocked}</p>}
                  </div>
                </div>
                <div className="text-xs text-muted">
                  <div>{agent.integration_truth ?? 'detached'}</div>
                  <div>{agent.route_truth ?? 'off'} · {agent.traffic_truth ?? 'no_recent_evidence'}</div>
                </div>
                <div className="flex flex-wrap justify-end gap-2 max-xl:justify-start">
                  <Button size="sm" variant="secondary" disabled={busy || agent.installed} onClick={() => void attachAgent(agent.family_id)}>{t.attach}</Button>
                  <Button size="sm" variant="ghost" disabled={busy || !agent.installed} onClick={() => void detachAgent(agent.family_id)}>{t.detach}</Button>
                  <Button size="sm" disabled={busy || !canRoute || agent.routing_enabled} onClick={() => void enableRouting(agent.family_id)}>{t.enable}</Button>
                  <Button size="sm" variant="secondary" disabled={busy || !agent.routing_enabled} onClick={() => void disableRouting(agent.family_id)}>{t.disable}</Button>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>{t.scan}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {desktopAgents.map((agent) => (
            <div key={agent.id} className="rounded-md border border-border bg-background p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="font-medium text-foreground">{agent.name}</p>
                <Badge tone={agent.attached ? 'success' : agent.installed || agent.running ? 'accent' : 'neutral'}>{agent.state.replace('_', ' ')}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted">{agent.detail}</p>
            </div>
          ))}
          {!desktopAgents.length && <div className="rounded-md border border-border bg-background p-3 text-sm text-muted">{t.empty}</div>}
          <div className="rounded-md border border-border bg-panel p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground"><Activity className="h-4 w-4 text-success" /> {t.semantics}</div>
            <p className="mt-1 text-xs text-muted">{t.semanticsText}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
