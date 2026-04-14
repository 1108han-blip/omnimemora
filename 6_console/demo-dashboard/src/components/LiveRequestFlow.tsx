import type { RecentRequest } from '../types';

interface LiveRequestFlowProps {
  requests: RecentRequest[];
  onSelect: (request: RecentRequest) => void;
}

export function LiveRequestFlow({ requests, onSelect }: LiveRequestFlowProps) {
  if (requests.length === 0) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">No recent requests</div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Live Request Flow</h3>
      </div>
      <div className="divide-y divide-zinc-100 dark:divide-zinc-800 max-h-64 overflow-y-auto">
        {requests.map((req) => (
          <button
            key={req.request_id}
            onClick={() => onSelect(req)}
            className="w-full text-left px-6 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors text-xs font-mono"
          >
            <div className="flex items-center justify-between gap-4">
              <span className="text-zinc-400">{formatTime(req.timestamp)}</span>
              <span className={req.bypass ? 'text-amber-600' : 'text-emerald-600'}>
                {req.bypass ? 'bypass' : `saved ${Math.round(req.savings_ratio * 100)}%`}
              </span>
              <span className="text-zinc-500">{req.packed_memory_count} mems</span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                req.task_type === 'implementation' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' :
                req.task_type === 'decision' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300' :
                'bg-zinc-100 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300'
              }`}>
                {req.task_type}
              </span>
              <span className="text-zinc-300 truncate max-w-[200px]">{req.query || req.request_id}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return ts;
  }
}
