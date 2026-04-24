// metering/event.go - Metering event structures
// Aligns with RUNTIME_ARCHITECTURE.md Section 5.4 and DECISION_LEDGER.md Decision 08
package metering

import (
	"time"

	"github.com/omnimemora/local-runtime/pkg"
)

// Event represents a metering event
// This is the canonical event type - stored in DB and used across packages
type Event struct {
	EventID          string    `json:"event_id"`
	RequestID        string    `json:"request_id"`
	EventType        string    `json:"event_type"`
	TenantID         string    `json:"tenant_id"`
	UserID           string    `json:"user_id"`
	WorkspaceID      string    `json:"workspace_id"`
	AgentID          string    `json:"agent_id"`
	Scope            string    `json:"scope"`
	SharingMode      string    `json:"sharing_mode"`
	InputTokens      int       `json:"input_tokens"`
	CompressedTokens int       `json:"compressed_tokens"`
	SavedTokens      int       `json:"saved_tokens"`
	QueryCount       int       `json:"query_count"`
	RecallHits       int       `json:"recall_hits"`
	RecallHitRate    float64   `json:"recall_hit_rate"`
	Timestamp        time.Time `json:"timestamp"`
	RuntimeVersion   string    `json:"runtime_version"`
	StoreType        string    `json:"store_type"`
	// Phase 2b fields
	RawTokens      int    `json:"raw_tokens,omitempty"`
	AssembledHits  int    `json:"assembled_hits,omitempty"`
	// Phase 2c fields
	ContextStrategy string `json:"context_strategy,omitempty"`
	ContextMode     string `json:"context_mode,omitempty"`
	// Phase 2c.5 fields
	StrategyEffectiveness *pkg.StrategyEffectiveness `json:"strategy_effectiveness,omitempty"`
	// Phase CSP-001 fields: compile strategy policy evidence
	CompileStrategyPolicyVersion  string `json:"compile_strategy_policy_version,omitempty"`
	CompileStrategyPolicySource   string `json:"compile_strategy_policy_source,omitempty"`
	ContextStrategyRequested     string `json:"context_strategy_requested,omitempty"`
	ContextStrategyResolved      string `json:"context_strategy_resolved,omitempty"`
	ContextModeResolved          string `json:"context_mode_resolved,omitempty"`
}
