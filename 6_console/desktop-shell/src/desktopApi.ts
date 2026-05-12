import type {
  AgentControlResponse,
  AgentId,
  AgentStatus,
  AgentControlCard,
  CoreCapabilitiesResponse,
  CoreCapabilitiesTrendResponse,
  DesktopCommandResult,
  DesktopStatus,
  ProductConsoleSnapshot,
  RecentRequestsResponse,
  RequestEvidence,
  UsageSummary,
} from './types';

const PRODUCT_API_BASE = 'http://127.0.0.1:18011';
const PRODUCT_METRICS_TIMEOUT_MS = 6000;
const AGENT_CONTROL_TIMEOUT_MS = 6000;
const RECENT_REQUESTS_TIMEOUT_MS = 6000;

const DEFAULT_STATUS: DesktopStatus = {
  app_version: '1.0.0-beta.13',
  data_dir: '~/.omnimemora/app/current',
  services: [
    {
      name: 'runtime',
      port: 8765,
      state: 'unknown',
      url: 'http://127.0.0.1:8765/health',
      detail: 'Waiting for desktop host status.',
      managed_by_desktop: false,
      pid: null,
    },
    {
      name: 'adapter',
      port: 18011,
      state: 'unknown',
      url: 'http://127.0.0.1:18011/health',
      detail: 'Waiting for desktop host status.',
      managed_by_desktop: false,
      pid: null,
    },
  ],
  updates: [
    {
      layer: 'desktop_shell',
      current_version: '1.0.0-beta.13',
      available_version: null,
      status: 'not_checked',
      detail: 'Desktop shell updates are checked through the official release manifest.',
    },
    {
      layer: 'local_components',
      current_version: '1.0.0-beta.13',
      available_version: null,
      status: 'not_checked',
      detail: 'Local component updates use release manifests.',
    },
    {
      layer: 'cloud_policy',
      current_version: 'local-active',
      available_version: null,
      status: 'not_checked',
      detail: 'Cloud policy candidates never auto-promote.',
    },
  ],
  feedback_email: 'support@doloclaw.com',
};

async function invokeDesktop<T>(command: string): Promise<T> {
  if (!('__TAURI_INTERNALS__' in window)) {
    return Promise.reject(new Error('Tauri host is not available in browser preview.'));
  }
  const mod = await import('@tauri-apps/api/core');
  return mod.invoke<T>(command);
}

export async function getDesktopStatus(): Promise<DesktopStatus> {
  try {
    return await invokeDesktop<DesktopStatus>('get_desktop_status');
  } catch {
    return DEFAULT_STATUS;
  }
}

export async function runDesktopCommand(command: 'start_services' | 'stop_services' | 'restart_services' | 'check_for_updates' | 'install_desktop_update' | 'install_update' | 'rollback'): Promise<DesktopCommandResult> {
  try {
    return await invokeDesktop<DesktopCommandResult>(command);
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : String(error),
      status: DEFAULT_STATUS,
    };
  }
}

const DEFAULT_AGENTS: AgentStatus[] = [
  {
    id: 'claude',
    name: 'Claude Code',
    state: 'not_found',
    installed: false,
    running: false,
    attached: false,
    supported: true,
    experimental: false,
    detail: 'Open the desktop app to scan this Mac and connect Claude Code.',
    config_path: '~/.claude/settings.json',
  },
  {
    id: 'openclaw',
    name: 'OpenClaw',
    state: 'not_found',
    installed: false,
    running: false,
    attached: false,
    supported: true,
    experimental: false,
    detail: 'Open the desktop app to scan this Mac and connect OpenClaw.',
    config_path: '~/.openclaw/openclaw.json',
  },
  {
    id: 'codex',
    name: 'Codex',
    state: 'not_found',
    installed: false,
    running: false,
    attached: false,
    supported: true,
    experimental: true,
    detail: 'Codex is experimental and stays off by default.',
    config_path: '~/.codex/config.toml',
  },
];

export async function scanAgents(): Promise<AgentStatus[]> {
  try {
    return await invokeDesktop<AgentStatus[]>('scan_agents');
  } catch {
    return DEFAULT_AGENTS;
  }
}

export async function runAgentCommand(command: 'attach_agent' | 'detach_agent', agent: AgentId): Promise<DesktopCommandResult> {
  try {
    const mod = await import('@tauri-apps/api/core');
    return await mod.invoke<DesktopCommandResult>(command, { agent });
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : String(error),
      status: DEFAULT_STATUS,
    };
  }
}

