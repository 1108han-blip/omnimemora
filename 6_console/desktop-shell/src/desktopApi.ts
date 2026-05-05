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

const DEFAULT_STATUS: DesktopStatus = {
  app_version: '1.0.0-beta.9',
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
    {
      name: 'ui',
      port: 5173,
      state: 'unknown',
      url: 'http://127.0.0.1:5173/',
      detail: 'Waiting for desktop host status.',
      managed_by_desktop: false,
      pid: null,
    },
  ],
  updates: [
    {
      layer: 'desktop_shell',
      current_version: '1.0.0-beta.9',
      available_version: null,
      status: 'not_checked',
      detail: 'Desktop shell updates are installer-based in this beta.',
    },
    {
      layer: 'local_components',
      current_version: '1.0.0-beta.9',
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

export async function runDesktopCommand(command: 'start_services' | 'stop_services' | 'restart_services' | 'check_for_updates' | 'install_update' | 'rollback'): Promise<DesktopCommandResult> {
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

function normalizeUsage(raw: Record<string, unknown>): UsageSummary {
  return {
    tenant: (raw.tenant as string) ?? 'all',
    request_count: Number(raw.request_count ?? 0),
    total_requests: Number(raw.total_requests ?? 0),
    saved_tokens_total: Number(raw.saved_tokens_total ?? raw.saved_tokens_estimate_total ?? 0),
    average_savings_ratio: Number(raw.average_savings_ratio ?? 0),
    last_request_at: (raw.last_request_at as string | null) ?? null,
    by_agent: Array.isArray(raw.by_agent)
      ? raw.by_agent.map((entry) => {
          const item = entry as Record<string, unknown>;
          return {
            agent: (item.agent as string) ?? 'unknown',
            requests: Number(item.requests ?? 0),
            saved_tokens: Number(item.saved_tokens ?? 0),
            savings_ratio: Number(item.savings_ratio ?? 0),
            last_request_at: (item.last_request_at as string | null) ?? null,
          };
        })
      : [],
  };
}

export async function getProductConsoleSnapshot(): Promise<ProductConsoleSnapshot> {
  const [core, coreTrend, recent, usage, controls] = await Promise.allSettled([
    fetchProductJson<CoreCapabilitiesResponse>('/metrics/core_capabilities?tenant=all'),
    fetchProductJson<CoreCapabilitiesTrendResponse>('/metrics/core_capabilities/trend?tenant=all&days=7'),
    fetchProductJson<RecentRequestsResponse>('/metrics/recent_requests?tenant=all&limit=30&value_qualified_only=false'),
    fetchProductJson<Record<string, unknown>>('/usage/token-savings?tenant=all'),
    fetchProductJson<AgentControlResponse>('/agents/control'),
  ]);

  const fulfilled = [core, coreTrend, recent, usage, controls].filter((result) => result.status === 'fulfilled');
  const firstError = [core, coreTrend, recent, usage, controls].find((result) => result.status === 'rejected');

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
    core: core.status === 'fulfilled' ? core.value : null,
    coreTrend: coreTrend.status === 'fulfilled' ? coreTrend.value : null,
    recent: recent.status === 'fulfilled' ? recent.value : null,
    usage: usage.status === 'fulfilled' ? normalizeUsage(usage.value) : null,
    controls: controls.status === 'fulfilled' ? controls.value : null,
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

async function postAgentControlAction(action: 'install' | 'uninstall' | 'enable' | 'disable', familyId: string): Promise<AgentControlCard> {
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
