import { useMemo } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { PathTrafficLights, buildPathStatus } from '../components/panels/PathTrafficLights';
import { compactNumber, percent, timeShort } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';
import type { RecentRequest, RequestEvidence } from '../types';

function decisionFor(request: RecentRequest): 'COMPILED' | 'BYPASS' | 'NO_VALUE' | 'FALLBACK' {
  if (request.bypass) return 'BYPASS';
  if (request.request_class === 'value_qualified') return 'COMPILED';
  if (request.request_class === 'task_non_value') return 'NO_VALUE';
  return 'FALLBACK';
}

function tone(decision: string) {
  if (decision === 'COMPILED') return 'success';
  if (decision === 'FALLBACK' || decision === 'NO_VALUE') return 'warning';
  return 'neutral';
}

function decisionLabel(decision: 'COMPILED' | 'BYPASS' | 'NO_VALUE' | 'FALLBACK', t: typeof copy.en.live | typeof copy.zh.live): string {
  if (decision === 'COMPILED') return t.decisionCompiled;
  if (decision === 'BYPASS') return t.decisionBypass;
  if (decision === 'NO_VALUE') return t.decisionNoValue;
  return t.decisionFallback;
}

function displayText(request: RecentRequest): string {
  return request.user_visible_query || request.query || request.diagnostic_label || request.request_id;
}

function evidenceTokens(evidence: RequestEvidence | null | undefined) {
  if (!evidence?.context) return { before: null, after: null, saving: null };
  return {
    before: evidence.context.before_tokens,
    after: evidence.context.after_tokens,
    saving: evidence.context.savings_ratio,
  };
}

