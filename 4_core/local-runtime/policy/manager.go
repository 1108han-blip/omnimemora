// policy/manager.go - Compile Strategy Policy Manager
// Aligns with DECISION-CSP-001 Section 4
package policy

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/omnimemora/local-runtime/app/context"
)

// Manager loads, validates, and serves the active compile strategy policy.
// All methods are safe for concurrent use. Invalid policy never causes a runtime
// error; the manager falls back to built-in runtime constants in that case.
type Manager struct {
	mu             sync.RWMutex
	activePolicy  *CompileStrategyPolicy
	resolved      *ResolvedDefaults
	candidate     *CompileStrategyPolicy
	policyDir     string
	manifestPath  string
}

// NewManager creates a policy manager rooted at policyDir.
// If manifestPath is empty the default "config/compile_strategy_policies/manifest.json"
// is used relative to the binary working directory.
// If the policy directory cannot be read the manager initialises with built-in
// defaults (never returns an error).
func NewManager(policyDir string) *Manager {
	if policyDir == "" {
		// Default to the bundled config directory
		policyDir = "config/compile_strategy_policies"
	}

	m := &Manager{
		policyDir:    policyDir,
		manifestPath: filepath.Join(policyDir, "manifest.json"),
	}
	m.initBuiltin()
	return m
}

// initBuiltin seeds the manager with hardcoded built-in defaults so that
// LoadActive and ResolveAuto always have a working baseline.
func (m *Manager) initBuiltin() {
	builtin := &CompileStrategyPolicy{
		Version:                 "builtin",
		DefaultContextStrategy:  context.DefaultStrategy,
		AllowedStrategies:       []string{"topk_excerpt", "recency_boost_select", "diversity_select"},
		AutoResolution: &AutoResolutionConfig{
			Enabled: true,
			Rules: AutoResolutionRules{
				QuestionPatterns:        "topk_excerpt",
				LongQueryThresholdChars: 50,
				LongQueryStrategy:       "diversity_select",
				DefaultStrategy:         "recency_boost_select",
			},
		},
		ModeDefaults: map[string]ModeDefaults{
			"precise":    {TokenBudget: 300,  MaxItems: 3},
			"balanced":   {TokenBudget: 800,  MaxItems: 6},
			"aggressive": {TokenBudget: 1500, MaxItems: 10},
		},
	}
	defaults := modeDefaultsFromPolicy(builtin)
	m.resolved = &ResolvedDefaults{
		DefaultStrategy: builtin.DefaultContextStrategy,
		ModeDefaults:    defaults,
		AutoEnabled:     true,
		AutoRules:       &builtin.AutoResolution.Rules,
		PolicyVersion:   "builtin",
		PolicySource:    PolicySourceBuiltIn,
	}
	m.activePolicy = builtin
}

// LoadActive reads the manifest, finds the active version, loads the corresponding
// policy file, and caches it. Missing or invalid files fall back to built-in defaults
// silently. This method is idempotent; subsequent calls refresh the cache.
func (m *Manager) LoadActive() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	manifest, err := m.readManifestNoLock()
	if err != nil {
		// Manifest missing or unreadable — keep built-in defaults
		return nil
	}

	activeVersion := manifest.ActiveVersion
	for _, v := range manifest.Versions {
		if v.Version != activeVersion {
			continue
		}
		policy, err := m.readPolicyFile(v.PolicyFile)
		if err != nil {
			// Policy file missing or unreadable — keep built-in defaults
			return nil
		}
		policy = m.validatePolicy(policy)
		m.activePolicy = policy
		m.resolved = m.resolveDefaultsNoLock(policy, string(v.Source))
		return nil
	}

	// Active version not found in manifest — keep built-in defaults
	return nil
}

// LoadCandidate reads the manifest and loads any present candidate version
// without activating it. Returns nil, nil if no candidate is configured.
func (m *Manager) LoadCandidate() (*CompileStrategyPolicy, error) {
	m.mu.RLock()
	manifest, err := m.readManifestNoLock()
	m.mu.RUnlock()
	if err != nil {
		return nil, nil // No manifest — no candidate
	}

	if manifest.CandidateVersion == nil || *manifest.CandidateVersion == "" {
		return nil, nil
	}

	for _, v := range manifest.Versions {
		if v.Version != *manifest.CandidateVersion {
			continue
		}
		policy, err := m.readPolicyFile(v.PolicyFile)
		if err != nil {
			return nil, nil // Candidate file missing — not an error
		}
		candidate := m.validatePolicy(policy)
		m.mu.Lock()
		m.candidate = candidate
		m.mu.Unlock()
		return candidate, nil
	}

	return nil, nil
}

