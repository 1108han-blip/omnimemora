import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { ChartTooltip } from '../components/panels/ChartTooltip';
import { Badge } from '../components/ui/badge';
import { PathTrafficLights, buildPathStatus } from '../components/panels/PathTrafficLights';
import { compactNumber, percent } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';

export function OverviewPage() {
  const language = useDashboardStore((state) => state.language);
  const product = useDashboardStore((state) => state.product);
  const setPage = useDashboardStore((state) => state.setPage);
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
  }));
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
        {[
          [t.tokensSaved, compactNumber(saved), t.basedOnReal, 'savings'],
          [t.compileRate, percent(compileRate), t.compiledWithMemory, 'live-flow'],
          [t.coverage, percent(coverage), t.realTraffic, 'live-flow'],
          [t.activeAgents, String(activeAgents), t.detectedActive, 'agents'],
        ].map(([label, value, detail, page]) => (
          <button key={label} className="text-left" onClick={() => setPage(page as never)}>
            <Card className="transition hover:border-accent/50 hover:bg-panel/70">
              <CardContent className="p-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</p>
                <div className="mt-2 flex items-end justify-between gap-3">
                  <strong className="text-2xl font-semibold tracking-tight text-foreground">{value}</strong>
                  <Badge tone="accent">{t.drill}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted">{detail}</p>
              </CardContent>
            </Card>
          </button>
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
                  <XAxis dataKey="date" stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} />
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
