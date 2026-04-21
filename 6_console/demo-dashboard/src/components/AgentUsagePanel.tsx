import type { AgentUsage } from '../types';
import { normalizeAgentUsageList } from '../utils/familyNormalization';

interface AgentUsagePanelProps {
  agents: AgentUsage[];
  onAgentClick?: (familyId: string) => void;
  /** If provided, observed traffic counts will be shown alongside KPI counts */
  observedCounts?: Record<string, number>;
}

export function AgentUsagePanel({ agents, onAgentClick, observedCounts }: AgentUsagePanelProps) {
  // Normalize and aggregate agent usage by canonical family
  const normalizedAgents = normalizeAgentUsageList(agents);

  if (normalizedAgents.length === 0) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">No agent usage yet</div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Agent Breakdown</h3>
      </div>
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="bg-zinc-50 dark:bg-zinc-800 text-zinc-500">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Family</th>
              <th className="text-right px-4 py-2 font-medium">Qualified</th>
              {observedCounts && <th className="text-right px-4 py-2 font-medium">Observed</th>}
              <th className="text-right px-4 py-2 font-medium">Saved</th>
              <th className="text-right px-4 py-2 font-medium">Ratio</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {normalizedAgents
              .slice()
              .sort((a, b) => {
                // Sort by observed count if available, otherwise by qualified requests
                const aObs = (observedCounts?.[a.family] ?? a.requests);
                const bObs = (observedCounts?.[b.family] ?? b.requests);
                if (bObs !== aObs) return bObs - aObs;
                return b.requests - a.requests;
              })
              .map((agent) => {
                const observed = observedCounts?.[agent.family] ?? null;
                return (
                  <tr
                    key={agent.family}
                    onClick={() => onAgentClick?.(agent.family)}
                    className={onAgentClick ? 'cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-800' : ''}
                  >
                    <td className="px-4 py-2 font-medium text-zinc-700 dark:text-zinc-300">
                      {agent.displayName}
                    </td>
                    <td className="px-4 py-2 text-right text-zinc-600 dark:text-zinc-400">{agent.requests.toLocaleString()}</td>
                    {observed !== null && (
                      <td className="px-4 py-2 text-right text-amber-600 dark:text-amber-400">
                        {observed.toLocaleString()}
                        {observed > agent.requests && (
                          <span className="ml-1 text-[10px] text-amber-400">({observed - agent.requests} non-value)</span>
                        )}
                      </td>
                    )}
                    <td className="px-4 py-2 text-right text-emerald-600">{agent.savedTokens.toLocaleString()}</td>
                    <td className="px-4 py-2 text-right text-zinc-600 dark:text-zinc-400">
                      {Math.round(agent.savingsRatio * 100)}%
                    </td>
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
