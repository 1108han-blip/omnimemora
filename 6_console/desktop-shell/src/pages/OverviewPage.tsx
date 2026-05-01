import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { ChartTooltip } from '../components/panels/ChartTooltip';
import { Badge } from '../components/ui/badge';
import { PathTrafficLights } from '../components/panels/PathTrafficLights';
import { compactNumber, percent } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';

const series = Array.from({ length: 12 }, (_, index) => ({
  time: `${String(index * 2).padStart(2, '0')}:00`,
  saved: 1200 + index * 380 + (index % 3) * 520,
  compile: 42 + ((index * 7) % 31),
}));

export function OverviewPage() {
  const product = useDashboardStore((state) => state.product);
  const agents = useDashboardStore((state) => state.agents);
  const flow = useDashboardStore((state) => state.flow);
  const setPage = useDashboardStore((state) => state.setPage);
  const saved = product?.core?.cards.token_savings.saved_tokens ?? 28025;
  const compileRate = flow.filter((event) => event.decision === 'COMPILED').length / Math.max(1, flow.length);
  const coverage = product?.core?.cards.real_requests.ratio ?? 0.72;
  const activeAgents = agents.filter((agent) => agent.status === 'active').length;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-3 max-xl:grid-cols-2 max-sm:grid-cols-1">
        {[
          ['Tokens Saved Today', compactNumber(saved), 'Based on value-qualified requests', 'savings'],
          ['Compile Rate', percent(compileRate), 'Compiled vs bypass/fallback', 'live-flow'],
          ['Coverage %', percent(coverage), 'Real traffic covered by OmniMemora', 'live-flow'],
          ['Active Agents', String(activeAgents), 'Detected and recently active', 'agents'],
        ].map(([label, value, detail, page]) => (
          <button key={label} className="text-left" onClick={() => setPage(page as never)}>
            <Card className="transition hover:border-accent/50 hover:bg-panel/70">
              <CardContent className="p-3">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</p>
                <div className="mt-2 flex items-end justify-between gap-3">
                  <strong className="text-2xl font-semibold tracking-tight text-foreground">{value}</strong>
                  <Badge tone="accent">drill</Badge>
                </div>
                <p className="mt-1 text-xs text-muted">{detail}</p>
              </CardContent>
            </Card>
          </button>
        ))}
      </div>

      <PathTrafficLights status={flow[0]?.path} />

      <div className="grid grid-cols-[1.45fr_.9fr] gap-3 max-xl:grid-cols-1">
        <Card>
          <CardHeader><CardTitle>Token savings and compile rate</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1} initialDimension={{ width: 640, height: 260 }}>
              <LineChart data={series} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
                <CartesianGrid stroke="#1F2A37" vertical={false} />
                <XAxis dataKey="time" stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Line type="monotone" dataKey="saved" stroke="#35D7FF" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="compile" stroke="#6D7CFF" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Agent usage</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1} initialDimension={{ width: 640, height: 260 }}>
              <BarChart data={agents} layout="vertical" margin={{ left: 12, right: 12, top: 8, bottom: 0 }}>
                <CartesianGrid stroke="#1F2A37" horizontal={false} />
                <XAxis type="number" stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="name" stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} width={86} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="usagePct" fill="#6D7CFF" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
