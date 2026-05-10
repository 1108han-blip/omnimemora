import { Fragment, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Table, TBody, TD, TH, THead, TR } from '../components/ui/table';
import { ScrollArea } from '../components/ui/scroll-area';
import { PathTrafficLights, buildPathStatus } from '../components/panels/PathTrafficLights';
import { percent, timeShort } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';
import type { RecentRequest, RequestEvidence } from '../types';

type DecisionTag = 'REFINED' | 'MEMORY' | 'BYPASS' | 'NONE';

function hasMemoryHit(request: RecentRequest, evidence?: RequestEvidence | null): boolean {
  return (
    (evidence?.context?.selected_memory_count ?? 0) > 0 ||
    request.packed_memory_count > 0 ||
    request.local_cards_used > 0 ||
    request.remote_used_count > 0 ||
    request.request_class === 'value_qualified'
  );
}

function hasRealInputMetrics(request: RecentRequest, evidence?: RequestEvidence | null): boolean {
  const baseline = evidence?.context?.real_input?.baseline_payload_tokens ?? request.baseline_payload_tokens ?? 0;
  const forwarded = evidence?.context?.real_input?.forwarded_payload_tokens ?? request.forwarded_payload_tokens ?? 0;
  return baseline > 0 && forwarded > 0;
}

function realInputSavingRatio(before: number | null | undefined, after: number | null | undefined): number | null {
  if (before == null || after == null || before <= 0) return null;
  return (before - after) / before;
}

function formatTokenCount(value: number | null | undefined): string {
  if (!Number.isFinite(value ?? Number.NaN)) return '0';
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(Math.round(value as number));
}

function savingClass(hasMetrics: boolean, saving: number | null | undefined): string {
  if (!hasMetrics) return 'text-right font-mono text-xs text-muted';
  if ((saving ?? 0) > 0) return 'text-right font-mono text-xs text-success';
  if ((saving ?? 0) < 0) return 'text-right font-mono text-xs text-warning';
  return 'text-right font-mono text-xs text-muted';
}

function selectedMemoryCount(request: RecentRequest, evidence?: RequestEvidence | null): number {
  return Math.max(
    evidence?.context?.selected_memory_count ?? 0,
    request.packed_memory_count ?? 0,
    request.local_cards_used ?? 0,
    request.remote_used_count ?? 0,
  );
}

function hasRefinement(request: RecentRequest, evidence?: RequestEvidence | null): boolean {
  const sourceTokens = evidence?.context?.compression?.source_tokens ?? request.compression_source_tokens ?? 0;
  const outputTokens = evidence?.context?.compression?.output_tokens ?? request.compression_output_tokens ?? 0;
  return sourceTokens > 0 && outputTokens > 0 && outputTokens < sourceTokens;
}

function decisionTagsFor(request: RecentRequest, evidence?: RequestEvidence | null): DecisionTag[] {
  if (request.bypass) return ['BYPASS'];
  const tags: DecisionTag[] = [];
  if (hasRefinement(request, evidence)) tags.push('REFINED');
  if (hasMemoryHit(request, evidence)) tags.push('MEMORY');
  return tags.length ? tags : ['NONE'];
}

function tone(decision: DecisionTag) {
  if (decision === 'MEMORY') return 'success';
  if (decision === 'REFINED') return 'accent';
  if (decision === 'BYPASS') return 'neutral';
  return 'neutral';
}

function decisionLabel(decision: DecisionTag, t: typeof copy.en.live | typeof copy.zh.live): string {
  if (decision === 'MEMORY') return t.decisionMemory;
  if (decision === 'REFINED') return t.decisionRefined;
  if (decision === 'BYPASS') return t.decisionBypass;
  return t.decisionNone;
}

function DecisionTags({ tags, t }: { tags: DecisionTag[]; t: typeof copy.en.live | typeof copy.zh.live }) {
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Badge key={tag} tone={tone(tag)}>{decisionLabel(tag, t)}</Badge>
      ))}
    </div>
  );
}

function displayText(request: RecentRequest): string {
  return request.user_visible_query || request.query || request.diagnostic_label || request.request_id;
}

function evidenceTokens(evidence: RequestEvidence | null | undefined) {
  if (!evidence?.context) return { before: null, after: null, saving: null };
  if (evidence.context.real_input) {
    const before = evidence.context.real_input.baseline_payload_tokens;
    const after = evidence.context.real_input.forwarded_payload_tokens;
    return {
      before,
      after,
      saving: realInputSavingRatio(before, after),
    };
  }
  return {
    before: null,
    after: null,
    saving: null,
  };
}

