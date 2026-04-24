// pkg/types.go - Shared types that don't belong to any specific package
// These types are used across multiple packages and help avoid import cycles
package pkg

import "time"

// ScopeType represents the memory boundary type
type ScopeType string

const (
	ScopeAgent     ScopeType = "agent"
	ScopeWorkspace ScopeType = "workspace"
	ScopeUser      ScopeType = "user"
	ScopeCustom    ScopeType = "custom"
)

// SharingMode represents how memory can be shared within a scope
type SharingMode string

const (
	SharingModeIsolated       SharingMode = "isolated"
	SharingModeShared         SharingMode = "shared"
	SharingModeSharedReadOnly SharingMode = "shared_read_only"
	SharingModeCustom         SharingMode = "custom"
)

// ScopeRef is the governance body for memory access control
// Aligns with RUNTIME_ARCHITECTURE.md Section 5.2
type ScopeRef struct {
	TenantID      string      `json:"tenant_id"`
	UserID        string      `json:"user_id"`
	WorkspaceID   string      `json:"workspace_id"`
	AgentID       string      `json:"agent_id"`
	Scope         ScopeType   `json:"scope"`
	SharingMode   SharingMode `json:"sharing_mode"`
	CustomScopeID string      `json:"custom_scope_id,omitempty"` // populated when Scope == ScopeCustom
}

// MemoryDomainType is the high-level domain identity used by AccessPlan.
type MemoryDomainType string

const (
	DomainInstancePrivate MemoryDomainType = "instance_private"
	DomainWorkspaceShared MemoryDomainType = "workspace_shared"
	DomainUserShared      MemoryDomainType = "user_shared"
	DomainCustomShared    MemoryDomainType = "custom_shared"
	DomainSharedReadOnly  MemoryDomainType = "shared_read_only"
)

// AccessPlanIdentity carries request-level identity spine fields.
type AccessPlanIdentity struct {
	TenantID   string `json:"tenant_id,omitempty"`
	FamilyID   string `json:"family_id,omitempty"`
	InstanceID string `json:"instance_id,omitempty"`
	WindowID   string `json:"window_id,omitempty"`
	SessionID  string `json:"session_id,omitempty"`
	RequestID  string `json:"request_id,omitempty"`
	RawAgentID string `json:"raw_agent_id,omitempty"`
}

// MemoryDomainRef represents one planned read/write domain in AccessPlan.
type MemoryDomainRef struct {
	DomainID    string           `json:"domain_id,omitempty"`
	TenantID    string           `json:"tenant_id,omitempty"`
	ScopeType   MemoryDomainType `json:"scope_type,omitempty"`
	ScopeKey    string           `json:"scope_key,omitempty"`
	SharingMode SharingMode      `json:"sharing_mode,omitempty"`
}

// AccessPlan describes planned memory-domain operations for one request.
type AccessPlan struct {
	Identity              *AccessPlanIdentity `json:"identity,omitempty"`
	ReadDomains           []MemoryDomainRef   `json:"read_domains,omitempty"`
	PrimaryWriteDomain    *MemoryDomainRef    `json:"primary_write_domain,omitempty"`
	SecondaryWriteDomains []MemoryDomainRef   `json:"secondary_write_domains,omitempty"`
	AllowSecondaryWrites  bool                `json:"allow_secondary_writes,omitempty"`
	SharingPolicySource   string              `json:"sharing_policy_source,omitempty"`
}

// EnforcedDomain captures one actual enforcement decision.
type EnforcedDomain struct {
	DomainID    string    `json:"domain_id,omitempty"`
	ScopeRef    *ScopeRef `json:"scope_ref,omitempty"`
	Operation   string    `json:"operation,omitempty"`
	Decision    string    `json:"decision,omitempty"`
	Reason      string    `json:"reason,omitempty"`
	MemoryID    string    `json:"memory_id,omitempty"`
	ResultCount int       `json:"result_count,omitempty"`
}

// EnforcementTrace keeps planned-vs-actual domain execution details.
type EnforcementTrace struct {
	PlannedReadDomains    []MemoryDomainRef `json:"planned_read_domains,omitempty"`
	PlannedWriteDomains   []MemoryDomainRef `json:"planned_write_domains,omitempty"`
	ActualEnforcedDomains []EnforcedDomain  `json:"actual_enforced_domains,omitempty"`
}

