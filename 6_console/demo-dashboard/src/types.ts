// API response types matching the backend endpoints

export interface LiveAgent {
  agent_id: string;
  session_id: string;
  workspace_id: string;
  integration_type: string;
  mode: 'observe' | 'guided' | 'force_if_possible' | 'off';
  request_count: number;
  optimized_count: number;
  entry_rate: number;
  saved_tokens: number;
  quality_delta_pct: number;
  last_seen_at: string;
}

export interface SystemStatus {
  status: string;
  status_source?: string;
  transition_reason?: string;
  gateway_health: string;
  capability_health: string;
  routing_requested: boolean;
  routing_effective: boolean;
  user_action_required: boolean;
  recommended_action: string;
  error_code?: string;
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
}

export interface AgentControlResponse {
  agents: AgentControlCard[];
  count: number;
  system_status: SystemStatus;
}

export interface MetricsSummary {
  token_saving_ratio: number;
  tokens_saved: number;
  request_count: number;
  avg_context_reduction: number;
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

export interface RecentRequest {
  request_id: string;
  agent: string;
  timestamp: string;
  task_type: string;
  bypass: boolean;
  saved_tokens: number;
  savings_ratio: number;
  query: string;
  packed_memory_count: number;
  local_cards_used: number;
}

export interface RecentRequestsResponse {
  tenant: string;
  requests: RecentRequest[];
}

export interface ContextDiff {
  request_id: string;
  before_tokens: number;
  after_tokens: number;
  selected_memories: MemoryEntry[];
  dropped_memories: MemoryEntry[];
}

export interface MemoryEntry {
  uri: string;
  content: string;
  abstract?: string;
  score: number;
  category: string;
  level: number;
  metadata: Record<string, unknown>;
  _score?: number;
  _filter_reason?: string;
  _relevance_score?: number;
  _type_score?: number;
  _length_penalty?: number;
  _final_score?: number;
}

export interface CallChainStage {
  name: string;
  duration_ms: number;
  metadata: Record<string, unknown>;
}

export interface CallChain {
  trace_id: string;
  stages: CallChainStage[];
}
