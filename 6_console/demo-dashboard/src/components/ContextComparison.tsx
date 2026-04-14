import type { ContextDiff } from '../types';

interface ContextComparisonProps {
  diff: ContextDiff | null;
  loading: boolean;
}

export function ContextComparison({ diff, loading }: ContextComparisonProps) {
  if (loading) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!diff) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">Select a request to see context comparison</div>
      </div>
    );
  }

  const savedTokens = diff.before_tokens - diff.after_tokens;
  const savingsPct = diff.before_tokens > 0 ? Math.round((savedTokens / diff.before_tokens) * 100) : 0;

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Context Before / After</h3>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-zinc-400">
            <span className="font-mono text-red-500">{diff.before_tokens}</span> tokens before
          </span>
          <span className="text-emerald-500">→</span>
          <span className="text-zinc-400">
            <span className="font-mono text-emerald-600">{diff.after_tokens}</span> tokens after
          </span>
          <span className="font-semibold text-emerald-600">-{savingsPct}%</span>
        </div>
      </div>

      <div className="grid grid-cols-2 divide-x divide-zinc-100 dark:divide-zinc-800">
        {/* BEFORE */}
        <div>
          <div className="px-4 py-2 bg-red-50 dark:bg-red-950 border-b border-zinc-200 dark:border-zinc-700">
            <span className="text-xs font-semibold text-red-600 dark:text-red-400">
              BEFORE ({diff.selected_memories.length + diff.dropped_memories.length} candidates)
            </span>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {[...diff.selected_memories, ...diff.dropped_memories].map((mem, i) => (
              <div key={mem.uri || i} className="px-4 py-2 border-b border-zinc-50 dark:border-zinc-800 last:border-0">
                <div className="text-[10px] font-mono text-zinc-400 truncate">{mem.uri}</div>
                <div className="text-xs text-zinc-700 dark:text-zinc-300 mt-0.5 line-clamp-2">
                  {mem.content || mem.abstract || '(no content)'}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] px-1 bg-zinc-100 dark:bg-zinc-700 rounded text-zinc-500">
                    {mem.category}
                  </span>
                  {diff.selected_memories.includes(mem) && (
                    <span className="text-[10px] text-emerald-600 font-medium">✓ selected</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* AFTER */}
        <div>
          <div className="px-4 py-2 bg-emerald-50 dark:bg-emerald-950 border-b border-zinc-200 dark:border-zinc-700">
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              AFTER ({diff.selected_memories.length} selected)
            </span>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {diff.selected_memories.map((mem, i) => (
              <div key={mem.uri || i} className="px-4 py-2 border-b border-zinc-50 dark:border-zinc-800 last:border-0">
                <div className="text-[10px] font-mono text-zinc-400 truncate">{mem.uri}</div>
                <div className="text-xs text-zinc-700 dark:text-zinc-300 mt-0.5 line-clamp-2">
                  {mem.content || mem.abstract || '(no content)'}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] px-1 bg-emerald-100 dark:bg-emerald-900 rounded text-emerald-700 dark:text-emerald-300">
                    score={mem._final_score ?? mem.score ?? 0}
                  </span>
                  <span className="text-[10px] px-1 bg-zinc-100 dark:bg-zinc-700 rounded text-zinc-500">
                    {mem.category}
                  </span>
                </div>
              </div>
            ))}
            {diff.selected_memories.length === 0 && (
              <div className="px-4 py-4 text-xs text-zinc-400">No memories selected (bypass)</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
