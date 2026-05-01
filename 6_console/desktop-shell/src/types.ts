export type ServiceName = 'runtime' | 'adapter' | 'ui';
export type ServiceState = 'healthy' | 'unreachable' | 'unknown' | 'blocked';
export type UpdateLayer = 'desktop_shell' | 'local_components' | 'cloud_policy';
export type AgentId = 'claude' | 'openclaw' | 'codex';
export type AgentState = 'connected' | 'ready' | 'not_found';

export interface ServiceStatus {
  name: ServiceName;
  port: number;
  state: ServiceState;
  url: string;
  detail: string;
  managed_by_desktop: boolean;
  pid: number | null;
}

export interface UpdateLayerStatus {
  layer: UpdateLayer;
  current_version: string;
  available_version: string | null;
  status: 'current' | 'available' | 'not_checked' | 'blocked';
  detail: string;
}

export interface DesktopStatus {
  app_version: string;
  data_dir: string;
  services: ServiceStatus[];
  updates: UpdateLayerStatus[];
  feedback_email: string;
}

export interface DesktopCommandResult {
  ok: boolean;
  message: string;
  status: DesktopStatus | null;
}

export interface AgentStatus {
  id: AgentId;
  name: string;
  state: AgentState;
  installed: boolean;
  running: boolean;
  attached: boolean;
  supported: boolean;
  experimental: boolean;
  detail: string;
  config_path: string;
}

export interface CoreCapabilitiesResponse {
  period: '24h';
  observed_request_count: number;
  non_value_count: number;
  internal_or_wrapper_count?: number;
  cards: {
    real_requests: {
      count: number;
      ratio: number;
    };
    context_compression: {
      ratio: number;
      baseline_tokens: number;
      actual_tokens: number;
    };
    memory_enhancement: {
      rate: number;
      memory_count: number;
    };
    token_savings: {
      ratio: number;
      saved_tokens: number;
    };
  };
}

export interface RecentRequest {
  request_id: string;
  agent: string;
  timestamp: string;
  task_type: string;
  bypass: boolean;
  saved_tokens: number;
  savings_ratio: number;
  query: string;
  raw_query?: string;
  user_visible_query?: string;
  packed_memory_count: number;
  local_cards_used: number;
  remote_used_count: number;
  request_class: 'internal' | 'task_non_value' | 'value_qualified';
  qualification_reason?: string;
  value_paths?: string[];
  diagnostic_label?: string;
  display_savings_as_value?: boolean;
}

export interface RecentRequestsResponse {
  tenant: string;
  requests: RecentRequest[];
}

export interface AgentUsage {
  agent: string;
  requests: number;
  saved_tokens: number;
  savings_ratio: number;
  last_request_at?: string | null;
}

export interface UsageSummary {
  tenant: string;
  request_count: number;
  total_requests: number;
  saved_tokens_total: number;
  average_savings_ratio: number;
  last_request_at?: string | null;
  by_agent: AgentUsage[];
}

export interface AgentControlCard {
  family_id: string;
  display_name: string;
  installed: boolean;
  routing_enabled: boolean;
  detected: boolean;
  active: boolean;
  last_seen_at?: string | null;
  health_state: string;
  backup_available: boolean;
  subagent_count_active: number;
  subagent_count_total_visible: number;
  message?: string;
  integration_truth?: 'detached' | 'mcp_attached' | 'attached_with_backup';
  route_truth?: 'off' | 'intent_on' | 'effective';
  traffic_truth?: 'no_recent_evidence' | 'internal_only' | 'real_request_observed' | 'compile_empty' | 'bypassed';
  requests_24h?: number;
  saved_tokens_24h?: number;
  savings_ratio_24h?: number;
  last_request_at?: string | null;
  observed_requests_24h?: number;
}

export interface AgentControlResponse {
  agents: AgentControlCard[];
  count: number;
  system_status?: {
    status: string;
    recommended_action?: string;
    user_action_required?: boolean;
  };
}

export interface ProductConsoleSnapshot {
  online: boolean;
  error: string | null;
  core: CoreCapabilitiesResponse | null;
  recent: RecentRequestsResponse | null;
  usage: UsageSummary | null;
  controls: AgentControlResponse | null;
}
