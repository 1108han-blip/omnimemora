// policy/types.go - Compile Strategy Policy types
// Aligns with DECISION-CSP-001
package policy

import (
	"time"
)

// CompileStrategyPolicy represents a versioned compile strategy policy document.
type CompileStrategyPolicy struct {
	Version                  string                    `json:"version"`
	Description             string                    `json:"description,omitempty"`
	DefaultContextStrategy  string                    `json:"default_context_strategy"`
	AllowedStrategies       []string                  `json:"allowed_strategies"`
	AutoResolution          *AutoResolutionConfig     `json:"auto_resolution,omitempty"`
	ModeDefaults            map[string]ModeDefaults   `json:"mode_defaults,omitempty"`
}

// AutoResolutionConfig controls how "auto" strategy is resolved.
type AutoResolutionConfig struct {
	Enabled bool                `json:"enabled"`
	Rules   AutoResolutionRules `json:"rules"`
}

// AutoResolutionRules mirrors the heuristics in app/context/strategy_auto.go.
type AutoResolutionRules struct {
	QuestionPatterns          string `json:"question_patterns"`
	LongQueryThresholdChars   int    `json:"long_query_threshold_chars"`
	LongQueryStrategy        string `json:"long_query_strategy"`
	DefaultStrategy          string `json:"default_strategy"`
}

// ModeDefaults defines token budget and max items for a given context mode.
type ModeDefaults struct {
	TokenBudget int `json:"token_budget"`
	MaxItems    int `json:"max_items"`
}

// PolicyVersion represents a single version entry in the manifest.
type PolicyVersion struct {
	Version    string    `json:"version"`
	Status     string    `json:"status"` // "active" | "candidate"
	PolicyFile string    `json:"policy_file"`
	Source     string    `json:"source"` // "bundled" | "local" | "cloud-candidate"
	VerifiedAt time.Time `json:"verified_at,omitempty"`
}

// Manifest tracks all known policy versions and the active/candidate state.
type Manifest struct {
	ActiveVersion    string          `json:"active_version"`
	CandidateVersion *string        `json:"candidate_version"`
	Versions         []PolicyVersion `json:"versions"`
}

// PolicySource identifies where the active policy originated.
type PolicySource string

const (
	PolicySourceBundled        PolicySource = "bundled"
	PolicySourceLocal          PolicySource = "local"
	PolicySourceCloudCandidate PolicySource = "cloud-candidate"
	PolicySourceBuiltIn        PolicySource = "builtin" // fallback when no policy file exists
)

// ResolvedDefaults holds the effective defaults derived from active policy.
type ResolvedDefaults struct {
	DefaultStrategy string
	ModeDefaults    map[string]ModeDefaults
	AutoEnabled     bool
	AutoRules       *AutoResolutionRules
	PolicyVersion   string
	PolicySource    PolicySource
}