// PromoteCandidate moves the loaded candidate to active by updating the manifest.
// Returns an error if no candidate is currently loaded.
// This is NOT an automatic operation — it requires an explicit call.
func (m *Manager) PromoteCandidate() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.candidate == nil {
		return fmt.Errorf("promote: no candidate policy loaded")
	}

	// Read manifest
	manifest, err := m.readManifestNoLock()
	if err != nil {
		return fmt.Errorf("promote: cannot read manifest: %w", err)
	}

	// Update active_version to candidate version
	newActive := m.candidate.Version
	manifest.ActiveVersion = newActive

	// Mark previously active as inactive, candidate as active
	for i := range manifest.Versions {
		if manifest.Versions[i].Version == newActive {
			manifest.Versions[i].Status = "active"
		} else if manifest.Versions[i].Status == "active" {
			manifest.Versions[i].Status = "superseded"
		}
	}
	manifest.CandidateVersion = nil

	// Write manifest back
	if err := m.writeManifestNoLock(manifest); err != nil {
		return fmt.Errorf("promote: cannot write manifest: %w", err)
	}

	// Update in-memory state
	m.activePolicy = m.candidate
	m.candidate = nil
	m.resolved = m.resolveDefaultsNoLock(m.activePolicy, string(PolicySourceLocal))

	return nil
}

// ResolveAuto applies the active policy's auto-resolution rules to a query string.
// Returns the resolved strategy name. Falls back to built-in defaults if the
// active policy is absent or invalid. This method does NOT make network calls.
func (m *Manager) ResolveAuto(query string) string {
	m.mu.RLock()
	resolved := m.resolved
	m.mu.RUnlock()

	if resolved == nil || !resolved.AutoEnabled || resolved.AutoRules == nil {
		// Fall back to built-in auto resolution
		return context.ResolveAutoStrategy(query)
	}

	rules := resolved.AutoRules
	q := strings.ToLower(strings.TrimSpace(query))

	// Question patterns
	if strings.Contains(q, "?") ||
		strings.HasPrefix(q, "what") ||
		strings.HasPrefix(q, "how") ||
		strings.HasPrefix(q, "why") ||
		strings.HasPrefix(q, "when") ||
		strings.HasPrefix(q, "where") ||
		strings.HasPrefix(q, "who") {
		return rules.QuestionPatterns
	}

	// Long query
	if len(query) > rules.LongQueryThresholdChars {
		return rules.LongQueryStrategy
	}

	return rules.DefaultStrategy
}

// GetModeDefaults returns the mode defaults from the active policy.
// Returns the built-in defaults if the active policy is absent or invalid.
func (m *Manager) GetModeDefaults(mode string) (tokenBudget, maxItems int) {
	m.mu.RLock()
	resolved := m.resolved
	m.mu.RUnlock()

	if resolved != nil && resolved.ModeDefaults != nil {
		if d, ok := resolved.ModeDefaults[mode]; ok {
			return d.TokenBudget, d.MaxItems
		}
	}

	// Built-in fallback: mirror StrategyOptions.GetDefaults()
	switch mode {
	case "precise":
		return 300, 3
	case "aggressive":
		return 1500, 10
	default:
		return 800, 6
	}
}

// GetDefaultStrategy returns the default strategy from the active policy.
func (m *Manager) GetDefaultStrategy() string {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.resolved != nil {
		return m.resolved.DefaultStrategy
	}
	return context.DefaultStrategy
}

// GetResolved returns the full resolved defaults for the active policy.
// Used by callers that need to emit evidence (policy version, source, etc.).
func (m *Manager) GetResolved() *ResolvedDefaults {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.resolved == nil {
		return &ResolvedDefaults{
			DefaultStrategy: context.DefaultStrategy,
			PolicyVersion:   "builtin",
			PolicySource:    PolicySourceBuiltIn,
			AutoEnabled:     true,
			ModeDefaults: map[string]ModeDefaults{
				"precise":    {TokenBudget: 300,  MaxItems: 3},
				"balanced":   {TokenBudget: 800,  MaxItems: 6},
				"aggressive": {TokenBudget: 1500, MaxItems: 10},
			},
		}
	}
	return m.resolved
}

// InvalidateCache forces the manager to reload the manifest and active policy
// on the next call to LoadActive. Call this after external changes to the
// policy directory.
func (m *Manager) InvalidateCache() {
	m.mu.Lock()
	defer m.mu.Unlock()
	// Keep built-in as baseline; next LoadActive will re-read
}

