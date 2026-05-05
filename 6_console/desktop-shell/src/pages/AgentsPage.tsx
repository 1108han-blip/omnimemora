import { Activity, Bot } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { compactNumber, percent } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';
import type { AgentControlCard, AgentStatus } from '../types';

const DESKTOP_TO_PRODUCT_FAMILY: Record<string, string> = {
  claude: 'claude_code',
  openclaw: 'openclaw',
  codex: 'codex_cli',
};

function productFamilyId(agent: AgentStatus): string {
  return DESKTOP_TO_PRODUCT_FAMILY[agent.id] ?? agent.id;
}

function productCardFor(agent: AgentStatus, cards: AgentControlCard[]): AgentControlCard | undefined {
  const familyId = productFamilyId(agent);
  return cards.find((card) => card.family_id === familyId);
}

function scanLabel(agent: AgentStatus, t: typeof copy.en.agents | typeof copy.zh.agents): string {
  if (agent.attached) return t.scanAttached;
  if (agent.running) return t.scanRunning;
  if (agent.installed) return t.scanFound;
  if (agent.state === 'not_found') return t.scanNotFound;
  return t.scanUnknown;
}

function scanDetail(agent: AgentStatus, t: typeof copy.en.agents | typeof copy.zh.agents): string {
  if (agent.attached) return t.scanDetailAttached;
  if (agent.installed || agent.running) return t.scanDetailFound;
  return t.scanDetailMissing;
}

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
              <div key={agent.family_id} className="grid grid-cols-[1fr_250px] items-center gap-3 rounded-md border border-border bg-background p-3 max-xl:grid-cols-1">
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
                <div className="grid grid-cols-2 gap-2 max-xl:max-w-[320px]">
                  {agent.installed ? (
                    <Button size="sm" variant="ghost" disabled={busy} onClick={() => void detachAgent(agent.family_id)}>{t.detach}</Button>
                  ) : (
                    <Button size="sm" variant="secondary" disabled={busy || !agent.detected} onClick={() => void attachAgent(agent.family_id)}>{t.attach}</Button>
                  )}
                  {agent.routing_enabled ? (
                    <Button size="sm" variant="secondary" disabled={busy} onClick={() => void disableRouting(agent.family_id)}>{t.disable}</Button>
                  ) : (
                    <Button size="sm" disabled={busy || !canRoute} onClick={() => void enableRouting(agent.family_id)}>{t.enable}</Button>
                  )}
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
            (() => {
              const card = productCardFor(agent, cards);
              const familyId = card?.family_id ?? productFamilyId(agent);
              const attached = card?.installed ?? agent.attached;
              const routingEnabled = card?.routing_enabled ?? false;
              const canAttach = agent.supported && (agent.installed || agent.running || card?.detected);
              const canEnable = attached && (card?.health_state ?? 'healthy') === 'healthy';
              const busy = agentBusy === familyId;
              return (
                <div key={agent.id} className="rounded-md border border-border bg-background p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium text-foreground">{agent.name}</p>
                    <div className="flex flex-wrap justify-end gap-1">
                      <Badge tone={attached ? 'success' : agent.installed || agent.running ? 'accent' : 'neutral'}>{attached ? t.attached : scanLabel(agent, t)}</Badge>
                      <Badge tone={routingEnabled ? 'accent' : 'neutral'}>{routingEnabled ? t.routeOn : t.routeDisabled}</Badge>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-muted">{attached ? t.scanDetailAttached : scanDetail(agent, t)}</p>
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {attached ? (
                      <Button size="sm" variant="ghost" disabled={busy} onClick={() => void detachAgent(familyId)}>{t.detach}</Button>
                    ) : (
                      <Button size="sm" variant="secondary" disabled={busy || !canAttach} onClick={() => void attachAgent(familyId)}>{t.attach}</Button>
                    )}
                    {routingEnabled ? (
                      <Button size="sm" variant="secondary" disabled={busy} onClick={() => void disableRouting(familyId)}>{t.disable}</Button>
                    ) : (
                      <Button size="sm" disabled={busy || !canEnable} onClick={() => void enableRouting(familyId)}>{t.enable}</Button>
                    )}
                  </div>
                </div>
              );
            })()
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
