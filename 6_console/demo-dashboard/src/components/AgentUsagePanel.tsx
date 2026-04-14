import type { AgentUsage } from '../types';

interface AgentUsagePanelProps {
  agents: AgentUsage[];
}

export function AgentUsagePanel({ agents }: AgentUsagePanelProps) {
  if (agents.length === 0) {
    return (
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6">
        <div className="text-sm text-zinc-400">No agent usage yet</div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-zinc-200 dark:border-zinc-700">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Agent Usage</h3>
      </div>
      <div className="max-h-64 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="bg-zinc-50 dark:bg-zinc-800 text-zinc-500">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Agent</th>
              <th className="text-right px-4 py-2 font-medium">Requests</th>
              <th className="text-right px-4 py-2 font-medium">Saved</th>
              <th className="text-right px-4 py-2 font-medium">Ratio</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {agents
              .slice()
              .sort((a, b) => b.requests - a.requests)
              .map((agent) => (
                <tr key={agent.agent}>
                  <td className="px-4 py-2 font-mono text-zinc-700 dark:text-zinc-300">{agent.agent}</td>
                  <td className="px-4 py-2 text-right text-zinc-600 dark:text-zinc-400">{agent.requests.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right text-emerald-600">{agent.saved_tokens.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right text-zinc-600 dark:text-zinc-400">
                    {Math.round(agent.savings_ratio * 100)}%
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
