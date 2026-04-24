// policy/manager.go - Compile Strategy Policy Manager
// Aligns with DECISION-CSP-001 Section 4
package policy

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/omnimemora/local-runtime/app/context"
)

// CandidateFetcher is implemented by sources that can supply a CandidatePack.
// The interface is intentionally narrow — callers provide metadata (bytes, source)
// and the implementation is free to fetch from network, filesystem, or in-process
// generation. No concrete implementations exist in this batch; the interface
// exists to define the contract for future Cloudflare/Railway/embedding sources.
type CandidateFetcher interface {
	// Fetch returns a validated CandidatePack for the given candidateID, or an error.
	// Implementations must return packs that already pass CandidatePack.Validate().
	Fetch(candidateID string, policyJSON []byte) (*CandidatePack, error)
}

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
//
// When policyDir is empty, it resolves the policy directory by checking, in order:
//
//  1. A "config/compile_strategy_policies/" subdirectory of the binary's own
//     directory (promotion-bundle layout: binary lives in
//     ~/.omnimemora/service/current/tools/ and the policy directory lives at
//     ~/.omnimemora/service/current/tools/config/compile_strategy_policies/).
//  2. A "config/compile_strategy_policies/" subdirectory of the current
//     working directory (repo / dev layout).
//
// If neither exists the manager initialises with built-in defaults and never
// returns an error — LoadActive will fall back to the built-in policy silently.
func NewManager(policyDir string) *Manager {
	if policyDir != "" {
		// Explicit path provided (useful for tests or custom deployments)
		m := &Manager{
			policyDir:    policyDir,
			manifestPath: filepath.Join(policyDir, "manifest.json"),
		}
		m.initBuiltin()
		return m
	}

	// Auto-discover: try binary-bundle layout first, then CWD layout.
	resolved := resolvePolicyDir("")
	m := &Manager{
		policyDir:    resolved,
		manifestPath: filepath.Join(resolved, "manifest.json"),
	}
	m.initBuiltin()
	return m
}

