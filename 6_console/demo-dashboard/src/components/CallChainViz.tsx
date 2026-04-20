import type { RequestEvidence } from '../types';

interface CallChainVizProps {
  evidence: RequestEvidence | null;
  loading: boolean;
}

export function CallChainViz({ evidence, loading }: CallChainVizProps) {
  if (loading) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!evidence || !evidence.chain) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">Select a request to see call chain</div>
      </div>
    );
  }

  const chain = evidence.chain;
  const nodes = chain.nodes;
  const totalMs = nodes.reduce((sum, n) => sum + n.duration_ms, 0) || 1;

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
          {nodes.map((node) => {
            const widthPct = Math.max(2, (node.duration_ms / totalMs) * 100);
            return (
              <div
                key={node.id}
                className="relative group"
                style={{ width: `${widthPct}%`, minWidth: '30px' }}
              >
                <div
                  className="h-8 flex items-center justify-center text-[10px] font-mono text-white rounded-sm"
                  style={{ backgroundColor: nodeStatusColor(node.status) }}
                  title={`${node.label}: ${node.duration_ms.toFixed(3)}ms`}
                >
                  {node.label}
                </div>
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-zinc-900 text-white text-[10px] rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-10">
                  {node.note}
                </div>
              </div>
            );
          })}
        </div>

        {/* Node list */}
        <div className="space-y-2">
          {nodes.map((node) => {
            const barPct = Math.max(1, (node.duration_ms / totalMs) * 100);
            return (
              <div key={node.id} className="flex items-center gap-3">
                <div className="w-24 text-xs font-mono text-zinc-500 text-right truncate">{node.label}</div>
                <div className="flex-1 bg-zinc-100 dark:bg-zinc-800 rounded-sm h-5 relative overflow-hidden">
                  <div
                    className="absolute left-0 top-0 h-full rounded-sm opacity-80"
                    style={{ width: `${barPct}%`, backgroundColor: nodeStatusColor(node.status) }}
                  />
                </div>
                <div className="w-20 text-xs font-mono text-zinc-600 dark:text-zinc-400">
                  {node.duration_ms.toFixed(3)}ms
                </div>
                <div className={`w-16 text-xs font-medium text-center px-1 py-0.5 rounded ${
                  node.status === 'success' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300' :
                  node.status === 'warning' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300' :
                  node.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' :
                  node.status === 'bypassed' ? 'bg-zinc-100 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300' :
                  'bg-zinc-100 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400'
                }`}>
                  {node.status}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function nodeStatusColor(status: string): string {
  const colors: Record<string, string> = {
    success: '#10b981',
    warning: '#f59e0b',
    failed: '#ef4444',
    bypassed: '#64748b',
    not_used: '#94a3b8',
  };
  return colors[status] ?? '#64748b';
}
