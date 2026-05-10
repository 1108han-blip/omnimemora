import { useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { ChartTooltip } from '../components/panels/ChartTooltip';
import { PathTrafficLights, buildPathStatus } from '../components/panels/PathTrafficLights';
import { compactNumber, percent } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';

type MetricKey = 'saved' | 'compile' | 'coverage' | 'agents';

interface MetricCard {
  key: MetricKey;
  label: string;
  value: string;
  detail: string;
  data: Array<{ date: string; value: number }>;
  valueKind: 'number' | 'percent';
}

function formatDay(date: string): string {
  const [, month, day] = date.split('-');
  return month && day ? `${month}/${day}` : date;
}

function formatMetricValue(value: number, kind: MetricCard['valueKind']): string {
  return kind === 'percent' ? `${Math.round(value)}%` : compactNumber(value);
}

function sevenDayAgentCounts(requests: ReturnType<typeof useDashboardStore.getState>['product'] extends infer _ ? Array<{ timestamp: string; agent: string }> : never) {
  const byDate = new Map<string, Set<string>>();
  for (const request of requests) {
    const day = new Date(request.timestamp).toISOString().slice(0, 10);
    if (!byDate.has(day)) byDate.set(day, new Set());
    byDate.get(day)?.add(request.agent || 'unknown');
  }
  return byDate;
}

function MetricFlipCard({ card, flipped, onToggle, hint }: { card: MetricCard; flipped: boolean; onToggle: () => void; hint: string }) {
  return (
    <button
      type="button"
      className="flip-card min-h-[104px] text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
      data-flipped={flipped}
      onClick={onToggle}
      aria-pressed={flipped}
      aria-label={`${card.label}: ${hint}`}
    >
      <div className="flip-card-inner min-h-[104px]">
        <Card className="flip-card-face min-h-[104px] transition hover:border-accent/50 hover:bg-panel/70" aria-hidden={flipped}>
          <CardContent className="p-3">
            <div className="flex items-start justify-between gap-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{card.label}</p>
              <span className="text-[10px] font-medium text-muted opacity-0 transition group-hover:opacity-100">{hint}</span>
            </div>
            <strong className="mt-2 block text-2xl font-semibold tracking-tight text-foreground">{card.value}</strong>
            <p className="mt-1 text-xs text-muted">{card.detail}</p>
          </CardContent>
        </Card>
        <Card className="flip-card-face flip-card-back min-h-[104px] border-accent/40 bg-panel/80" aria-hidden={!flipped}>
          <CardContent className="flex h-[104px] flex-col p-3">
            <div className="mb-1 flex items-center justify-between gap-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{card.label}</p>
              <span className="text-[10px] text-muted">{hint}</span>
            </div>
            <div className="min-h-0 flex-1">
              <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1} initialDimension={{ width: 360, height: 62 }}>
                <BarChart data={card.data} margin={{ left: -12, right: 0, top: 4, bottom: 0 }}>
                  <XAxis dataKey="date" tickFormatter={formatDay} stroke="#8B96A6" fontSize={9} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis hide domain={[0, 'dataMax']} />
                  <Tooltip content={<ChartTooltip />} formatter={(value) => formatMetricValue(Number(value), card.valueKind)} />
                  <Bar dataKey="value" fill="#35D7FF" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </button>
  );
}

