import { useState, useEffect, useCallback } from 'react';
import type { LiveAgent } from '../types';

type SortKey = 'saved_tokens' | 'entry_rate' | 'request_count' | 'quality_delta_pct' | 'last_seen_at';
type SortDir = 'asc' | 'desc';

const MODE_LABELS: Record<string, string> = {
  observe: '观察',
  guided: '引导',
  force_if_possible: '强制优化',
  off: '关闭',
};

function formatRelativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return `${secs}秒前`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}分钟前`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}小时前`;
    return `${Math.floor(hrs / 24)}天前`;
  } catch {
    return iso;
  }
}

export function AgentsDashboard() {
  const [agents, setAgents] = useState<LiveAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [modeFilter, setModeFilter] = useState<string>('all');
  const [sortKey, setSortKey] = useState<SortKey>('saved_tokens');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const load = useCallback(async () => {
    try {
      const res = await fetch('/agents/live?window_minutes=1440'); // 24h window for overview
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAgents(data.agents ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [load]);

  // Derived totals
  const totalAgents = agents.length;
  const totalRequests = agents.reduce((s, a) => s + a.request_count, 0);
  const totalSaved = agents.reduce((s, a) => s + a.saved_tokens, 0);
  const avgEntryRate = totalRequests > 0
    ? agents.reduce((s, a) => s + a.entry_rate * a.request_count, 0) / totalRequests
    : 0;

  // Filter
  const filtered = agents.filter(a => {
    const matchSearch = !search || a.agent_id.toLowerCase().includes(search.toLowerCase());
    const matchMode = modeFilter === 'all' || a.mode === modeFilter;
    return matchSearch && matchMode;
  });

  // Sort
  const sorted = [...filtered].sort((a, b) => {
    let va: number | string = 0;
    let vb: number | string = 0;
    if (sortKey === 'saved_tokens') { va = a.saved_tokens; vb = b.saved_tokens; }
    else if (sortKey === 'entry_rate') { va = a.entry_rate; vb = b.entry_rate; }
    else if (sortKey === 'request_count') { va = a.request_count; vb = b.request_count; }
    else if (sortKey === 'quality_delta_pct') { va = a.quality_delta_pct; vb = b.quality_delta_pct; }
    else if (sortKey === 'last_seen_at') { va = a.last_seen_at; vb = b.last_seen_at; }
    if (va < vb) return sortDir === 'asc' ? -1 : 1;
    if (va > vb) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  function SortIcon({ col }: { col: SortKey }) {
    if (sortKey !== col) return <span className="text-zinc-600 ml-1">↕</span>;
    return <span className="text-zinc-900 dark:text-zinc-100 ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Agent 监控面板</h2>
          <p className="text-xs text-zinc-400 mt-0.5">实时 · 10秒自动刷新</p>
        </div>
        <div className={`w-2 h-2 rounded-full ${error ? 'bg-red-500' : 'bg-emerald-500'}`} />
        <span className="text-xs text-zinc-500">{error ? '连接异常' : '已连接'}</span>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="活跃 Agent" value={totalAgents} unit="个" />
        <MetricCard label="累计请求" value={totalRequests} unit="次" />
        <MetricCard label="累计节省 Token" value={totalSaved} unit=" tokens" accent />
        <MetricCard label="平均入口占比" value={Math.round(avgEntryRate * 100)} unit="%" />
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="搜索 agent_id..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="text-sm border border-zinc-300 dark:border-zinc-700 rounded-lg px-3 py-1.5 bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={modeFilter}
          onChange={e => setModeFilter(e.target.value)}
          className="text-sm border border-zinc-300 dark:border-zinc-700 rounded-lg px-3 py-1.5 bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">全部模式</option>
          <option value="observe">观察</option>
          <option value="guided">引导</option>
          <option value="force_if_possible">强制优化</option>
          <option value="off">关闭</option>
        </select>
        <span className="text-xs text-zinc-400">
          {sorted.length} / {agents.length} 个 agent
        </span>
      </div>

      {/* Table */}
      {loading && agents.length === 0 ? (
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-8">
          <div className="animate-pulse space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-8 bg-zinc-200 dark:bg-zinc-700 rounded w-full" />
            ))}
          </div>
        </div>
      ) : sorted.length === 0 ? (
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-8 text-center">
          <div className="text-zinc-400 text-sm">暂无 Agent 数据</div>
        </div>
      ) : (
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-zinc-50 dark:bg-zinc-800 text-zinc-500 border-b border-zinc-200 dark:border-zinc-700">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Agent</th>
                  <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Session</th>
                  <th
                    className="text-right px-4 py-3 font-medium cursor-pointer select-none"
                    onClick={() => toggleSort('request_count')}
                  >
                    请求数<SortIcon col="request_count" />
                  </th>
                  <th
                    className="text-right px-4 py-3 font-medium cursor-pointer select-none"
                    onClick={() => toggleSort('saved_tokens')}
                  >
                    累计节省 Token<SortIcon col="saved_tokens" />
                  </th>
                  <th
                    className="text-right px-4 py-3 font-medium cursor-pointer select-none"
                    onClick={() => toggleSort('entry_rate')}
                  >
                    产品入口占比<SortIcon col="entry_rate" />
                  </th>
                  <th
                    className="text-right px-4 py-3 font-medium cursor-pointer select-none hidden sm:table-cell"
                    onClick={() => toggleSort('quality_delta_pct')}
                  >
                    质量代理提升<SortIcon col="quality_delta_pct" />
                  </th>
                  <th className="text-center px-4 py-3 font-medium">运行模式</th>
                  <th
                    className="text-right px-4 py-3 font-medium cursor-pointer select-none"
                    onClick={() => toggleSort('last_seen_at')}
                  >
                    最近活动<SortIcon col="last_seen_at" />
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {sorted.map(agent => (
                  <tr key={`${agent.agent_id}-${agent.session_id}`} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
                    <td className="px-4 py-3 font-mono text-zinc-800 dark:text-zinc-200 font-medium">
                      {agent.agent_id}
                    </td>
                    <td className="px-4 py-3 font-mono text-zinc-500 text-[11px] hidden md:table-cell">
                      {agent.session_id}
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-600 dark:text-zinc-400">
                      {agent.request_count.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-emerald-600 dark:text-emerald-400">
                      {agent.saved_tokens.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-zinc-700 dark:text-zinc-300">
                        {Math.round(agent.entry_rate * 100)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-600 dark:text-zinc-400 hidden sm:table-cell">
                      {agent.quality_delta_pct > 0
                        ? <span className="text-blue-600">+{agent.quality_delta_pct.toFixed(1)}%</span>
                        : <span className="text-zinc-400">—</span>
                      }
                    </td>
                    <td className="px-4 py-3 text-center">
                      <ModeBadge mode={agent.mode} />
                    </td>
                    <td className="px-4 py-3 text-right text-zinc-400 text-[11px]">
                      {formatRelativeTime(agent.last_seen_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, unit, accent }: { label: string; value: number; unit: string; accent?: boolean }) {
  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl px-5 py-4">
      <div className="text-[11px] text-zinc-400 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold ${accent ? 'text-emerald-600' : 'text-zinc-900 dark:text-zinc-100'}`}>
        {value.toLocaleString()}{unit}
      </div>
    </div>
  );
}

function ModeBadge({ mode }: { mode: string }) {
  const styles: Record<string, string> = {
    observe: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    guided: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    force_if_possible: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
    off: 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400',
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${styles[mode] ?? styles.off}`}>
      {MODE_LABELS[mode] ?? mode}
    </span>
  );
}