async function fetchProductJson<T>(path: string, timeoutMs = 2200): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${PRODUCT_API_BASE}${path}`, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`${path} returned ${response.status}`);
    }
    return response.json();
  } finally {
    window.clearTimeout(timer);
  }
}

function emptyUsageSummary(): UsageSummary {
  return {
    tenant: 'all',
    request_count: 0,
    total_requests: 0,
    saved_tokens_total: 0,
    average_savings_ratio: 0,
    last_request_at: null,
    by_agent: [],
  };
}

function realInputSavedTokens(request: RecentRequestsResponse['requests'][number]): number {
  if (typeof request.real_input_saved_tokens === 'number') return Math.max(0, request.real_input_saved_tokens);
  if (typeof request.baseline_payload_tokens === 'number' && typeof request.forwarded_payload_tokens === 'number') {
    return Math.max(0, request.baseline_payload_tokens - request.forwarded_payload_tokens);
  }
  return 0;
}

function realInputBaselineTokens(request: RecentRequestsResponse['requests'][number]): number {
  return Math.max(0, request.baseline_payload_tokens ?? 0);
}

function familyIdForRecentRequest(agent: string): string {
  if (agent === 'openclaw' || agent.startsWith('openclaw-')) return 'openclaw';
  if (agent === 'claude' || agent === 'claude_code' || agent.startsWith('claude-')) return 'claude_code';
  if (agent === 'codex' || agent === 'codex_cli' || agent.startsWith('codex-')) return 'codex_cli';
  return agent || 'unknown';
}

function latestTimestamp(current: string | null, next: string): string {
  return current && current > next ? current : next;
}

function applyRealInputAgentSavings(
  controls: AgentControlResponse | null,
  recent: RecentRequestsResponse | null,
): AgentControlResponse | null {
  if (!controls) return null;

  const realInputByFamily = new Map<string, { saved: number; baseline: number }>();
  for (const request of recent?.requests ?? []) {
    if (request.request_class === 'internal') continue;
    const familyId = familyIdForRecentRequest(request.agent);
    const current = realInputByFamily.get(familyId) ?? { saved: 0, baseline: 0 };
    current.saved += realInputSavedTokens(request);
    current.baseline += realInputBaselineTokens(request);
    realInputByFamily.set(familyId, current);
  }

  return {
    ...controls,
    agents: controls.agents.map((agent) => {
      const realInput = realInputByFamily.get(agent.family_id);
      const savedTokens = realInput?.saved ?? 0;
      const savingsRatio = realInput && realInput.baseline > 0 ? savedTokens / realInput.baseline : 0;
      return {
        ...agent,
        saved_tokens_24h: savedTokens,
        savings_ratio_24h: savingsRatio,
      };
    }),
  };
}

function buildRealInputUsageSummary(recent: RecentRequestsResponse | null): UsageSummary {
  if (!recent) return emptyUsageSummary();

  const byAgent = new Map<string, { requests: number; saved: number; baseline: number; lastRequestAt: string | null }>();
  let savedTotal = 0;
  let baselineTotal = 0;
  let requestCount = 0;
  let lastRequestAt: string | null = null;

  for (const request of recent.requests) {
    if (request.request_class === 'internal') continue;
    const agent = familyIdForRecentRequest(request.agent);
    const saved = realInputSavedTokens(request);
    const baseline = realInputBaselineTokens(request);
    const current = byAgent.get(agent) ?? { requests: 0, saved: 0, baseline: 0, lastRequestAt: null };
    current.requests += 1;
    current.saved += saved;
    current.baseline += baseline;
    current.lastRequestAt = latestTimestamp(current.lastRequestAt, request.timestamp);
    byAgent.set(agent, current);
    savedTotal += saved;
    baselineTotal += baseline;
    requestCount += 1;
    lastRequestAt = latestTimestamp(lastRequestAt, request.timestamp);
  }

  return {
    tenant: recent.tenant,
    request_count: requestCount,
    total_requests: requestCount,
    saved_tokens_total: savedTotal,
    average_savings_ratio: baselineTotal > 0 ? savedTotal / baselineTotal : 0,
    last_request_at: lastRequestAt,
    by_agent: Array.from(byAgent.entries()).map(([agent, metrics]) => ({
      agent,
      requests: metrics.requests,
      saved_tokens: metrics.saved,
      savings_ratio: metrics.baseline > 0 ? metrics.saved / metrics.baseline : 0,
      last_request_at: metrics.lastRequestAt,
    })),
  };
}

export async function getProductConsoleSnapshot(): Promise<ProductConsoleSnapshot> {
  const [core, coreTrend, recent, controls] = await Promise.allSettled([
    fetchProductJson<CoreCapabilitiesResponse>('/metrics/core_capabilities?tenant=all', PRODUCT_METRICS_TIMEOUT_MS),
    fetchProductJson<CoreCapabilitiesTrendResponse>('/metrics/core_capabilities/trend?tenant=all&days=7', PRODUCT_METRICS_TIMEOUT_MS),
    fetchProductJson<RecentRequestsResponse>('/metrics/recent_requests?tenant=all&limit=1000&per_agent_limit=1000&include_internal=true&value_qualified_only=false', RECENT_REQUESTS_TIMEOUT_MS),
    fetchProductJson<AgentControlResponse>('/agents/control', AGENT_CONTROL_TIMEOUT_MS),
  ]);

  const fulfilled = [core, coreTrend, recent, controls].filter((result) => result.status === 'fulfilled');
  const firstError = [core, coreTrend, recent, controls].find((result) => result.status === 'rejected');
  const recentError = recent.status === 'rejected'
    ? recent.reason instanceof Error
      ? recent.reason.message
      : String(recent.reason)
    : null;

  const recentValue = recent.status === 'fulfilled' ? recent.value : null;
  const controlsValue = controls.status === 'fulfilled' ? controls.value : null;

  return {
    online: fulfilled.length > 0,
    error:
      fulfilled.length > 0
        ? null
        : firstError?.status === 'rejected'
          ? firstError.reason instanceof Error
            ? firstError.reason.message
            : String(firstError.reason)
          : 'Product console is offline.',
    recentError,
    core: core.status === 'fulfilled' ? core.value : null,
    coreTrend: coreTrend.status === 'fulfilled' ? coreTrend.value : null,
    recent: recentValue,
    usage: buildRealInputUsageSummary(recentValue),
    controls: applyRealInputAgentSavings(controlsValue, recentValue),
  };
}

export async function fetchRequestEvidence(requestId: string): Promise<RequestEvidence> {
  const raw = await fetchProductJson<RequestEvidence>(`/debug/request_evidence?request_id=${encodeURIComponent(requestId)}`, 3000);
  return {
    ...raw,
    skill_suggestions: Array.isArray(raw.skill_suggestions) ? raw.skill_suggestions : [],
    skill_policy_name: raw.skill_policy_name ?? 'local_fallback',
    skill_policy_version: raw.skill_policy_version ?? 'static_catalog_v1',
    skill_policy_source: raw.skill_policy_source ?? 'local_builtin',
    skill_policy_status: raw.skill_policy_status ?? 'fallback',
  };
}

async function postAgentControlAction(action: 'install' | 'uninstall' | 'enable' | 'disable' | 'repair', familyId: string): Promise<AgentControlCard> {
  const response = await fetch(`${PRODUCT_API_BASE}/agents/control/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ family_id: familyId }),
  });
  if (!response.ok) {
    const detail = await response.text();
    let message = detail;
    try {
      const parsed = JSON.parse(detail) as { detail?: unknown };
      message = typeof parsed.detail === 'string' ? parsed.detail : detail;
    } catch {
      message = detail;
    }
    throw new Error(message || `Failed to ${action} ${familyId}`);
  }
  return response.json();
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

export function repairAgentAttach(familyId: string): Promise<AgentControlCard> {
  return postAgentControlAction('repair', familyId);
}

export function buildFeedbackMailto(status: DesktopStatus): string {
  const subject = encodeURIComponent('OmniMemora Desktop Beta Feedback');
  const services = status.services.map((service) => `${service.name}:${service.state}`).join(',');
  const updates = status.updates.map((update) => `${update.layer}:${update.status}`).join(',');
  const body = encodeURIComponent([
    `version: ${status.app_version}`,
    `platform: ${navigator.userAgent || 'unknown'}`,
    `services: ${services}`,
    `updates: ${updates}`,
    'request_id: ',
    'error_code: ',
    'steps:',
    '- ',
  ].join('\n'));
  return `mailto:${status.feedback_email}?subject=${subject}&body=${body}`;
}
