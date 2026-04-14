import type { CallChain } from '../types';

interface CallChainVizProps {
  chain: CallChain | null;
  loading: boolean;
}

export function CallChainViz({ chain, loading }: CallChainVizProps) {
  if (loading) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!chain) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">Select a request to see call chain</div>
      </div>
    );
  }

  const totalMs = chain.stages.find(s => s.name === 'engine_total')?.duration_ms ?? 1;

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Call Chain</h3>
        <div className="text-xs text-zinc-400 mt-0.5">
          trace_id: <span className="font-mono">{chain.trace_id}</span>
        </div>
      </div>

      <div className="p-6">
        {/* Timeline visualization */}
        <div className="flex items-center gap-0 mb-6">
          {chain.stages.map((stage) => {
            const widthPct = Math.max(2, (stage.duration_ms / totalMs) * 100);
            return (
              <div
                key={stage.name}
                className="relative group"
                style={{ width: `${widthPct}%`, minWidth: '30px' }}
              >
                <div
                  className="h-8 flex items-center justify-center text-[10px] font-mono text-white rounded-sm"
                  style={{ backgroundColor: stageColor(stage.name) }}
                  title={`${stage.name}: ${stage.duration_ms.toFixed(3)}ms`}
                >
                  {stage.name}
                </div>
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-zinc-900 text-white text-[10px] rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                  {stage.name}: {stage.duration_ms.toFixed(3)}ms
                </div>
              </div>
            );
          })}
        </div>

        {/* Stage list */}
        <div className="space-y-2">
          {chain.stages.map((stage) => {
            const barPct = Math.max(1, (stage.duration_ms / totalMs) * 100);
            return (
              <div key={stage.name} className="flex items-center gap-3">
                <div className="w-20 text-xs font-mono text-zinc-500 text-right truncate">{stage.name}</div>
                <div className="flex-1 bg-zinc-100 dark:bg-zinc-800 rounded-sm h-5 relative overflow-hidden">
                  <div
                    className="absolute left-0 top-0 h-full rounded-sm opacity-80"
                    style={{ width: `${barPct}%`, backgroundColor: stageColor(stage.name) }}
                  />
                </div>
                <div className="w-20 text-xs font-mono text-zinc-600 dark:text-zinc-400">
                  {stage.duration_ms.toFixed(3)}ms
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function stageColor(name: string): string {
  const colors: Record<string, string> = {
    engine_total: '#6366f1',
    filter: '#3b82f6',
    route_score: '#8b5cf6',
    dedup: '#ec4899',
    select: '#f59e0b',
    pack: '#10b981',
    meter: '#64748b',
    policy_eval: '#ef4444',
    backend_search: '#f97316',
  };
  return colors[name] ?? '#64748b';
}