function requestTokens(request: RecentRequest, evidence: RequestEvidence | null | undefined) {
  const tokens = evidenceTokens(evidence);
  if (tokens.before != null || tokens.after != null || tokens.saving != null) return tokens;
  const before = request.baseline_payload_tokens ?? null;
  const after = request.forwarded_payload_tokens ?? null;
  return {
    before,
    after,
    saving: realInputSavingRatio(before, after) ?? request.real_input_savings_ratio ?? null,
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
  const requests = useMemo(() => product?.recent?.requests ?? [], [product]);
  const recentError = product?.recentError ?? null;
  const groups = useMemo(() => groupRequests(requests), [requests]);
  const selected = requests.find((request) => request.request_id === selectedRequestId) ?? null;
  const selectedEvidence = selected ? evidenceByRequestId[selected.request_id] : null;
  const selectedTokens = selected ? requestTokens(selected, selectedEvidence) : { before: null, after: null, saving: null };
  const selectedHasMetrics = selected ? hasRealInputMetrics(selected, selectedEvidence) : false;
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
          {recentError ? (
            <div className="m-4 rounded-md border border-warning/30 bg-warning/10 p-3 text-sm text-warning">
              <p className="font-medium">{t.recentError}</p>
              <p className="mt-1 font-mono text-xs">{recentError}</p>
            </div>
          ) : !requests.length ? (
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
                  const latestTags = decisionTagsFor(group.latest, latestEvidence);
                  const latestHasMetrics = hasRealInputMetrics(group.latest, latestEvidence);
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
                        <TD><DecisionTags tags={latestTags} t={t} /></TD>
                        <TD className="text-right font-mono text-xs">{latestHasMetrics ? formatTokenCount(latestTokens.before) : t.notAvailable}</TD>
                        <TD className="text-right font-mono text-xs">{latestHasMetrics ? formatTokenCount(latestTokens.after) : t.notAvailable}</TD>
                        <TD className={savingClass(latestHasMetrics, latestTokens.saving)}>
                          {latestHasMetrics ? percent(latestTokens.saving ?? group.latest.real_input_savings_ratio ?? 0, 2) : t.notAvailable}
                        </TD>
                      </TR>
                      {rows.map((request) => {
                        const expanded = selectedRequestId === request.request_id;
                        const evidence = evidenceByRequestId[request.request_id];
                        const tokens = requestTokens(request, evidence);
                        const decisionTags = decisionTagsFor(request, evidence);
                        const showMetrics = hasRealInputMetrics(request, evidence);
                        return (
                          <TR key={request.request_id} className={expanded ? 'bg-panel/60' : ''} onClick={() => void selectRequest(request)}>
                            <TD className="pl-6">{expanded ? <ChevronDown className="h-3.5 w-3.5 text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-muted" />}</TD>
                            <TD className="font-mono text-xs text-muted">{timeShort(request.timestamp)}</TD>
                            <TD>{request.agent || 'unknown'}</TD>
                            <TD><DecisionTags tags={decisionTags} t={t} /></TD>
                            <TD className="text-right font-mono text-xs">{showMetrics ? formatTokenCount(tokens.before) : t.notAvailable}</TD>
                            <TD className="text-right font-mono text-xs">{showMetrics ? formatTokenCount(tokens.after) : t.notAvailable}</TD>
                            <TD className={savingClass(showMetrics, tokens.saving)}>
                              {showMetrics ? percent(tokens.saving ?? request.real_input_savings_ratio ?? 0, 2) : t.notAvailable}
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
                  <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">{t.before}</p><strong>{selectedHasMetrics ? formatTokenCount(selectedTokens.before) : t.notAvailable}</strong></div>
                  <div className="rounded-md border border-border bg-background p-2"><p className="text-xs text-muted">{t.after}</p><strong>{selectedHasMetrics ? formatTokenCount(selectedTokens.after) : t.notAvailable}</strong></div>
                  <div className="rounded-md border border-border bg-background p-2">
                    <p className="text-xs text-muted">{t.saving}</p>
                    <strong className={selectedHasMetrics && (selectedTokens.saving ?? 0) > 0 ? 'text-success' : selectedHasMetrics && (selectedTokens.saving ?? 0) < 0 ? 'text-warning' : 'text-muted'}>{selectedHasMetrics ? percent(selectedTokens.saving ?? 0, 2) : t.notAvailable}</strong>
                  </div>
                </div>
                <section>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t.raw}</p>
                  <pre className="max-h-32 overflow-auto rounded-md border border-border bg-background p-2 font-mono text-xs text-muted">{selectedDisplayText}</pre>
                </section>
                <section>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t.compiled}</p>
                  <p className="rounded-md border border-border bg-background p-2 text-sm text-foreground">{selectedMemoryCount(selected, selectedEvidence)} {t.memoryItems}</p>
                </section>
                <section>
                  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t.reason}</p>
                  <p className="rounded-md border border-border bg-background p-2 text-sm text-foreground">{selectedEvidence.status.failure_reason || selected.qualification_reason || selected.diagnostic_label || decisionTagsFor(selected, selectedEvidence).map((tag) => decisionLabel(tag, t)).join(' / ')}</p>
                </section>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
