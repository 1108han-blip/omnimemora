import type { AgentControlCard, RecentRequest } from '../types';
import { normalizeFamilyName, isInternalEvent, rankRecentRequests } from '../utils/familyNormalization';

interface LiveRequestFlowProps {
  requests: RecentRequest[];
  onSelect: (request: RecentRequest) => void;
  selectedRequestId?: string | null;
  runningAgents?: AgentControlCard[];
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

function hasMemoryHit(req: RecentRequest): boolean {
  return (req.packed_memory_count ?? 0) > 0 || (req.local_cards_used ?? 0) > 0 || (req.remote_used_count ?? 0) > 0;
}

function hasRefinement(req: RecentRequest): boolean {
  const sourceTokens = req.compression_source_tokens ?? 0;
  const outputTokens = req.compression_output_tokens ?? 0;
  return sourceTokens > 0 && outputTokens > 0 && outputTokens < sourceTokens;
}

function hasRealInputSavings(req: RecentRequest): boolean {
  return (req.real_input_saved_tokens ?? 0) > 0 || (req.real_input_savings_ratio ?? 0) > 0;
}

function decisionTags(req: RecentRequest): string[] {
  if (req.bypass) return ['绕过'];
  const tags = [];
  if (hasRefinement(req)) tags.push('精练');
  if (hasMemoryHit(req)) tags.push('记忆');
  return tags.length > 0 ? tags : ['无'];
}

export function LiveRequestFlow({ requests, onSelect, selectedRequestId = null, runningAgents = [] }: LiveRequestFlowProps) {
  // Filter out internal events and normalize agent names
  const userFacingRequests = requests.filter(req => req.request_class !== 'internal' && !isInternalEvent(req.query, req.agent));
  const normalizedRequests = rankRecentRequests(userFacingRequests).map(req => ({
    ...req,
    agent: normalizeFamilyName(req.agent),
  }));
  const displayedRequests = normalizedRequests.slice(0, 10);

  if (displayedRequests.length === 0) {
    const running = runningAgents.filter(agent => agent.process_running);
    if (running.length > 0) {
      return (
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
          <div className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Client running, no product request yet</div>
          <div className="mt-3 flex flex-wrap gap-2">
            {running.map(agent => (
              <span
                key={agent.family_id}
                className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
              >
                {normalizeFamilyName(agent.family_id)}
              </span>
            ))}
          </div>
        </div>
      );
    }
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
        <span className="text-xs text-zinc-400">
          {displayedRequests.length} user-visible requests
          {runningAgents.some(agent => agent.process_running) ? ` / ${runningAgents.filter(agent => agent.process_running).length} running` : ''}
        </span>
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
              <span className={valueBadgeClass(req)}>
                {valueBadgeLabel(req)}
              </span>
              <span className="flex items-center gap-1">
                {decisionTags(req).map(tag => (
                  <span
                    key={tag}
                    className={`rounded border px-1.5 py-0.5 text-[10px] ${
                      tag === '精练' ? 'border-indigo-300 text-indigo-600 dark:border-indigo-700 dark:text-indigo-300' :
                      tag === '记忆' ? 'border-emerald-300 text-emerald-600 dark:border-emerald-700 dark:text-emerald-300' :
                      tag === '绕过' ? 'border-amber-300 text-amber-600 dark:border-amber-700 dark:text-amber-300' :
                      'border-zinc-200 text-zinc-400 dark:border-zinc-700 dark:text-zinc-500'
                    }`}
                  >
                    {tag}
                  </span>
                ))}
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
              <span className="text-zinc-300 truncate max-w-[240px]" title={requestDisplayText(req)}>
                {requestDisplayText(req)}
              </span>
            </div>
            {req.request_class !== 'value_qualified' && req.qualification_reason && (
              <div className="mt-1 truncate text-[10px] text-amber-600 dark:text-amber-300">
                No memory was used because {req.qualification_reason}.
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

function requestDisplayText(req: RecentRequest): string {
  const visible = (req.user_visible_query || req.query || '').trim();
  if (visible) return visible;
  return req.diagnostic_label || 'wrapper/context envelope';
}

function valueBadgeLabel(req: RecentRequest): string {
  if (req.bypass) return 'bypass';
  if (hasRealInputSavings(req)) {
    return `real saving ${formatRatioPct(req.real_input_savings_ratio ?? 0)}`;
  }
  if ((req.compression_ratio ?? req.savings_ratio ?? 0) > 0) {
    return `compression ${formatRatioPct(req.compression_ratio ?? req.savings_ratio)}`;
  }
  return req.diagnostic_label || 'not helping yet';
}

function valueBadgeClass(req: RecentRequest): string {
  if (req.bypass) return 'text-amber-600';
  if (hasRealInputSavings(req)) {
    return 'text-emerald-600';
  }
  if ((req.compression_ratio ?? req.savings_ratio ?? 0) > 0) return 'text-indigo-500';
  return 'text-zinc-500';
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
