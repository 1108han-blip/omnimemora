import type { MetricsSummary } from '../types';

interface HeroMetricsProps {
  data: MetricsSummary;
}

export function HeroMetrics({ data }: HeroMetricsProps) {
  const metrics = [
    {
      label: 'Token Saving',
      value: `${Math.round(data.token_saving_ratio * 100)}%`,
      sub: `Saved: ${data.tokens_saved.toLocaleString()} tokens`,
      color: 'text-emerald-600',
    },
    {
      label: 'Requests Processed',
      value: data.request_count.toLocaleString(),
      sub: 'total queries',
      color: 'text-blue-600',
    },
    {
      label: 'Avg Context Reduction',
      value: `${Math.round(data.avg_context_reduction * 100)}%`,
      sub: 'tokens saved per query',
      color: 'text-purple-600',
    },
    {
      label: 'Total Tokens Saved',
      value: data.tokens_saved > 1000
        ? `${(data.tokens_saved / 1000).toFixed(1)}K`
        : data.tokens_saved.toString(),
      sub: 'across all requests',
      color: 'text-amber-600',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {metrics.map((m) => (
        <div
          key={m.label}
          className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6 text-center shadow-sm"
        >
          <div className="text-sm text-zinc-500 dark:text-zinc-400 font-medium">{m.label}</div>
          <div className={`text-4xl font-bold mt-2 ${m.color}`}>{m.value}</div>
          <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">{m.sub}</div>
        </div>
      ))}
    </div>
  );
}
