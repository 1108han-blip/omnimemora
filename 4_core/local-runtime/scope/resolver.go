// scope/resolver.go - Scope resolution from various sources
// Per RUNTIME_ARCHITECTURE.md Section 7.2, scope priority: Header > Body > Config
package scope

import (
	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/pkg"
)

// Resolver resolves scope from different sources
type Resolver struct {
	cfg *config.RuntimeConfig
}

// NewResolver creates a new scope resolver
func NewResolver(cfg *config.RuntimeConfig) *Resolver {
	return &Resolver{cfg: cfg}
}

// ResolveScopeRef resolves a ScopeRef from multiple sources
// Priority: Header > Body > Config
// Headers have highest priority for ALL fields
// Body values override Config defaults
// Config defaults are fallback for empty fields
// Note: scope-specific sharing_mode defaults (e.g. workspace->shared) are
// handled in service layer, not here
func (r *Resolver) ResolveScopeRef(
	headerAgent, headerUser, headerWorkspace string,
	headerScope, headerSharingMode, headerTenant string,
	bodyScopeRef *pkg.ScopeRef,
) *pkg.ScopeRef {
	// Determine effective scope first (may come from header/body/config)
	effectiveScope := pkg.ScopeType(r.cfg.Scope.Default)
	if headerScope != "" {
		effectiveScope = pkg.ScopeType(headerScope)
	} else if bodyScopeRef != nil && bodyScopeRef.Scope != "" {
		effectiveScope = bodyScopeRef.Scope
	}

	// Start with config defaults
	result := &pkg.ScopeRef{
		TenantID:    "",
		UserID:      r.cfg.Scope.DefaultWorkspace,
		WorkspaceID: r.cfg.Scope.DefaultWorkspace,
		AgentID:     "local",
		Scope:       effectiveScope,
		SharingMode: "", // Don't pre-fill - service layer handles workspace->shared
	}

	// Apply body values (second priority) - body overrides config
	if bodyScopeRef != nil {
		if bodyScopeRef.TenantID != "" {
			result.TenantID = bodyScopeRef.TenantID
		}
		if bodyScopeRef.UserID != "" {
			result.UserID = bodyScopeRef.UserID
		}
		if bodyScopeRef.WorkspaceID != "" {
			result.WorkspaceID = bodyScopeRef.WorkspaceID
		}
		if bodyScopeRef.AgentID != "" {
			result.AgentID = bodyScopeRef.AgentID
		}
		if bodyScopeRef.Scope != "" {
			result.Scope = bodyScopeRef.Scope
		}
		if bodyScopeRef.SharingMode != "" {
			result.SharingMode = bodyScopeRef.SharingMode
		}
	}

	// Apply header values (highest priority) - headers override everything
	if headerTenant != "" {
		result.TenantID = headerTenant
	}
	if headerUser != "" {
		result.UserID = headerUser
	}
	if headerWorkspace != "" {
		result.WorkspaceID = headerWorkspace
	}
	if headerAgent != "" {
		result.AgentID = headerAgent
	}
	if headerScope != "" {
		result.Scope = pkg.ScopeType(headerScope)
	}
	if headerSharingMode != "" {
		result.SharingMode = pkg.SharingMode(headerSharingMode)
	}

	return result
}
