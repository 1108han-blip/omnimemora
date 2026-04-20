import type {
  MetricsSummary,
  MetricsTrend,
  RecentRequestsResponse,
  ContextDiff,
  CallChain,
  UsageSummary,
  LiveAgent,
  AgentControlCard,
  AgentControlResponse,
} from './types';

const API_BASE = '';

export async function fetchMetricsSummary(tenant: string = 'all'): Promise<MetricsSummary> {
  const r = await fetch(`${API_BASE}/metrics/summary?tenant=${encodeURIComponent(tenant)}`);
  if (!r.ok) throw new Error(`Failed to fetch metrics: ${r.statusText}`);
  return r.json();
}

export async function fetchMetricsSummary24h(tenant: string = 'all'): Promise<MetricsSummary> {
  const r = await fetch(`${API_BASE}/metrics/summary_24h?tenant=${encodeURIComponent(tenant)}`);
  if (!r.ok) throw new Error(`Failed to fetch 24h metrics: ${r.statusText}`);
  return r.json();
}

export async function fetchMetricsTrend(tenant: string = 'all', days: number = 7): Promise<MetricsTrend> {
  const r = await fetch(`${API_BASE}/usage/token-savings/trend?tenant=${encodeURIComponent(tenant)}&days=${days}`);
  if (!r.ok) throw new Error(`Failed to fetch trend: ${r.statusText}`);
  const raw = await r.json();
  return {
    tenant: raw.tenant,
    days: raw.days ?? days,
    trend: (raw.trend ?? []).map((p: Record<string, unknown>) => ({
      date: p.date as string,
      requests: p.requests as number,
      saved_tokens: p.saved_tokens as number,
      savings_ratio: p.savings_ratio as number,
    })),
  };
}

export async function fetchRecentRequests(tenant: string = 'default', limit = 20): Promise<RecentRequestsResponse> {
  const r = await fetch(`${API_BASE}/metrics/recent_requests?tenant=${encodeURIComponent(tenant)}&limit=${limit}`);
  if (!r.ok) throw new Error(`Failed to fetch recent requests: ${r.statusText}`);
  return r.json();
}

export async function fetchUsageSummary(tenant: string = 'all'): Promise<UsageSummary> {
  const r = await fetch(`${API_BASE}/usage/token-savings?tenant=${encodeURIComponent(tenant)}`);
  if (!r.ok) throw new Error(`Failed to fetch usage summary: ${r.statusText}`);
  const raw = await r.json();
  return {
    tenant: raw.tenant,
    request_count: raw.request_count ?? 0,
    total_requests: raw.total_requests ?? 0,
    saved_tokens_total: raw.saved_tokens_total ?? raw.saved_tokens_estimate_total ?? 0,
    average_savings_ratio: raw.average_savings_ratio ?? 0,
    last_request_at: raw.last_request_at ?? null,
    by_agent: (raw.by_agent ?? []).map((entry: Record<string, unknown>) => ({
      agent: (entry.agent as string) ?? 'unknown',
      requests: (entry.requests as number) ?? 0,
      saved_tokens: (entry.saved_tokens as number) ?? 0,
      savings_ratio: (entry.savings_ratio as number) ?? 0,
      last_request_at: (entry.last_request_at as string | null) ?? null,
    })),
  };
}

export async function fetchTenants(): Promise<string[]> {
  const r = await fetch(`${API_BASE}/metrics/tenants`);
  if (!r.ok) throw new Error(`Failed to fetch tenants: ${r.statusText}`);
  const data = await r.json();
  return data.tenants ?? [];
}

export async function fetchContextDiff(requestId: string): Promise<ContextDiff> {
  const r = await fetch(`${API_BASE}/debug/context_diff?request_id=${encodeURIComponent(requestId)}`);
  if (!r.ok) throw new Error(`Failed to fetch context diff: ${r.statusText}`);
  return r.json();
}

export async function fetchCallChain(requestId: string): Promise<CallChain> {
  const r = await fetch(`${API_BASE}/debug/call_chain?request_id=${encodeURIComponent(requestId)}`);
  if (!r.ok) throw new Error(`Failed to fetch call chain: ${r.statusText}`);
  return r.json();
}

export async function fetchLiveAgents(windowMinutes = 30): Promise<LiveAgent[]> {
  const r = await fetch(`${API_BASE}/agents/live?window_minutes=${windowMinutes}`);
  if (!r.ok) throw new Error(`Failed to fetch live agents: ${r.statusText}`);
  const data = await r.json();
  return data.agents ?? [];
}

export async function fetchAgentMetrics(agentId?: string): Promise<LiveAgent[]> {
  const params = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : '';
  const r = await fetch(`${API_BASE}/agents/metrics${params}`);
  if (!r.ok) throw new Error(`Failed to fetch agent metrics: ${r.statusText}`);
  const data = await r.json();
  return data.metrics ?? [];
}

export async function fetchAgentControls(): Promise<AgentControlResponse> {
  const r = await fetch(`${API_BASE}/agents/control`);
  if (!r.ok) throw new Error(`Failed to fetch agent controls: ${r.statusText}`);
  return r.json();
}

export async function rescanAgentControls(): Promise<AgentControlResponse> {
  const r = await fetch(`${API_BASE}/agents/control/rescan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!r.ok) throw new Error(`Failed to rescan agent controls: ${r.statusText}`);
  return r.json();
}

async function postAgentControlAction(action: 'install' | 'uninstall' | 'enable' | 'disable', familyId: string): Promise<AgentControlCard> {
  const r = await fetch(`${API_BASE}/agents/control/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ family_id: familyId }),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(detail || `Failed to ${action} ${familyId}`);
  }
  return r.json();
}

export function installAgent(familyId: string): Promise<AgentControlCard> {
  return postAgentControlAction('install', familyId);
}

export function uninstallAgent(familyId: string): Promise<AgentControlCard> {
  return postAgentControlAction('uninstall', familyId);
}

export function enableAgentRoute(familyId: string): Promise<AgentControlCard> {
  return postAgentControlAction('enable', familyId);
}

export function disableAgentRoute(familyId: string): Promise<AgentControlCard> {
  return postAgentControlAction('disable', familyId);
}
