import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { ChartTooltip } from '../components/panels/ChartTooltip';
import { compactNumber } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';
import { copy } from '../lib/i18n';

export function SavingsPage() {
  const language = useDashboardStore((state) => state.language);
  const product = useDashboardStore((state) => state.product);
  const t = copy[language].savings;
  const overview = copy[language].overview;
  const saved = product?.core?.cards.token_savings.saved_tokens ?? 0;
  const usd = saved * 0.00001;
  const trend = (product?.coreTrend?.trend ?? []).map((point) => ({ day: point.date, tokens: point.token_savings.saved_tokens }));

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3 max-lg:grid-cols-1">
        <Card><CardContent><p className="text-xs uppercase tracking-wide text-muted">{t.total}</p><strong className="mt-2 block text-3xl">{compactNumber(saved)}</strong></CardContent></Card>
        <Card><CardContent><p className="text-xs uppercase tracking-wide text-muted">{t.usd}</p><strong className="mt-2 block text-3xl">${usd.toFixed(2)}</strong></CardContent></Card>
        <Card><CardContent><p className="text-xs uppercase tracking-wide text-muted">{t.quality}</p><strong className="mt-2 block text-3xl text-success">{t.stable}</strong></CardContent></Card>
      </div>
      <Card>
        <CardHeader><CardTitle>{t.trend}</CardTitle></CardHeader>
        <CardContent className="h-[420px]">
          {trend.length ? (
            <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1} initialDimension={{ width: 640, height: 260 }}>
              <AreaChart data={trend} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
                <CartesianGrid stroke="#1F2A37" vertical={false} />
                <XAxis dataKey="day" stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} padding={{ left: 12, right: 24 }} />
                <YAxis stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="tokens" stroke="#35D7FF" fill="#35D7FF" fillOpacity={0.12} dot={{ r: 3, fill: '#35D7FF', strokeWidth: 0 }} activeDot={{ r: 5 }} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <div className="grid h-full place-items-center text-sm text-muted">{overview.noData}</div>}
        </CardContent>
      </Card>
    </div>
  );
}
