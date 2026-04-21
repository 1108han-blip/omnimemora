import type { RecentRequest } from '../types';
import { normalizeFamilyName, isInternalEvent, rankRecentRequests } from '../utils/familyNormalization';

interface LiveRequestFlowProps {
  requests: RecentRequest[];
  onSelect: (request: RecentRequest) => void;
  selectedRequestId?: string | null;
}

function requestClassLabel(cls: RecentRequest['request_class']): string {
  if (cls === 'value_qualified') return 'qualified';
  if (cls === 'task_non_value') return 'non-value';
  return 'internal';
}

function requestClassColor(cls: RecentRequest['request_class']): string {
  if (cls === 'value_qualified') return 'text-emerald-600 dark:text-emerald-400';
  if (cls === 'task_non_value') return 'text-amber-600 dark:text-amber-400';
  return 'text-zinc-400 dark:text-zinc-500';
}

export function LiveRequestFlow({ requests, onSelect, selectedRequestId = null }: LiveRequestFlowProps) {
  // Filter out internal events and normalize agent names
  const userFacingRequests = requests.filter(req => !isInternalEvent(req.query, req.agent));
  const normalizedRequests = rankRecentRequests(userFacingRequests).map(req => ({
    ...req,
    agent: normalizeFamilyName(req.agent),
  }));
  const displayedRequests = normalizedRequests.slice(0, 10);

  if (displayedRequests.length === 0) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">No recent task requests</div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Live Request Flow</h3>
        <span className="text-xs text-zinc-400">{displayedRequests.length} task requests</span>
      </div>
      <div className="divide-y divide-zinc-100 dark:divide-zinc-800 max-h-64 overflow-y-auto">
        {displayedRequests.map((req) => (
          <button
            key={req.request_id}
            onClick={() => onSelect(req)}
            className={`w-full text-left px-6 py-3 transition-colors text-xs font-mono ${
              req.request_id === selectedRequestId
                ? 'bg-blue-50 dark:bg-blue-950 border-l-2 border-blue-500'
                : 'hover:bg-zinc-50 dark:hover:bg-zinc-800'
            }`}
          >
            <div className="flex items-center justify-between gap-4">
              <span className="text-zinc-400">{formatTime(req.timestamp)}</span>
              <span className="font-medium text-zinc-600 dark:text-zinc-300">{req.agent}</span>
              <span className={req.bypass ? 'text-amber-600' : 'text-emerald-600'}>
                {req.bypass ? 'bypass' : `saved ${formatRatioPct(req.savings_ratio)}`}
              </span>
              <span className="text-zinc-500">{req.packed_memory_count} mems</span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                normalizeTaskType(req.task_type) === 'implementation' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' :
                normalizeTaskType(req.task_type) === 'decision' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300' :
                'bg-zinc-100 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-300'
              }`}>
                {normalizeTaskType(req.task_type)}
              </span>
              <span className={`text-[10px] font-medium ${requestClassColor(req.request_class)}`}>
                [{requestClassLabel(req.request_class)}]
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

function formatRatioPct(ratio: number): string {
  const safeRatio = Math.max(0, Math.min(1, Number.isFinite(ratio) ? ratio : 0));
  if (safeRatio >= 1) return '100%';
  const rounded = Math.round(safeRatio * 1000) / 10;
  const capped = Math.min(99.9, rounded);
  return Number.isInteger(capped) ? `${capped.toFixed(0)}%` : `${capped.toFixed(1)}%`;
}

function normalizeTaskType(taskType: string): string {
  if (!taskType || taskType === 'unknown') return 'request';
  return taskType;
}