export function OverviewPage() {
  const [flipped, setFlipped] = useState<Record<MetricKey, boolean>>({ saved: false, compile: false, coverage: false, agents: false });
  const language = useDashboardStore((state) => state.language);
  const product = useDashboardStore((state) => state.product);
  const t = copy[language].overview;
  const recent = (product?.recent?.requests ?? []).filter((request) => request.request_class !== 'internal');
  const controls = product?.controls?.agents ?? [];
  const saved = product?.core?.cards.token_savings.saved_tokens ?? 0;
  const compileRate = product?.core?.cards.memory_enhancement.rate ?? 0;
  const coverage = product?.core?.cards.real_requests.ratio ?? 0;
  const activeAgents = controls.filter((agent) => agent.active).length;
  const trend = (product?.coreTrend?.trend ?? []).map((point) => ({
    date: point.date,
    saved: point.token_savings.saved_tokens,
    compile: Math.round((point.memory_enhancement.rate ?? 0) * 100),
    coverage: Math.round((point.real_requests.ratio ?? 0) * 100),
  }));
  const agentCounts = useMemo(() => sevenDayAgentCounts(recent), [recent]);
  const metricCards: MetricCard[] = [
    {
      key: 'saved',
      label: t.tokensSaved,
      value: compactNumber(saved),
      detail: t.basedOnReal,
      data: trend.map((point) => ({ date: point.date, value: point.saved })),
      valueKind: 'number',
    },
    {
      key: 'compile',
      label: t.compileRate,
      value: percent(compileRate),
      detail: t.compiledWithMemory,
      data: trend.map((point) => ({ date: point.date, value: point.compile })),
      valueKind: 'percent',
    },
    {
      key: 'coverage',
      label: t.coverage,
      value: percent(coverage),
      detail: t.realTraffic,
      data: trend.map((point) => ({ date: point.date, value: point.coverage })),
      valueKind: 'percent',
    },
    {
      key: 'agents',
      label: t.activeAgents,
      value: String(activeAgents),
      detail: t.detectedActive,
      data: trend.map((point) => ({ date: point.date, value: agentCounts.get(point.date)?.size ?? 0 })),
      valueKind: 'number',
    },
  ];
  const agentUsage = controls.map((agent) => ({
    name: agent.display_name,
    usagePct: Math.round((agent.savings_ratio_24h ?? 0) * 100),
    requests: agent.requests_24h ?? agent.observed_requests_24h ?? 0,
  }));

  if (!product?.online) {
    return <div className="rounded-lg border border-border bg-surface p-4 text-sm text-muted">{t.noData}</div>;
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-3 max-xl:grid-cols-2 max-sm:grid-cols-1">
        {metricCards.map((card) => (
          <MetricFlipCard
            key={card.key}
            card={card}
            flipped={flipped[card.key]}
            hint={flipped[card.key] ? t.backHint : t.flipHint}
            onToggle={() => setFlipped((state) => ({ ...state, [card.key]: !state[card.key] }))}
          />
        ))}
      </div>

      <PathTrafficLights language={language} status={buildPathStatus(recent[0] ? { bypass: recent[0].bypass, request_status: recent[0].request_class } : null)} />

      <div className="grid grid-cols-[1.45fr_.9fr] gap-3 max-xl:grid-cols-1">
        <Card>
          <CardHeader><CardTitle>{t.savingsChart}</CardTitle></CardHeader>
          <CardContent className="h-72">
            {trend.length ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1} initialDimension={{ width: 640, height: 260 }}>
                <LineChart data={trend} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
                  <CartesianGrid stroke="#1F2A37" vertical={false} />
                  <XAxis dataKey="date" stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} padding={{ left: 12, right: 24 }} />
                  <YAxis stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="saved" stroke="#35D7FF" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="compile" stroke="#6D7CFF" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div className="grid h-full place-items-center text-sm text-muted">{t.noData}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t.agentUsage}</CardTitle></CardHeader>
          <CardContent className="h-72">
            {agentUsage.length ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1} initialDimension={{ width: 640, height: 260 }}>
                <BarChart data={agentUsage} layout="vertical" margin={{ left: 12, right: 12, top: 8, bottom: 0 }}>
                  <CartesianGrid stroke="#1F2A37" horizontal={false} />
                  <XAxis type="number" stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis type="category" dataKey="name" stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} width={86} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="requests" fill="#6D7CFF" radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : <div className="grid h-full place-items-center text-sm text-muted">{t.noData}</div>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
