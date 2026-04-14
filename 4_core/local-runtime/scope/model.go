// scope/model.go - Scope model and enforcement
// Aligns with MEMORY_SCOPE_MODEL.md and RUNTIME_ARCHITECTURE.md Section 6
package scope

import (
	"fmt"
	"time"

	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/pkg"
)

// Model implements scope governance
type Model struct {
	cfg       *config.RuntimeConfig
	startedAt time.Time
}

// NewModel creates a new scope model
func NewModel(cfg *config.RuntimeConfig) *Model {
	return &Model{
		cfg:       cfg,
		startedAt: time.Now(),
	}
}

// StartedAt returns the runtime start time
func (m *Model) StartedAt() time.Time {
	return m.startedAt
}

// EnforceWrite enforces write access based on scope rules
// Per MEMORY_SCOPE_MODEL.md Section 五
func (m *Model) EnforceWrite(scopeRef *pkg.ScopeRef) error {
	if scopeRef == nil {
		return fmt.Errorf("scope ref is nil")
	}

	switch scopeRef.Scope {
	case pkg.ScopeAgent:
		if scopeRef.AgentID == "" {
			return fmt.Errorf("agent_id required for agent scope")
		}
	case pkg.ScopeWorkspace:
		if scopeRef.WorkspaceID == "" {
			return fmt.Errorf("workspace_id required for workspace scope")
		}
	case pkg.ScopeUser:
		if scopeRef.UserID == "" {
			return fmt.Errorf("user_id required for user scope")
		}
	case pkg.ScopeCustom:
		return fmt.Errorf("custom scope not yet implemented")
	}

	return nil
}

// EnforceRead enforces read access based on scope rules
// Per MEMORY_SCOPE_MODEL.md Section 五
func (m *Model) EnforceRead(scopeRef *pkg.ScopeRef) error {
	if scopeRef == nil {
		return fmt.Errorf("scope ref is nil")
	}

	switch scopeRef.Scope {
	case pkg.ScopeAgent:
		if scopeRef.AgentID == "" {
			return fmt.Errorf("agent_id required for agent scope")
		}
	case pkg.ScopeWorkspace:
		if scopeRef.WorkspaceID == "" {
			return fmt.Errorf("workspace_id required for workspace scope")
		}
	case pkg.ScopeUser:
		if scopeRef.UserID == "" {
			return fmt.Errorf("user_id required for user scope")
		}
	case pkg.ScopeCustom:
		return fmt.Errorf("custom scope not yet implemented")
	}

	return nil
}

// ValidateScopeRef validates that a ScopeRef has all required fields
func (m *Model) ValidateScopeRef(scopeRef *pkg.ScopeRef) error {
	if scopeRef == nil {
		return fmt.Errorf("scope ref is nil")
	}

	if scopeRef.Scope == "" {
		return fmt.Errorf("scope is required")
	}

	switch scopeRef.Scope {
	case pkg.ScopeAgent, pkg.ScopeWorkspace, pkg.ScopeUser, pkg.ScopeCustom:
		// Valid
	default:
		return fmt.Errorf("invalid scope type: %s", scopeRef.Scope)
	}

	switch scopeRef.SharingMode {
	case pkg.SharingModeIsolated, pkg.SharingModeShared, pkg.SharingModeSharedReadOnly, pkg.SharingModeCustom, "":
		// Valid
	default:
		return fmt.Errorf("invalid sharing mode: %s", scopeRef.SharingMode)
	}

	return nil
}

// GetDefaultScopeRef returns a default scope reference based on config
func (m *Model) GetDefaultScopeRef() *pkg.ScopeRef {
	return &pkg.ScopeRef{
		TenantID:    "",
		UserID:      m.cfg.Scope.DefaultWorkspace,
		WorkspaceID: m.cfg.Scope.DefaultWorkspace,
		AgentID:     "local",
		Scope:       pkg.ScopeType(m.cfg.Scope.Default),
		SharingMode: pkg.SharingMode(m.cfg.Scope.DefaultSharingMode),
	}
}
