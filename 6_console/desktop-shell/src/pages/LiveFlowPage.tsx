import { Fragment, useMemo, useState } from 'react';
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

type Decision = 'MEMORY_HIT' | 'REFINED' | 'BYPASS' | 'NO_MEMORY' | 'FALLBACK';

function hasTokenSavings(request: RecentRequest, evidence?: RequestEvidence | null): boolean {
  const savingsRatio = evidence?.context?.savings_ratio ?? request.savings_ratio;
  const savedTokens = evidence?.context?.saved_tokens ?? request.saved_tokens;
  return (savedTokens ?? 0) > 0 || (savingsRatio ?? 0) > 0;
}

function decisionFor(request: RecentRequest, evidence?: RequestEvidence | null): Decision {
  if (request.bypass) return 'BYPASS';
  if (request.request_class === 'value_qualified') return 'MEMORY_HIT';
  if (request.request_class === 'task_non_value' && hasTokenSavings(request, evidence)) return 'REFINED';
  if (request.request_class === 'task_non_value') return 'NO_MEMORY';
  return 'FALLBACK';
}

function tone(decision: string) {
  if (decision === 'MEMORY_HIT') return 'success';
  if (decision === 'REFINED') return 'accent';
  if (decision === 'FALLBACK' || decision === 'NO_MEMORY') return 'warning';
  return 'neutral';
}