// MemoryRecord represents a single memory entry
// Aligns with RUNTIME_ARCHITECTURE.md Section 5.3
type MemoryRecord struct {
	MemoryID    string         `json:"memory_id"`
	Content     string         `json:"content"`
	ContentHash string         `json:"content_hash"`
	Metadata    map[string]any `json:"metadata,omitempty"`
	ScopeRef    *ScopeRef      `json:"scope_ref"`
	CreatedAt   time.Time      `json:"created_at"`
	UpdatedAt   time.Time      `json:"updated_at"`
	ExpiresAt   *time.Time     `json:"expires_at,omitempty"`
	AccessCount int            `json:"access_count"`
}

// QueryRequest represents a memory query request
type QueryRequest struct {
	Query      string      `json:"query"`
	ScopeRef   *ScopeRef   `json:"scope_ref,omitempty"`
	AccessPlan *AccessPlan `json:"access_plan,omitempty"`
	Limit      int         `json:"limit"`
	RequestID  string      `json:"request_id,omitempty"`
}

// QueryResult represents query results
type QueryResult struct {
	RequestID        string            `json:"request_id"`
	Query            string            `json:"query"`
	Results          []QueryMatch      `json:"results"`
	Total            int               `json:"total"`
	ScopeApplied     ScopeType         `json:"scope_applied"`
	TookMs           int64             `json:"took_ms"`
	EnforcementTrace *EnforcementTrace `json:"enforcement_trace,omitempty"`
}

// QueryMatch represents a single query match
type QueryMatch struct {
	MemoryID  string         `json:"memory_id"`
	Content   string         `json:"content"`
	Score     float64        `json:"score"`
	Scope     ScopeType      `json:"scope"`
	DomainID  string         `json:"domain_id,omitempty"`
	CreatedAt time.Time      `json:"created_at"`
	Metadata  map[string]any `json:"metadata,omitempty"`
}

// WriteRequest represents a memory write request
type WriteRequest struct {
	Content     string         `json:"content"`
	Metadata    map[string]any `json:"metadata,omitempty"`
	Scope       ScopeType      `json:"scope,omitempty"`
	AgentID     string         `json:"agent_id,omitempty"`
	WorkspaceID string         `json:"workspace_id,omitempty"`
	AccessPlan  *AccessPlan    `json:"access_plan,omitempty"`
	Tags        []string       `json:"tags,omitempty"`
	RequestID   string         `json:"request_id,omitempty"`
}

// WriteResponse represents a write operation response
type WriteResponse struct {
	MemoryID         string            `json:"memory_id"`
	Status           string            `json:"status"`
	Scope            ScopeType         `json:"scope"`
	SharingMode      SharingMode       `json:"sharing_mode"`
	CreatedAt        time.Time         `json:"created_at"`
	RequestID        string            `json:"request_id"`
	DedupHit         bool              `json:"dedup_hit,omitempty"`
	EnforcementTrace *EnforcementTrace `json:"enforcement_trace,omitempty"`
}

// MetricsResponse represents the /metrics endpoint response
type MetricsResponse struct {
	Runtime RuntimeMetrics                     `json:"runtime"`
	Totals  TotalsMetrics                      `json:"totals"`
	ByScope map[string]map[string]ScopeMetrics `json:"by_scope"`
	ByDay   []DailyMetrics                     `json:"by_day"`
	// Phase 3: Token Savings Metrics
	TokenSavings *TokenSavingsMetrics `json:"token_savings,omitempty"`
	Efficiency   *EfficiencyMetrics   `json:"efficiency,omitempty"`
	// Phase 4: MCP integration metrics
	MCP *MCPMetrics `json:"mcp,omitempty"`
	// Phase 3.5: Demo detection
	DemoEventsOccurred bool `json:"demo_events_occurred,omitempty"`
}

// MCPMetrics contains protocol-level integration signals for agent connectivity.
type MCPMetrics struct {
	Handshakes                     int64  `json:"handshakes"`
	ToolInvocations                int64  `json:"tool_invocations"`
	MemoryWriteCalls               int64  `json:"memory_write_calls"`
	MemorySearchContextRecallCalls int64  `json:"memory_search_context_recall_calls"`
	LastStartupError               string `json:"last_startup_error,omitempty"`
}

// TokenSavingsMetrics contains token savings aggregations (Phase 3)
type TokenSavingsMetrics struct {
	TotalSavedTokens int64 `json:"total_saved_tokens"`
	TodaySavedTokens int64 `json:"today_saved_tokens"`
	WeekSavedTokens  int64 `json:"week_saved_tokens"`
	MonthSavedTokens int64 `json:"month_saved_tokens"`
}

