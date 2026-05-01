import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { ChartTooltip } from '../components/panels/ChartTooltip';
import { compactNumber } from '../lib/utils';
import { useDashboardStore } from '../store/useDashboardStore';

const trend = Array.from({ length: 14 }, (_, index) => ({ day: `D-${13 - index}`, tokens: 4200 + index * 760 + (index % 4) * 900, usd: 0.8 + index * 0.22 }));

export function SavingsPage() {
  const product = useDashboardStore((state) => state.product);
  const saved = product?.usage?.saved_tokens_total ?? 28025;
  const usd = saved * 0.00001;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3 max-lg:grid-cols-1">
        <Card><CardContent><p className="text-xs uppercase tracking-wide text-muted">Total tokens saved</p><strong className="mt-2 block text-3xl">{compactNumber(saved)}</strong></CardContent></Card>
        <Card><CardContent><p className="text-xs uppercase tracking-wide text-muted">USD equivalent</p><strong className="mt-2 block text-3xl">${usd.toFixed(2)}</strong></CardContent></Card>
        <Card><CardContent><p className="text-xs uppercase tracking-wide text-muted">Savings quality</p><strong className="mt-2 block text-3xl text-success">Stable</strong></CardContent></Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Token savings trend</CardTitle></CardHeader>
        <CardContent className="h-[420px]">
          <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1} initialDimension={{ width: 640, height: 260 }}>
            <AreaChart data={trend} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
              <CartesianGrid stroke="#1F2A37" vertical={false} />
              <XAxis dataKey="day" stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#8B96A6" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="tokens" stroke="#35D7FF" fill="#35D7FF" fillOpacity={0.12} />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}
