// scope/model.go - Scope model and enforcement
// Aligns with MEMORY_SCOPE_MODEL.md and RUNTIME_ARCHITECTURE.md Section 6
package scope

import (
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/pkg"
)

// CustomScopeRegistry is the on-disk registry for named custom scopes.
type CustomScopeRegistry struct {
	CustomScopes []CustomScopeDef `json:"custom_scopes"`
}

// CustomScopeDef defines a named custom scope with its members and default sharing mode.
type CustomScopeDef struct {
	ID            string   `json:"id"`              // stable unique identifier
	Name          string   `json:"name"`            // display name
	AllowedUsers  []string `json:"allowed_users"`   // user IDs allowed in this scope
	DefaultMode   string   `json:"default_mode"`   // "isolated", "shared", "shared_read_only"
}

// Model implements scope governance
type Model struct {
	cfg       *config.RuntimeConfig
	startedAt time.Time
	registry  *CustomScopeRegistry
}

// NewModel creates a new scope model and loads the custom scope registry.
func NewModel(cfg *config.RuntimeConfig) *Model {
	m := &Model{
		cfg:       cfg,
		startedAt: time.Now(),
	}
	m.loadRegistry()
	return m
}

// loadRegistry loads the custom scope registry from disk.
func (m *Model) loadRegistry() {
	registryPath := os.ExpandEnv("~/.omnimemora/config/scope_registry.json")
	data, err := os.ReadFile(registryPath)
	if err != nil {
		// File doesn't exist yet — start with empty registry
		m.registry = &CustomScopeRegistry{CustomScopes: []CustomScopeDef{}}
		return
	}
	var reg CustomScopeRegistry
	if err := json.Unmarshal(data, &reg); err != nil {
		m.registry = &CustomScopeRegistry{CustomScopes: []CustomScopeDef{}}
		return
	}
	m.registry = &reg
}

// lookupCustomScope finds a custom scope definition by ID.
func (m *Model) lookupCustomScope(id string) *CustomScopeDef {
	for _, cs := range m.registry.CustomScopes {
		if cs.ID == id {
			return &cs
		}
	}
	return nil
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
		if scopeRef.CustomScopeID == "" {
			return fmt.Errorf("custom_scope_id required for custom scope")
		}
		cs := m.lookupCustomScope(scopeRef.CustomScopeID)
		if cs == nil {
			return fmt.Errorf("custom scope %q not found in registry", scopeRef.CustomScopeID)
		}
		// Check user is in allowed list
		if len(cs.AllowedUsers) > 0 {
			found := false
			for _, u := range cs.AllowedUsers {
				if u == scopeRef.UserID {
					found = true
					break
				}
			}
			if !found {
				return fmt.Errorf("user %q not in allowed list for custom scope %q", scopeRef.UserID, scopeRef.CustomScopeID)
			}
		}
		// Reject writes to shared_read_only custom scopes
		if cs.DefaultMode == string(pkg.SharingModeSharedReadOnly) {
			return fmt.Errorf("custom scope %q is read-only", scopeRef.CustomScopeID)
		}
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
		if scopeRef.CustomScopeID == "" {
			return fmt.Errorf("custom_scope_id required for custom scope")
		}
		cs := m.lookupCustomScope(scopeRef.CustomScopeID)
		if cs == nil {
			return fmt.Errorf("custom scope %q not found in registry", scopeRef.CustomScopeID)
		}
		// Check user is in allowed list
		if len(cs.AllowedUsers) > 0 {
			found := false
			for _, u := range cs.AllowedUsers {
				if u == scopeRef.UserID {
					found = true
					break
				}
			}
			if !found {
				return fmt.Errorf("user %q not in allowed list for custom scope %q", scopeRef.UserID, scopeRef.CustomScopeID)
			}
		}
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
