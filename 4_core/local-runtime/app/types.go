// app/types.go - Application-level types for OmniMemora Local Runtime
// Note: Shared types (ScopeRef, ScopeType, SharingMode, etc.) are in pkg/types.go
// This file contains app-specific types only
package app

import "time"

// ErrorResponse represents an error response
type ErrorResponse struct {
	Error string `json:"error"`
	Code  string `json:"code"`
}

// ConnectorInfo represents a registered connector
type ConnectorInfo struct {
	ConnectorID   string    `json:"connector_id"`
	AgentID       string    `json:"agent_id"`
	ConnectorType string    `json:"connector_type"`
	WorkspaceID   string    `json:"workspace_id"`
	Status        string    `json:"status"`
	RegisteredAt  time.Time `json:"registered_at"`
}

// MeteringEvent represents a metering record for token savings
// Aligns with RUNTIME_ARCHITECTURE.md Section 5.4
type MeteringEvent struct {
	EventID          string      `json:"event_id"`
	RequestID        string      `json:"request_id"`
	EventType        string      `json:"event_type"`
	TenantID         string      `json:"tenant_id"`
	UserID           string      `json:"user_id"`
	WorkspaceID      string      `json:"workspace_id"`
	AgentID          string      `json:"agent_id"`
	Scope            string      `json:"scope"`
	SharingMode      string      `json:"sharing_mode"`
	InputTokens      int         `json:"input_tokens"`
	CompressedTokens int         `json:"compressed_tokens"`
	SavedTokens      int         `json:"saved_tokens"`
	QueryCount       int         `json:"query_count"`
	RecallHits       int         `json:"recall_hits"`
	RecallHitRate    float64     `json:"recall_hit_rate"`
	Timestamp        time.Time   `json:"timestamp"`
	RuntimeVersion   string      `json:"runtime_version"`
	StoreType        string      `json:"store_type"`
}