function decisionLabel(decision: Decision, t: typeof copy.en.live | typeof copy.zh.live): string {
  if (decision === 'MEMORY_HIT') return t.decisionCompiled;
  if (decision === 'REFINED') return t.decisionRefined;
  if (decision === 'BYPASS') return t.decisionBypass;
  if (decision === 'NO_MEMORY') return t.decisionNoValue;
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

function requestTokens(request: RecentRequest, evidence: RequestEvidence | null | undefined) {
  const tokens = evidenceTokens(evidence);
  if (tokens.before != null || tokens.after != null || tokens.saving != null) return tokens;
  if (request.saved_tokens > 0 && request.savings_ratio > 0) {
    const before = Math.round(request.saved_tokens / request.savings_ratio);
    return {
      before,
      after: Math.max(0, before - request.saved_tokens),
      saving: request.savings_ratio,
    };
  }
  return {
    before: null,
    after: null,
    saving: request.savings_ratio,
  };
}

function instanceKey(request: RecentRequest) {
  return request.agent || 'unknown';
}

function groupRequests(requests: RecentRequest[]) {
  const groups = new Map<string, RecentRequest[]>();
  for (const request of requests) {
    const key = instanceKey(request);
    groups.set(key, [...(groups.get(key) ?? []), request]);
  }
  return Array.from(groups.entries()).map(([key, items]) => ({ key, items, latest: items[0] }));
}

export function LiveFlowPage() {
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const language = useDashboardStore((state) => state.language);
  const product = useDashboardStore((state) => state.product);
  const selectedRequestId = useDashboardStore((state) => state.selectedRequestId);
  const evidenceByRequestId = useDashboardStore((state) => state.evidenceByRequestId);
  const evidenceLoading = useDashboardStore((state) => state.evidenceLoading);
  const evidenceError = useDashboardStore((state) => state.evidenceError);
  const selectRequest = useDashboardStore((state) => state.selectRequest);
  const t = copy[language].live;
  const requests = useMemo(() => (product?.recent?.requests ?? []).filter((request) => request.request_class !== 'internal'), [product]);
  const groups = useMemo(() => groupRequests(requests), [requests]);
  const selected = requests.find((request) => request.request_id === selectedRequestId) ?? null;
  const selectedEvidence = selected ? evidenceByRequestId[selected.request_id] : null;
  const selectedTokens = selected ? requestTokens(selected, selectedEvidence) : { before: null, after: null, saving: null };
  const selectedHasSavings = selected ? hasTokenSavings(selected, selectedEvidence) : false;
  const selectedExpanded = selectedHasSavings && selectedTokens.before != null && selectedTokens.after != null && selectedTokens.after > selectedTokens.before;
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
                {groups.map((group) => {
                  const groupExpanded = expandedGroups[group.key] ?? false;
                  const latestEvidence = evidenceByRequestId[group.latest.request_id];
                  const latestTokens = requestTokens(group.latest, latestEvidence);
                  const latestDecision = decisionFor(group.latest, latestEvidence);
                  const latestHasSavings = hasTokenSavings(group.latest, latestEvidence);
                  const rows = groupExpanded ? group.items : [];
                  return (
                    <Fragment key={group.key}>
                      <TR key={group.key} className="bg-background/60" onClick={() => setExpandedGroups((current) => ({ ...current, [group.key]: !groupExpanded }))}>
                        <TD>{groupExpanded ? <ChevronDown className="h-3.5 w-3.5 text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-muted" />}</TD>
                        <TD className="font-mono text-xs text-muted">{timeShort(group.latest.timestamp)}</TD>
                        <TD>
                          <span>{group.key}</span>
                          <Badge tone="neutral" className="ml-2">{group.items.length} {t.records}</Badge>
                        </TD>
                        <TD><Badge tone={tone(latestDecision) as never}>{decisionLabel(latestDecision, t)}</Badge></TD>
                        <TD className="text-right font-mono text-xs">{latestHasSavings && latestTokens.before != null ? compactNumber(latestTokens.before) : t.notAvailable}</TD>
                        <TD className="text-right font-mono text-xs">{latestHasSavings && latestTokens.after != null ? compactNumber(latestTokens.after) : t.notAvailable}</TD>
                        <TD className={!latestHasSavings ? 'text-right font-mono text-xs text-muted' : latestTokens.before != null && latestTokens.after != null && latestTokens.after > latestTokens.before ? 'text-right font-mono text-xs text-warning' : 'text-right font-mono text-xs text-success'}>
                          {latestHasSavings ? percent(latestTokens.saving ?? group.latest.savings_ratio, 2) : t.notAvailable}
                        </TD>
                      </TR>
                      {rows.map((request) => {
                        const expanded = selectedRequestId === request.request_id;
                        const evidence = evidenceByRequestId[request.request_id];
                        const tokens = requestTokens(request, evidence);
                        const decision = decisionFor(request, evidence);
                        const showSavings = hasTokenSavings(request, evidence);
                        return (
                          <TR key={request.request_id} className={expanded ? 'bg-panel/60' : ''} onClick={() => void selectRequest(request)}>
                            <TD className="pl-6">{expanded ? <ChevronDown className="h-3.5 w-3.5 text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-muted" />}</TD>
                            <TD className="font-mono text-xs text-muted">{timeShort(request.timestamp)}</TD>
                            <TD>{request.agent || 'unknown'}</TD>
                            <TD><Badge tone={tone(decision) as never}>{decisionLabel(decision, t)}</Badge></TD>
                            <TD className="text-right font-mono text-xs">{showSavings && tokens.before != null ? compactNumber(tokens.before) : t.notAvailable}</TD>
                            <TD className="text-right font-mono text-xs">{showSavings && tokens.after != null ? compactNumber(tokens.after) : t.notAvailable}</TD>
                            <TD className={!showSavings ? 'text-right font-mono text-xs text-muted' : tokens.before != null && tokens.after != null && tokens.after > tokens.before ? 'text-right font-mono text-xs text-warning' : 'text-right font-mono text-xs text-success'}>
                              {showSavings ? percent(tokens.saving ?? request.savings_ratio, 2) : t.notAvailable}
                            </TD>
                          </TR>
                        );
                      })}
                    </Fragment>
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
                  <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">{t.before}</p><strong>{selectedHasSavings ? compactNumber(selectedTokens.before) : t.notAvailable}</strong></div>
                  <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">{t.after}</p><strong>{selectedHasSavings ? compactNumber(selectedTokens.after) : t.notAvailable}</strong></div>
                  <div className="rounded-md border border-border bg-background p-2">
                    <p className="text-xs text-muted">{selectedExpanded ? t.expandedTokens : t.saving}</p>
                    <strong className={!selectedHasSavings ? 'text-muted' : selectedExpanded ? 'text-warning' : 'text-success'}>{!selectedHasSavings ? t.notAvailable : selectedExpanded ? `+${compactNumber((selectedTokens.after ?? 0) - (selectedTokens.before ?? 0))}` : percent(selectedTokens.saving, 2)}</strong>
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
