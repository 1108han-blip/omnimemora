import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { PathTrafficLights } from '../components/panels/PathTrafficLights';
import { compactNumber, timeShort } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';

function tone(decision: string) {
  if (decision === 'COMPILED') return 'success';
  if (decision === 'FALLBACK') return 'warning';
  return 'neutral';
}

export function LiveFlowPage() {
  const flow = useDashboardStore((state) => state.flow);
  const [expanded, setExpanded] = useState<string | null>(flow[0]?.id ?? null);
  const selected = flow.find((event) => event.id === expanded) ?? flow[0];

  return (
    <div className="grid h-[calc(100vh-92px)] grid-cols-[1fr_380px] gap-3 max-2xl:grid-cols-1">
      <Card className="min-h-0">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Real-time request stream</CardTitle>
          <Badge tone="accent">DevTools style</Badge>
        </CardHeader>
        <ScrollArea className="h-[calc(100%-45px)]">
          <Table>
            <THead className="sticky top-0 z-10 bg-surface">
              <TR className="hover:bg-transparent">
                <TH className="w-8" />
                <TH>Time</TH>
                <TH>Agent</TH>
                <TH>Decision</TH>
                <TH className="text-right">Before</TH>
                <TH className="text-right">After</TH>
                <TH className="text-right">Saving</TH>
              </TR>
            </THead>
            <TBody>
              {flow.map((event) => (
                <TR key={event.id} className={expanded === event.id ? 'bg-panel/60' : ''} onClick={() => setExpanded(expanded === event.id ? null : event.id)}>
                  <TD>{expanded === event.id ? <ChevronDown className="h-3.5 w-3.5 text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-muted" />}</TD>
                  <TD className="font-mono text-xs text-muted">{timeShort(event.at)}</TD>
                  <TD>{event.agent}</TD>
                  <TD><Badge tone={tone(event.decision) as never}>{event.decision}</Badge></TD>
                  <TD className="text-right font-mono text-xs">{compactNumber(event.beforeTokens)}</TD>
                  <TD className="text-right font-mono text-xs">{compactNumber(event.afterTokens)}</TD>
                  <TD className="text-right font-mono text-xs text-success">{event.savingPct}%</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </ScrollArea>
      </Card>
      <div className="space-y-3 min-h-0">
        <PathTrafficLights status={selected?.path} />
        <Card>
          <CardHeader><CardTitle>Expanded request evidence</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <section>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Raw context</p>
              <pre className="max-h-32 overflow-auto rounded-md border border-border bg-background p-2 font-mono text-xs text-muted">{selected?.rawContext}</pre>
            </section>
            <section>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Compiled context</p>
              <pre className="max-h-40 overflow-auto rounded-md border border-border bg-background p-2 font-mono text-xs text-foreground">{selected?.compiledContext}</pre>
            </section>
            <section>
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">Decision reason</p>
              <p className="rounded-md border border-border bg-background p-2 text-sm text-foreground">{selected?.reason}</p>
            </section>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