// EfficiencyMetrics contains efficiency indicators (Phase 3)
type EfficiencyMetrics struct {
	AvgCompressionRatio float64 `json:"avg_compression_ratio"`
	AvgSavedPerQuery    float64 `json:"avg_saved_per_query"`
}

// ByWorkspaceMetrics holds metrics broken down by workspace (Phase 3)
type ByWorkspaceMetrics struct {
	SavedTokens int64 `json:"saved_tokens"`
	Queries     int64 `json:"queries"`
}

// ByAgentMetrics holds metrics broken down by agent (Phase 3)
type ByAgentMetrics struct {
	SavedTokens int64 `json:"saved_tokens"`
}

// EnhancedMetricsResponse is the full Phase 3 /metrics response
type EnhancedMetricsResponse struct {
	Runtime      RuntimeMetrics                     `json:"runtime"`
	Totals       TotalsMetrics                      `json:"totals"`
	ByScope      map[string]map[string]ScopeMetrics `json:"by_scope"`
	ByDay        []DailyMetrics                     `json:"by_day"`
	TokenSavings *TokenSavingsMetrics               `json:"token_savings,omitempty"`
	Efficiency   *EfficiencyMetrics                 `json:"efficiency,omitempty"`
	ByWorkspace  map[string]ByWorkspaceMetrics      `json:"by_workspace,omitempty"`
	ByAgent      map[string]ByAgentMetrics          `json:"by_agent,omitempty"`
}

// RuntimeMetrics contains runtime-level metrics
type RuntimeMetrics struct {
	Version       string `json:"version"`
	UptimeSeconds int64  `json:"uptime_seconds"`
	Mode          string `json:"mode"`
}

// TotalsMetrics contains aggregate metrics
type TotalsMetrics struct {
	MemoryCount           int64 `json:"memory_count"`
	TotalWrites           int64 `json:"total_writes"`
	TotalQueries          int64 `json:"total_queries"`
	TotalInputTokens      int64 `json:"total_input_tokens"`
	TotalCompressedTokens int64 `json:"total_compressed_tokens"`
	TotalSavedTokens      int64 `json:"total_saved_tokens"`
	TotalQueryCount       int64 `json:"total_query_count"`
	TotalRecallHits       int64 `json:"total_recall_hits"`
}

// ScopeMetrics contains metrics for a specific scope
type ScopeMetrics struct {
	MemoryCount      int64 `json:"memory_count"`
	TotalSavedTokens int64 `json:"total_saved_tokens"`
}

// DailyMetrics contains daily aggregated metrics
type DailyMetrics struct {
	Date        string `json:"date"`
	SavedTokens int64  `json:"saved_tokens"`
	QueryCount  int64  `json:"query_count"`
}

// HealthResponse represents the /health endpoint response
type HealthResponse struct {
	Status               string `json:"status"`
	Version              string `json:"version"`
	Mode                 string `json:"mode"`
	UptimeSeconds        int64  `json:"uptime_seconds"`
	StoreType            string `json:"store_type"`
	RegisteredConnectors int    `json:"registered_connectors"`
	MemoryCount          int64  `json:"memory_count"`
}

// ErrorResponse represents an API error response
type ErrorResponse struct {
	Error   string `json:"error"`
	Code    string `json:"code,omitempty"`
	Details string `json:"details,omitempty"`
}

// SearchOptions contains optional search behavior flags
type SearchOptions struct {
	IncludeBreakdown bool `json:"include_breakdown,omitempty"`
	AssembleContext  bool `json:"assemble_context,omitempty"`
	ContextLimit     int  `json:"context_limit,omitempty"`
	MaxContextTokens int  `json:"max_context_tokens,omitempty"`
	// Phase 2c fields
	ContextStrategy string `json:"context_strategy,omitempty"` // topk_excerpt, recency_boost_select, diversity_select
	ContextMode     string `json:"context_mode,omitempty"`     // precise, balanced, aggressive
}

// StrategySearchResult represents a search result for strategy selection (Phase 2c)
type StrategySearchResult struct {
	MemoryID      string    `json:"memory_id"`
	Content       string    `json:"content"`
	Score         float64   `json:"score"`
	TokenEstimate int       `json:"token_estimate"`
	CreatedAt     time.Time `json:"created_at,omitempty"`
}

