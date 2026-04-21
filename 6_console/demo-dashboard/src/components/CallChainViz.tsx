import type { RequestEvidence, NodeStatus } from '../types';

interface CallChainVizProps {
  evidence: RequestEvidence | null;
  loading: boolean;
}

const PRODUCT_NODE_ORDER = [
  'app_request',
  'entry_18011',
  'route_decision',
  'memory_recall',
  'context_pack',
  'compile_or_bypass',
  'upstream_forward',
  'response_recorded',
];

const NODE_LABELS: Record<string, string> = {
  app_request: 'Request',
  entry_18011: 'Entry',
  route_decision: 'Routing',
  memory_recall: 'Memory Recall',
  context_pack: 'Context Pack',
  compile_or_bypass: 'Compile',
  upstream_forward: 'Upstream',
  response_recorded: 'Response',
};

function nodeStatusColor(status: NodeStatus): string {
  const colors: Record<NodeStatus, string> = {
    success: '#10b981',
    warning: '#f59e0b',
    failed: '#ef4444',
    bypassed: '#64748b',
    not_used: '#94a3b8',
  };
  return colors[status] ?? '#64748b';
}

function statusBgClass(status: NodeStatus): string {
  switch (status) {
    case 'success':
      return 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300';
    case 'warning':
      return 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300';
    case 'failed':
      return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300';
    case 'bypassed':
      return 'bg-zinc-100 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300';
    case 'not_used':
    default:
      return 'bg-zinc-100 text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400';
  }
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
  const nodeMap = new Map(chain.nodes.map(n => [n.id, n]));
  const orderedNodes = PRODUCT_NODE_ORDER.map(id => nodeMap.get(id)).filter(Boolean) as typeof chain.nodes;

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Call Chain</h3>
        <div className="text-xs text-zinc-400 mt-0.5">
          trace_id: <span className="font-mono">{chain.trace_id}</span>
        </div>
      </div>

      <div className="p-6">
        <div className="space-y-1.5">
          {orderedNodes.map((node) => (
            <div key={node.id} className="flex items-center gap-2 text-[10px]">
              <div
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ backgroundColor: nodeStatusColor(node.status) }}
              />
              <span className="w-20 font-mono text-zinc-500 truncate">{NODE_LABELS[node.id] ?? node.id}</span>
              <span className="flex-1 text-zinc-400 truncate">{node.note}</span>
              <span className="w-12 font-mono text-zinc-500 text-right">{node.duration_ms.toFixed(1)}ms</span>
              <span className={`w-14 text-center px-1 py-0.5 rounded ${statusBgClass(node.status)}`}>
                {node.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}