// GetActivePolicy returns the currently active policy (or built-in fallback).
func (m *Manager) GetActivePolicy() *CompileStrategyPolicy {
	m.mu.RLock()
	defer m.mu.RUnlock()
	if m.activePolicy != nil {
		return m.activePolicy
	}
	return &CompileStrategyPolicy{
		Version:                "builtin",
		DefaultContextStrategy: context.DefaultStrategy,
	}
}

// --- private helpers ---

func (m *Manager) readManifest() (*Manifest, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.readManifestNoLock()
}

func (m *Manager) readManifestNoLock() (*Manifest, error) {
	data, err := os.ReadFile(m.manifestPath)
	if err != nil {
		return nil, err
	}
	var manifest Manifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return nil, err
	}
	return &manifest, nil
}

func (m *Manager) writeManifestNoLock(manifest *Manifest) error {
	data, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(m.manifestPath, data, 0644)
}

func (m *Manager) readPolicyFile(filename string) (*CompileStrategyPolicy, error) {
	if filename == "" {
		return nil, fmt.Errorf("empty policy filename")
	}
	path := filepath.Join(m.policyDir, filename)
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var policy CompileStrategyPolicy
	if err := json.Unmarshal(data, &policy); err != nil {
		return nil, err
	}
	return &policy, nil
}

// validatePolicy ensures the policy has at least a valid default strategy.
// Unknown extra fields are ignored; missing fields fall back to built-in.
func (m *Manager) validatePolicy(policy *CompileStrategyPolicy) *CompileStrategyPolicy {
	if policy == nil {
		return nil
	}
	// Ensure default strategy is non-empty and is a known strategy
	if policy.DefaultContextStrategy == "" {
		policy.DefaultContextStrategy = context.DefaultStrategy
	}
	if context.GetStrategy(policy.DefaultContextStrategy) == nil {
		policy.DefaultContextStrategy = context.DefaultStrategy
	}
	// Ensure at least one allowed strategy
	if len(policy.AllowedStrategies) == 0 {
		policy.AllowedStrategies = []string{"topk_excerpt", "recency_boost_select", "diversity_select"}
	}
	// Ensure mode defaults are present
	if policy.ModeDefaults == nil {
		policy.ModeDefaults = map[string]ModeDefaults{
			"precise":    {TokenBudget: 300,  MaxItems: 3},
			"balanced":   {TokenBudget: 800,  MaxItems: 6},
			"aggressive": {TokenBudget: 1500, MaxItems: 10},
		}
	}
	return policy
}

func (m *Manager) resolveDefaults(policy *CompileStrategyPolicy, source string) *ResolvedDefaults {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.resolveDefaultsNoLock(policy, source)
}

func (m *Manager) resolveDefaultsNoLock(policy *CompileStrategyPolicy, source string) *ResolvedDefaults {
	if policy == nil {
		return &ResolvedDefaults{
			DefaultStrategy: context.DefaultStrategy,
			PolicyVersion:   "builtin",
			PolicySource:    PolicySourceBuiltIn,
			AutoEnabled:     true,
		}
	}

	modeDefaults := modeDefaultsFromPolicy(policy)

	autoRules := policy.AutoResolution
	if policy.AutoResolution == nil {
		autoRules = &AutoResolutionConfig{
			Enabled: true,
			Rules: AutoResolutionRules{
				QuestionPatterns:        "topk_excerpt",
				LongQueryThresholdChars:  50,
				LongQueryStrategy:        "diversity_select",
				DefaultStrategy:          "recency_boost_select",
			},
		}
	}

	return &ResolvedDefaults{
		DefaultStrategy: policy.DefaultContextStrategy,
		ModeDefaults:    modeDefaults,
		AutoEnabled:     autoRules.Enabled,
		AutoRules:       &autoRules.Rules,
		PolicyVersion:   policy.Version,
		PolicySource:    PolicySource(source),
	}
}

func modeDefaultsFromPolicy(policy *CompileStrategyPolicy) map[string]ModeDefaults {
	if policy.ModeDefaults == nil {
		return map[string]ModeDefaults{
			"precise":    {TokenBudget: 300,  MaxItems: 3},
			"balanced":   {TokenBudget: 800,  MaxItems: 6},
			"aggressive": {TokenBudget: 1500, MaxItems: 10},
		}
	}
	return policy.ModeDefaults
}