// resolvePolicyDir returns the effective policy directory path.
// If the path argument is non-empty, it is returned as-is.
// Otherwise, binary-bundle layout is checked first (sibling of the executable),
// then CWD layout, then a safe empty string (triggering built-in fallback).
func resolvePolicyDir(explicit string) string {
	if explicit != "" {
		return explicit
	}

	// 1. Try binary-bundle layout: binary_dir/config/compile_strategy_policies
	if exe, err := os.Executable(); err == nil {
		bundleDir := filepath.Join(filepath.Dir(exe), "config", "compile_strategy_policies")
		if fi, err := os.Stat(bundleDir); err == nil && fi.IsDir() {
			return bundleDir
		}
	}

	// 2. Try CWD layout: CWD/config/compile_strategy_policies
	cwdDir := filepath.Join("config", "compile_strategy_policies")
	if fi, err := os.Stat(cwdDir); err == nil && fi.IsDir() {
		return cwdDir
	}

	// 3. Not found — return empty so LoadActive falls back to built-in.
	return ""
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

// CandidateInfo holds metadata about the current candidate without loading the policy.
type CandidateInfo struct {
	CandidateID   string          `json:"candidate_id"`
	PolicyVersion string          `json:"policy_version"`
	SHA256        string          `json:"sha256"`
	SignatureStatus SignatureStatus `json:"signature_status"`
	Source        CandidateSource `json:"source"`
	FetchedAt     time.Time       `json:"fetched_at"`
}

// InvalidateCache forces the manager to reload the manifest and active policy
// on the next call to LoadActive. Call this after external changes to the
// policy directory.
func (m *Manager) InvalidateCache() {
	m.mu.Lock()
	defer m.mu.Unlock()
	// Keep built-in as baseline; next LoadActive will re-read
}

// AcceptCandidate validates and stores a candidate pack to disk, then updates
// the manifest's candidate_version field only. It does NOT change active_version.
// The active policy is unaffected until PromoteCandidate() is called explicitly.
// Returns an error if validation fails or the write fails; in that case the
// manifest is left unchanged.
func (m *Manager) AcceptCandidate(pack *CandidatePack) error {
	if err := pack.Validate(); err != nil {
		return fmt.Errorf("accept: candidate validation failed: %w", err)
	}

	// Verify SHA256 against canonical policy JSON
	canonical, err := json.Marshal(pack.Policy)
	if err != nil {
		return fmt.Errorf("accept: cannot marshal policy for hash: %w", err)
	}
	hash := sha256.Sum256(canonical)
	hexHash := hex.EncodeToString(hash[:])
	if hexHash != pack.SHA256 {
		return fmt.Errorf("accept: sha256 mismatch: expected %s, got %s", pack.SHA256, hexHash)
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	// Write candidate file
	candidatePath := filepath.Join(m.policyDir, pack.PolicyVersion+".json")
	if err := os.WriteFile(candidatePath, canonical, 0644); err != nil {
		return fmt.Errorf("accept: cannot write candidate file %s: %w", candidatePath, err)
	}

	// Read manifest; create from scratch if missing
	manifest, err := m.readManifestNoLock()
	if os.IsNotExist(err) {
		manifest = &Manifest{
			ActiveVersion:    "builtin",
			CandidateVersion: nil,
			Versions:         []PolicyVersion{},
		}
	} else if err != nil {
		return fmt.Errorf("accept: cannot read manifest: %w", err)
	}

	// Check that version is not already present as active
	for _, v := range manifest.Versions {
		if v.Version == pack.PolicyVersion && v.Status == "active" {
			return fmt.Errorf("accept: cannot overwrite active version %q", pack.PolicyVersion)
		}
	}

	// Update or append candidate version in manifest
	found := false
	for i := range manifest.Versions {
		if manifest.Versions[i].Version == pack.PolicyVersion {
			manifest.Versions[i] = PolicyVersion{
				Version:    pack.PolicyVersion,
				Status:     "candidate",
				PolicyFile: pack.PolicyVersion + ".json",
				Source:     string(pack.Source),
			}
			found = true
			break
		}
	}
	if !found {
		manifest.Versions = append(manifest.Versions, PolicyVersion{
			Version:    pack.PolicyVersion,
			Status:     "candidate",
			PolicyFile: pack.PolicyVersion + ".json",
			Source:     string(pack.Source),
		})
	}
	manifest.CandidateVersion = &pack.PolicyVersion

	// Write manifest atomically: write to temp then rename
	if err := m.writeManifestAtomicNoLock(manifest); err != nil {
		// Manifest write failed — remove candidate file to leave state unchanged
		os.Remove(candidatePath)
		return fmt.Errorf("accept: manifest write failed, candidate file removed: %w", err)
	}

	return nil
}

// GetCandidateInfo returns metadata about the current candidate without loading the policy.
func (m *Manager) GetCandidateInfo() (*CandidateInfo, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	manifest, err := m.readManifestNoLock()
	if err != nil {
		return nil, nil // No manifest — no candidate
	}

	if manifest.CandidateVersion == nil || *manifest.CandidateVersion == "" {
		return nil, nil
	}

	for _, v := range manifest.Versions {
		if v.Version == *manifest.CandidateVersion {
			return &CandidateInfo{
				CandidateID:      v.Version,
				PolicyVersion:    v.Version,
				Source:           CandidateSource(v.Source),
				SignatureStatus:  SignatureStatusNotRequired,
				FetchedAt:        v.VerifiedAt,
			}, nil
		}
	}
	return nil, nil
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

// writeManifestAtomicNoLock writes the manifest atomically by writing to a temp
// file and renaming it over the target. This ensures the manifest is never left
// in a partially-written state.
func (m *Manager) writeManifestAtomicNoLock(manifest *Manifest) error {
	data, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	tmp, err := os.CreateTemp(m.policyDir, "manifest-*.tmp")
	if err != nil {
		return fmt.Errorf("atomic manifest: cannot create temp file: %w", err)
	}
	tmpPath := tmp.Name()
	_, err = tmp.Write(data)
	if closeErr := tmp.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		os.Remove(tmpPath)
		return fmt.Errorf("atomic manifest: write failed: %w", err)
	}
	// Atomic rename
	if err := os.Rename(tmpPath, m.manifestPath); err != nil {
		os.Remove(tmpPath)
		return fmt.Errorf("atomic manifest: rename failed: %w", err)
	}
	return nil
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
