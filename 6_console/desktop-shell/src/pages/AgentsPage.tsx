import { Bot, Activity } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';
import { compactNumber } from '../lib/utils';
import { useDashboardStore, type AgentMode } from '../store/useDashboardStore';

const modes: AgentMode[] = ['Observe', 'Guided', 'Force', 'Off'];

export function AgentsPage() {
  const agents = useDashboardStore((state) => state.agents);
  const desktopAgents = useDashboardStore((state) => state.desktopAgents);
  const setAgentMode = useDashboardStore((state) => state.setAgentMode);

  return (
    <div className="grid grid-cols-[1fr_360px] gap-3 max-xl:grid-cols-1">
      <Card>
        <CardHeader><CardTitle>Agent control surface</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {agents.map((agent) => (
            <div key={agent.id} className="grid grid-cols-[1fr_260px_110px] items-center gap-3 rounded-md border border-border bg-background p-3 max-lg:grid-cols-1">
              <div className="flex min-w-0 items-center gap-3">
                <div className="grid h-8 w-8 place-items-center rounded-md border border-border bg-panel"><Bot className="h-4 w-4 text-accent" /></div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-foreground">{agent.name}</p>
                    <Badge tone={agent.status === 'active' ? 'success' : agent.status === 'idle' ? 'neutral' : 'warning'}>{agent.status}</Badge>
                  </div>
                  <p className="text-xs text-muted">{agent.requests} requests · {compactNumber(agent.savedTokens)} tokens saved · usage {agent.usagePct}%</p>
                </div>
              </div>
              <Tabs value={agent.mode} onValueChange={(value) => setAgentMode(agent.id, value as AgentMode)}>
                <TabsList>
                  {modes.map((mode) => <TabsTrigger key={mode} value={mode}>{mode}</TabsTrigger>)}
                </TabsList>
              </Tabs>
              <Button variant="secondary" size="sm">Details</Button>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader><CardTitle>Desktop scan reality</CardTitle></CardHeader>
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
          {!desktopAgents.length && (
            <div className="rounded-md border border-border bg-background p-3 text-sm text-muted">
              Scan will populate local Claude Code, OpenClaw, and Codex connection candidates.
            </div>
          )}
          <div className="rounded-md border border-border bg-panel p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground"><Activity className="h-4 w-4 text-success" /> Control semantics</div>
            <p className="mt-1 text-xs text-muted">Observe collects evidence. Guided routes approved traffic. Force is explicit high-control mode. Off disables routing.</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
