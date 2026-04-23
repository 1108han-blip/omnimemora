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
  // Truth surface fields (product boundary clarity — from backend)
  integration_truth?: 'detached' | 'mcp_attached' | 'attached_with_backup';
  route_truth?: 'off' | 'intent_on' | 'effective';
  traffic_truth?: 'no_recent_evidence' | 'internal_only' | 'real_request_observed';
  observed_client_truth?: {
    provider: string | null;
    model: string | null;
    base_url: string | null;
    base_url_class: string;
  };
  truth_message?: string;
  // Scope identity fields
  identity_scope?: 'family';
  scope_note?: string | null;
  requests_24h?: number;
  saved_tokens_24h?: number;
  savings_ratio_24h?: number;
  last_request_at?: string | null;
  observed_requests_24h?: number;
}

export interface AgentControlResponse {
  agents: AgentControlCard[];
  count: number;
  system_status: SystemStatus;
  rescan_status?: 'added' | 'removed' | 'no_change';
  rescan_message?: string;
  rescan_added?: string[];
  rescan_removed?: string[];
}

// ---------------------------------------------------------------------------
// Core Capabilities — 首页四卡专用类型
// ---------------------------------------------------------------------------

export interface RealRequestsCard {
  count: number;
  ratio: number;
}

export interface ContextCompressionCard {
  ratio: number;
  baseline_tokens: number;
  actual_tokens: number;
}

export interface MemoryEnhancementCard {
  rate: number;
  memory_count: number;
}

export interface TokenSavingsCard {
  ratio: number;
  saved_tokens: number;
}

export interface CoreCapabilitiesResponse {
  period: '24h';
  observed_request_count: number;
  non_value_count: number;
  cards: {
    real_requests: RealRequestsCard;
    context_compression: ContextCompressionCard;
    memory_enhancement: MemoryEnhancementCard;
    token_savings: TokenSavingsCard;
  };
}

export interface CoreCapabilitiesTrendPoint {
  date: string;
  observed_request_count: number;
  non_value_count: number;
  real_requests: RealRequestsCard;
  context_compression: ContextCompressionCard;
  memory_enhancement: MemoryEnhancementCard;
  token_savings: TokenSavingsCard;
}

export interface CoreCapabilitiesTrendResponse {
  days: number;
  trend: CoreCapabilitiesTrendPoint[];
}

// ---------------------------------------------------------------------------
// Legacy types (kept for existing consumers — do not use for 四卡)
// ---------------------------------------------------------------------------

export interface MetricsSummary {
  token_saving_ratio: number;
  tokens_saved: number;
  request_count: number;
  avg_context_reduction: number;
  period?: '24h' | 'all';
}

export interface MetricsTrendPoint {
  date: string;
  requests: number;
  saved_tokens: number;
  savings_ratio: number;
}

export interface MetricsTrend {
  tenant: string;
  days: number;
  trend: MetricsTrendPoint[];
  total_saved_tokens_all_time?: number;
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
  remote_used_count: number;
  request_class: 'internal' | 'task_non_value' | 'value_qualified';
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

// ------------------------------------------------------------------
// Request Evidence (unified view for overview evidence layer)
// ------------------------------------------------------------------

export type RequestStatus = 'success' | 'warning' | 'failed' | 'bypassed' | 'not_used';
export type NodeStatus = 'success' | 'warning' | 'failed' | 'bypassed' | 'not_used';
export type ContextOptimizationState = 'optimized_visible' | 'traffic_but_no_optimization' | 'bypass_or_not_applicable';

export interface RequestEvidenceNode {
  id: string;
  label: string;
  status: NodeStatus;
  duration_ms: number;
  note: string;
}

export interface RequestEvidenceContext {
  before_tokens: number;
  after_tokens: number;
  saved_tokens: number;
  savings_ratio: number;
  selected_memory_count: number;
  dropped_memory_count: number;
  selected_memories: MemoryEntry[];
  dropped_memories: MemoryEntry[];
  context_state: ContextOptimizationState;
}

export interface RequestEvidenceStatus {
  request_status: RequestStatus;
  bypass: boolean;
  failure_stage: string | null;
  failure_reason: string | null;
  error_code?: string | null;
}

export interface RequestEvidenceRequest {
  request_id: string;
  timestamp: string;
  raw_agent_id: string;
  agent_family: string;
  task_type: string;
  query_summary: string;
}

export interface RequestEvidenceChain {
  nodes: RequestEvidenceNode[];
  trace_id: string;
}

export interface SkillSuggestionView {
  skill_id: string;
  title: string;
  reason: string;
  confidence: number;
  source: string;
}

export interface RequestEvidence {
  request: RequestEvidenceRequest;
  status: RequestEvidenceStatus;
  context: RequestEvidenceContext;
  chain: RequestEvidenceChain;
  skill_suggestions: SkillSuggestionView[];
  skill_policy_name?: string;
  skill_policy_version?: string;
  skill_policy_source?: string;
  skill_policy_status?: string;
}
