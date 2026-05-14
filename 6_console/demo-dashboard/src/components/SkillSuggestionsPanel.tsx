import type { RequestEvidence } from '../types';

interface SkillSuggestionsPanelProps {
  evidence: RequestEvidence | null;
  loading: boolean;
}

function formatConfidence(value: number): string {
  const bounded = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  return `${Math.round(bounded * 100)}%`;
}

function buildPolicyLine(evidence: RequestEvidence): string {
  const name = evidence.skill_policy_name ?? 'unknown';
  const version = evidence.skill_policy_version ?? 'unknown';
  const source = evidence.skill_policy_source ?? 'unknown';
  const status = evidence.skill_policy_status ?? 'unknown';
  return `policy: ${name} / ${version} / ${source} / ${status}`;
}

function suggestionKey(item: RequestEvidence['skill_suggestions'][number]): string {
  return [item.skill_id, item.source, item.title].join(':');
}

export function SkillSuggestionsPanel({ evidence, loading }: SkillSuggestionsPanelProps) {
  if (loading) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!evidence) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Suggested Skills</h3>
        <p className="text-xs text-zinc-500 mt-1">Advisory only; not executed automatically</p>
        <div className="text-sm text-zinc-400 mt-4">Select a request to see suggested skills</div>
      </div>
    );
  }

  const suggestions = evidence.skill_suggestions ?? [];
  const taskType = (evidence.request?.task_type ?? '').toLowerCase();
  const policyLine = buildPolicyLine(evidence);
  const isInvalidSnapshot = evidence.skill_policy_status === 'invalid_snapshot';

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Suggested Skills</h3>
        <p className="text-xs text-zinc-500 mt-1">Advisory only; not executed automatically</p>
        <p className="text-[11px] text-zinc-400 mt-2 font-mono">{policyLine}</p>
        {isInvalidSnapshot && (
          <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-1">
            Policy snapshot invalid; fell back to local policy
          </p>
        )}
      </div>

      <div className="p-6">
        {taskType === 'implementation' && suggestions.length === 0 && (
          <div className="text-sm text-zinc-400">No skill suggestions for implementation tasks</div>
        )}

        {taskType !== 'implementation' && suggestions.length === 0 && (
          <div className="text-sm text-zinc-400">No suggestions for this request</div>
        )}

        {suggestions.length > 0 && (
          <div className="space-y-3">
            {suggestions.map((item) => (
              <div
                key={suggestionKey(item)}
                className="border border-zinc-200 dark:border-zinc-700 rounded-lg p-3 bg-zinc-50/60 dark:bg-zinc-800/50"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-zinc-700 dark:text-zinc-200">{item.title}</div>
                  <div className="text-xs font-mono text-emerald-600 dark:text-emerald-400">
                    {formatConfidence(item.confidence)}
                  </div>
                </div>
                <div className="text-xs text-zinc-500 mt-1">{item.reason}</div>
                <div className="text-[11px] text-zinc-400 mt-2 font-mono">
                  {item.skill_id} · {item.source}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
