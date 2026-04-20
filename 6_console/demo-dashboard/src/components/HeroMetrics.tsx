import type { MetricsSummary, MetricsTrendPoint } from '../types';

interface HeroMetricsProps {
  data: MetricsSummary | null;
  trendData?: MetricsTrendPoint[];
  allTimeSavedTokens?: number;
  recent24hSavedTokens?: number;
  showBack?: boolean;
}

export function HeroMetrics({ data, trendData = [], allTimeSavedTokens = 0, recent24hSavedTokens = 0, showBack = false }: HeroMetricsProps) {
  if (!data) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6 animate-pulse">
            <div className="h-3 bg-zinc-200 dark:bg-zinc-700 rounded w-20 mb-3" />
            <div className="h-8 bg-zinc-200 dark:bg-zinc-700 rounded w-16" />
          </div>
        ))}
      </div>
    );
  }

  if (showBack) {
    const maxSaved = Math.max(...trendData.map(d => d.saved_tokens), 1);
    const total7dSaved = trendData.reduce((sum, d) => sum + d.saved_tokens, 0);
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="mb-4">
          <div className="text-sm font-semibold text-zinc-700 dark:text-zinc-300 mb-1">7 天趋势</div>
          <div className="text-xs text-zinc-400">Saved Tokens / 天 &nbsp;|&nbsp; 7天累计: {total7dSaved.toLocaleString()} tokens</div>
        </div>

        {trendData.length === 0 ? (
          <div className="text-sm text-zinc-400 py-8 text-center">暂无趋势数据</div>
        ) : (
          <div className="flex items-end gap-1 h-32 mb-4">
            {trendData.map((point) => {
              const heightPct = (point.saved_tokens / maxSaved) * 100;
              const dateLabel = point.date.slice(5); // MM-DD
              return (
                <div key={point.date} className="flex-1 flex flex-col items-center gap-1">
                  <div className="w-full flex flex-col items-center justify-end h-full">
                    <div
                      className="w-full bg-emerald-400 dark:bg-emerald-600 rounded-t transition-all"
                      style={{ height: `${Math.max(heightPct, 2)}%` }}
                      title={`${point.saved_tokens.toLocaleString()} tokens`}
                    />
                  </div>
                  <div className="text-[10px] text-zinc-400 mt-1">{dateLabel}</div>
                </div>
              );
            })}
          </div>
        )}

        <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-zinc-100 dark:border-zinc-800">
          <div className="text-center">
            <div className="text-xs text-zinc-500 mb-1">全历史累计 Saved</div>
            <div className="text-2xl font-bold text-amber-600">
              {allTimeSavedTokens > 1000
                ? `${(allTimeSavedTokens / 1000).toFixed(1)}K`
                : allTimeSavedTokens.toLocaleString()}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-zinc-500 mb-1">最近 24h</div>
            <div className="text-2xl font-bold text-emerald-600">
              {recent24hSavedTokens > 1000
                ? `${(recent24hSavedTokens / 1000).toFixed(1)}K`
                : recent24hSavedTokens.toLocaleString()}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 正面：24h metrics
  const metrics = [
    {
      label: 'Token Saving',
      value: `${Math.round(data.token_saving_ratio * 100)}%`,
      sub: `24h Saved: ${data.tokens_saved.toLocaleString()} tokens`,
      color: 'text-emerald-600',
    },
    {
      label: 'Requests (24h)',
      value: data.request_count.toLocaleString(),
      sub: 'queries optimized',
      color: 'text-blue-600',
    },
    {
      label: 'Avg Context Reduction',
      value: `${Math.round(data.avg_context_reduction * 100)}%`,
      sub: 'per query',
      color: 'text-purple-600',
    },
    {
      label: 'Saved Tokens (24h)',
      value: data.tokens_saved > 1000
        ? `${(data.tokens_saved / 1000).toFixed(1)}K`
        : data.tokens_saved.toString(),
      sub: 'tokens optimized',
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
