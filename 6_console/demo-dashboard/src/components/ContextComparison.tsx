import type { RequestEvidence } from '../types';

interface MemorySummary {
  uri: string;
  content: string;
  category: string;
  selected: boolean;
}

function toSummary(mem: RequestEvidence['context']['selected_memories'][0], selected: boolean): MemorySummary {
  return {
    uri: mem.uri,
    content: mem.content || mem.abstract || '(no content)',
    category: mem.category,
    selected,
  };
}

interface ContextComparisonProps {
  evidence: RequestEvidence | null;
  loading: boolean;
}

export function ContextComparison({ evidence, loading }: ContextComparisonProps) {
  if (loading) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">Loading...</div>
      </div>
    );
  }

  if (!evidence || !evidence.context) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">Select a request to see context comparison</div>
      </div>
    );
  }

  const ctx = evidence.context;
  const compressionBefore = ctx.compression?.source_tokens ?? ctx.before_tokens;
  const compressionAfter = ctx.compression?.output_tokens ?? ctx.after_tokens;
  const compressionSaved = Math.max(0, compressionBefore - compressionAfter);
  const compressionPct = compressionBefore > 0 ? Math.round((compressionSaved / compressionBefore) * 100) : 0;
  const realInput = ctx.real_input;

  // BEFORE: all candidates (selected + dropped)
  const beforeMemories: MemorySummary[] = [
    ...ctx.selected_memories.map(m => toSummary(m, true)),
    ...ctx.dropped_memories.map(m => toSummary(m, false)),
  ];

  // AFTER: only selected
  const afterMemories: MemorySummary[] = ctx.selected_memories.map(m => toSummary(m, true));

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Context Refinement / Real Input</h3>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-zinc-400">
            <span className="font-mono text-red-500">{compressionBefore}</span> compression source
          </span>
          <span className="text-emerald-500">→</span>
          <span className="text-zinc-400">
            <span className="font-mono text-emerald-600">{compressionAfter}</span> output
          </span>
          <span className="font-semibold text-indigo-600">-{compressionPct}% refined</span>
          {realInput && realInput.saved_tokens > 0 && (
            <span className="font-semibold text-emerald-600">
              {realInput.saved_tokens} real input saved
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 divide-x divide-zinc-100 dark:divide-zinc-800">
        {/* BEFORE */}
        <div>
          <div className="px-4 py-2 bg-red-50 dark:bg-red-950 border-b border-zinc-200 dark:border-zinc-700">
            <span className="text-xs font-semibold text-red-600 dark:text-red-400">
              BEFORE ({beforeMemories.length} candidates)
            </span>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {beforeMemories.map((mem, i) => (
              <div key={mem.uri || i} className="px-4 py-2 border-b border-zinc-50 dark:border-zinc-800 last:border-0">
                <div className="text-[10px] font-mono text-zinc-400 truncate">{mem.uri}</div>
                <div className="text-xs text-zinc-700 dark:text-zinc-300 mt-0.5 line-clamp-2">
                  {mem.content}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] px-1 bg-zinc-100 dark:bg-zinc-700 rounded text-zinc-500">
                    {mem.category}
                  </span>
                  {mem.selected && (
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
              AFTER ({afterMemories.length} selected)
            </span>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {afterMemories.map((mem, i) => (
              <div key={mem.uri || i} className="px-4 py-2 border-b border-zinc-50 dark:border-zinc-800 last:border-0">
                <div className="text-[10px] font-mono text-zinc-400 truncate">{mem.uri}</div>
                <div className="text-xs text-zinc-700 dark:text-zinc-300 mt-0.5 line-clamp-2">
                  {mem.content}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] px-1 bg-zinc-100 dark:bg-zinc-700 rounded text-zinc-500">
                    {mem.category}
                  </span>
                </div>
              </div>
            ))}
            {afterMemories.length === 0 && (
              <div className="px-4 py-4 text-xs text-zinc-400">No memories selected (bypass)</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