// StrategyContextItem represents a selected context item for strategy assembly (Phase 2c)
type StrategyContextItem struct {
	MemoryID  string    `json:"memory_id"`
	Content   string    `json:"content"`
	Score     float64   `json:"score"`
	Tokens    int       `json:"tokens"`
	CreatedAt time.Time `json:"created_at,omitempty"`
}

// StrategyAssembledContext represents the result of strategy-driven context assembly (Phase 2c)
type StrategyAssembledContext struct {
	Text             string  `json:"text"`
	TotalTokens      int     `json:"total_tokens"`
	UsedItems        int     `json:"used_items"`
	CompressionRatio float64 `json:"compression_ratio"`
}

// StrategyEffectiveness contains metrics for evaluating strategy performance (Phase 2c.5)
type StrategyEffectiveness struct {
	TokensPerItem    float64 `json:"tokens_per_item"`
	CompressionRatio float64 `json:"compression_ratio"`
	AvgScore         float64 `json:"avg_score"`
}

// ContextItem represents a single excerpt in the assembled context
type ContextItem struct {
	MemoryID      string  `json:"memory_id"`
	Excerpt       string  `json:"excerpt"`
	Score         float64 `json:"score"`
	TokenEstimate int     `json:"token_estimate"`
}

// AssembledContext represents the assembled context block from Phase 2b
type AssembledContext struct {
	Assembled        bool          `json:"assembled"`
	Strategy         string        `json:"strategy"`
	Items            []ContextItem `json:"items"`
	CombinedText     string        `json:"combined_text"`
	RawTokens        int           `json:"raw_tokens"`
	CompressedTokens int           `json:"compressed_tokens"`
	SavedTokens      int           `json:"saved_tokens"`
	// Phase 3: Enhanced observability fields
	CompressionRatio float64 `json:"compression_ratio,omitempty"`
	StrategyResolved string  `json:"strategy_resolved,omitempty"`
	Mode             string  `json:"mode,omitempty"`
	ItemsSelected    int     `json:"items_selected,omitempty"`
	TokenBudgetUsed  int     `json:"token_budget_used,omitempty"`
}

// SearchRequest represents a keyword search request
type SearchRequest struct {
	Keyword    string        `json:"keyword"`
	ScopeRef   *ScopeRef     `json:"scope_ref,omitempty"`
	AccessPlan *AccessPlan   `json:"access_plan,omitempty"`
	Limit      int           `json:"limit"`
	RequestID  string        `json:"request_id,omitempty"`
	Options    SearchOptions `json:"options,omitempty"`
}

// ScoreBreakdown shows the individual components of the ranking score
type ScoreBreakdown struct {
	TextMatchScore float64 `json:"text_match_score"`
	RecencyBoost   float64 `json:"recency_boost"`
	AccessBoost    float64 `json:"access_boost"`
	VectorScore    float64 `json:"vector_score"`
}

// SearchResultItem represents a single ranked search result
type SearchResultItem struct {
	MemoryID       string          `json:"memory_id"`
	Content        string          `json:"content"`
	Score          float64         `json:"score"`
	VectorScore    float64         `json:"vector_score"`
	Scope          ScopeType       `json:"scope,omitempty"`
	DomainID       string          `json:"domain_id,omitempty"`
	TokenEstimate  int             `json:"token_estimate"`
	ScoreBreakdown *ScoreBreakdown `json:"score_breakdown,omitempty"`
	CreatedAt      time.Time       `json:"created_at,omitempty"`
	UpdatedAt      time.Time       `json:"updated_at,omitempty"`
}

// SearchResponse represents a keyword search response
type SearchResponse struct {
	RequestID        string             `json:"request_id"`
	Keyword          string             `json:"keyword"`
	Results          []SearchResultItem `json:"results"`
	Total            int                `json:"total"`
	ScopeApplied     ScopeType          `json:"scope_applied"`
	TookMs           int64              `json:"took_ms"`
	Context          *AssembledContext  `json:"context,omitempty"`
	EnforcementTrace *EnforcementTrace  `json:"enforcement_trace,omitempty"`
}

// DeleteRequest represents a memory delete request
type DeleteRequest struct {
	MemoryID  string    `json:"memory_id"`
	Scope     ScopeType `json:"scope,omitempty"`
	RequestID string    `json:"request_id,omitempty"`
}

// DeleteResponse represents a memory delete response
type DeleteResponse struct {
	MemoryID  string `json:"memory_id"`
	Status    string `json:"status"`
	RequestID string `json:"request_id,omitempty"`
}
