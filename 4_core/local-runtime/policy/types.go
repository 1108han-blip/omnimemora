// policy/types.go - Compile Strategy Policy types
// Aligns with DECISION-CSP-001
package policy

import (
	"fmt"
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

// CandidateSource identifies where a candidate pack originated.
type CandidateSource string

const (
	CandidateSourceLocal CandidateSource = "local"
	CandidateSourceCloud CandidateSource = "cloud"
)

// SignatureStatus records the result of signature verification.
type SignatureStatus string

const (
	SignatureStatusNotRequired SignatureStatus = "not_required" // local skeleton — signatures out of scope for phase 1
	SignatureStatusValid        SignatureStatus = "valid"
	SignatureStatusInvalid      SignatureStatus = "invalid"
	SignatureStatusAbsent      SignatureStatus = "absent"
)

// CandidatePack represents a downloadable compile strategy policy candidate.
// It carries its own integrity hash and optional signature so callers can
// validate before writing to the local candidate store.
type CandidatePack struct {
	CandidateID      string          `json:"candidate_id"`
	PolicyVersion    string          `json:"policy_version"`
	Policy           *CompileStrategyPolicy `json:"policy"`
	SHA256           string          `json:"sha256"`
	Signature        *string         `json:"signature,omitempty"`
	SignatureStatus  SignatureStatus `json:"signature_status"`
	Source           CandidateSource `json:"source"`
	FetchedAt        time.Time       `json:"fetched_at"`
}

// Validate validates the candidate pack. Returns an error if required fields are
// missing or the policy is invalid. Unknown JSON fields are silently ignored.
// A pack that fails validation must never affect the active policy.
func (p *CandidatePack) Validate() error {
	if p.CandidateID == "" {
		return fmt.Errorf("candidate_id is required")
	}
	if p.PolicyVersion == "" {
		return fmt.Errorf("policy_version is required")
	}
	if p.Policy == nil {
		return fmt.Errorf("policy is nil")
	}
	if p.Policy.Version != p.PolicyVersion {
		return fmt.Errorf("policy.Version %q != candidate policy_version %q", p.Policy.Version, p.PolicyVersion)
	}
	if p.SHA256 == "" {
		return fmt.Errorf("sha256 is required")
	}
	return nil
}

// ResolvedDefaults holds the effective defaults derived from active policy.
type ResolvedDefaults struct {
	DefaultStrategy string
	ModeDefaults    map[string]ModeDefaults
	AutoEnabled     bool
	AutoRules       *AutoResolutionRules
	PolicyVersion   string
	PolicySource    PolicySource
}