export function LiveFlowPage() {
  const language = useDashboardStore((state) => state.language);
  const product = useDashboardStore((state) => state.product);
  const selectedRequestId = useDashboardStore((state) => state.selectedRequestId);
  const evidenceByRequestId = useDashboardStore((state) => state.evidenceByRequestId);
  const evidenceLoading = useDashboardStore((state) => state.evidenceLoading);
  const evidenceError = useDashboardStore((state) => state.evidenceError);
  const selectRequest = useDashboardStore((state) => state.selectRequest);
  const t = copy[language].live;
  const requests = useMemo(() => (product?.recent?.requests ?? []).filter((request) => request.request_class !== 'internal'), [product]);
  const selected = requests.find((request) => request.request_id === selectedRequestId) ?? null;
  const selectedEvidence = selected ? evidenceByRequestId[selected.request_id] : null;
  const selectedTokens = evidenceTokens(selectedEvidence);
  const selectedHasValue = selected?.display_savings_as_value === true;
  const selectedExpanded = selectedHasValue && selectedTokens.before != null && selectedTokens.after != null && selectedTokens.after > selectedTokens.before;
  const selectedDisplayText = selected
    ? selected.user_visible_query || selected.query || selectedEvidence?.request.query_summary || selected.diagnostic_label || selected.request_id
    : t.notAvailable;

  return (
    <div className="grid h-[calc(100vh-92px)] grid-cols-[1fr_420px] gap-3 max-2xl:grid-cols-1">
      <Card className="min-h-0">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>{t.stream}</CardTitle>
          <Badge tone="accent">{t.evidenceOnly}</Badge>
        </CardHeader>
        <ScrollArea className="h-[calc(100%-45px)]">
          {!requests.length ? (
            <div className="p-4 text-sm text-muted">{t.noRequests}</div>
          ) : (
            <Table>
              <THead className="sticky top-0 z-10 bg-surface">
                <TR className="hover:bg-transparent">
                  <TH className="w-8" />
                  <TH>{t.time}</TH>
                  <TH>{t.agent}</TH>
                  <TH>{t.decision}</TH>
                  <TH className="text-right">{t.before}</TH>
                  <TH className="text-right">{t.after}</TH>
                  <TH className="text-right">{t.saving}</TH>
                </TR>
              </THead>
              <TBody>
                {requests.map((request) => {
                  const expanded = selectedRequestId === request.request_id;
                  const evidence = evidenceByRequestId[request.request_id];
                  const tokens = evidenceTokens(evidence);
                  const decision = decisionFor(request);
                  const showSavings = request.display_savings_as_value === true;
                  return (
                    <TR key={request.request_id} className={expanded ? 'bg-panel/60' : ''} onClick={() => void selectRequest(request)}>
                      <TD>{expanded ? <ChevronDown className="h-3.5 w-3.5 text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-muted" />}</TD>
                      <TD className="font-mono text-xs text-muted">{timeShort(request.timestamp)}</TD>
                      <TD>{request.agent || 'unknown'}</TD>
                      <TD><Badge tone={tone(decision) as never}>{decisionLabel(decision, t)}</Badge></TD>
                      <TD className="text-right font-mono text-xs">{!showSavings || tokens.before == null ? t.notValue : compactNumber(tokens.before)}</TD>
                      <TD className="text-right font-mono text-xs">{!showSavings || tokens.after == null ? t.notValue : compactNumber(tokens.after)}</TD>
                      <TD className={!showSavings ? 'text-right font-mono text-xs text-muted' : tokens.before != null && tokens.after != null && tokens.after > tokens.before ? 'text-right font-mono text-xs text-warning' : 'text-right font-mono text-xs text-success'}>
                        {!showSavings ? t.notValue : percent(tokens.saving == null ? request.savings_ratio : tokens.saving, 2)}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          )}
        </ScrollArea>
      </Card>
      <div className="min-h-0 space-y-3">
        <PathTrafficLights language={language} status={buildPathStatus(selectedEvidence?.status ?? (selected ? { bypass: selected.bypass, request_status: selected.request_class } : null))} />
        <Card>
          <CardHeader><CardTitle>{t.expanded}</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {!selected && <p className="text-sm text-muted">{t.select}</p>}
            {selected && evidenceLoading && <p className="text-sm text-muted">{t.loading}</p>}
            {selected && !evidenceLoading && !selectedEvidence && <p className="text-sm text-muted">{evidenceError || t.unavailable}</p>}
            {selected && selectedEvidence && (
              <>
                <div className="grid grid-cols-3 gap-2">
                  <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">{t.before}</p><strong>{selectedHasValue ? compactNumber(selectedTokens.before) : t.notValue}</strong></div>
                  <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">{t.after}</p><strong>{selectedHasValue ? compactNumber(selectedTokens.after) : t.notValue}</strong></div>
                  <div className="rounded-md border border-border bg-background p-2">
                    <p className="text-xs text-muted">{selectedExpanded ? t.expandedTokens : t.saving}</p>
                    <strong className={!selectedHasValue ? 'text-muted' : selectedExpanded ? 'text-warning' : 'text-success'}>{!selectedHasValue ? t.notValue : selectedExpanded ? `+${compactNumber((selectedTokens.after ?? 0) - (selectedTokens.before ?? 0))}` : percent(selectedTokens.saving, 2)}</strong>
                  </div>
                </div>
                {selectedExpanded && <p className="rounded-md border border-warning/30 bg-warning/10 p-2 text-xs text-warning">{t.expandedDetail}</p>}
                <section>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t.raw}</p>
                  <pre className="max-h-32 overflow-auto rounded-md border border-border bg-background p-2 font-mono text-xs text-muted">{selectedDisplayText}</pre>
                </section>
                <section>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t.compiled}</p>
                  <pre className="max-h-40 overflow-auto rounded-md border border-border bg-background p-2 font-mono text-xs text-foreground">{selectedEvidence.context.selected_memories.map((memory) => memory.content || memory.abstract || memory.uri).join('\n\n') || t.notAvailable}</pre>
                </section>
                <section>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t.reason}</p>
                  <p className="rounded-md border border-border bg-background p-2 text-sm text-foreground">{selectedEvidence.status.failure_reason || selected.qualification_reason || selected.diagnostic_label || decisionLabel(decisionFor(selected), t)}</p>
                </section>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
