// connector/types.go - Connector types and structures
// Aligns with RUNTIME_ARCHITECTURE.md Section 11
package connector

import "time"

// Info represents a registered connector
type Info struct {
	ConnectorID   string    `json:"connector_id"`
	AgentID       string    `json:"agent_id"`
	ConnectorType string    `json:"connector_type"`
	WorkspaceID   string    `json:"workspace_id"`
	Status        string    `json:"status"`
	RegisteredAt  time.Time `json:"registered_at"`
}

// RegisterRequest represents a connector registration request
type RegisterRequest struct {
	ConnectorID   string `json:"connector_id"`
	AgentID       string `json:"agent_id"`
	ConnectorType string `json:"connector_type"`
	WorkspaceID   string `json:"workspace_id"`
}

// RegisterResponse represents a connector registration response
type RegisterResponse struct {
	ConnectorID  string    `json:"connector_id"`
	Status       string    `json:"status"`
	RegisteredAt time.Time `json:"registered_at"`
}

// DeregisterRequest represents a connector deregistration request
type DeregisterRequest struct {
	ConnectorID string `json:"connector_id"`
}
