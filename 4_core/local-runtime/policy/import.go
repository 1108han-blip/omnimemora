// policy/import.go - CSP-001 Candidate Pack Local Import
// Repo-only, no cloud download, no promotion, no Codex validation.
package policy

import (
	"encoding/json"
	"fmt"
	"os"
)

// ImportCandidate reads a candidate pack JSON from path, validates it, and
// calls AcceptCandidate to write it into the local candidate cache.
// policyDir is the policy directory; use "" for auto-discovery (CLI default).
// Returns the accepted CandidatePack on success.
// On any error the process exits with code 1; no partial state is left.
func ImportCandidate(path, policyDir string) (*CandidatePack, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read file %q: %w", path, err)
	}

	var pack CandidatePack
	if err := json.Unmarshal(data, &pack); err != nil {
		return nil, fmt.Errorf("parse JSON: %w", err)
	}

	// Basic structural validation before handing off to Manager
	if err := pack.Validate(); err != nil {
		return nil, fmt.Errorf("candidate pack validation failed: %w", err)
	}

	manager := NewManager(policyDir)
	if err := manager.AcceptCandidate(&pack); err != nil {
		return nil, err
	}

	return &pack, nil
}

// PolicyStatus describes the separation between active and candidate versions.
type PolicyStatus struct {
	ActiveVersion    string
	ActiveSource     string
	CandidateVersion *string // nil when no candidate is staged
	CandidateSource  string  // empty when no candidate
}

// GetPolicyStatus returns the current active and candidate version info
// without loading the full policy into memory.
// policyDir is the policy directory; use "" for auto-discovery (CLI default).
func GetPolicyStatus(policyDir string) *PolicyStatus {
	manager := NewManager(policyDir)
	// Load active policy so that GetResolved returns the manifest-based version
	// rather than the built-in fallback.
	_ = manager.LoadActive()
	resolved := manager.GetResolved()
	info, _ := manager.GetCandidateInfo()

	status := &PolicyStatus{
		ActiveVersion: resolved.PolicyVersion,
		ActiveSource:  string(resolved.PolicySource),
	}
	if info != nil {
		status.CandidateVersion = &info.PolicyVersion
		status.CandidateSource = string(info.Source)
	}
	return status
}

// Exit codes for the import command
const (
	ExitOK              = 0
	ExitInvalidArgs     = 1
	ExitFileRead        = 1
	ExitValidation      = 1
	ExitHashMismatch    = 1
	ExitActiveOverwrite = 1
	ExitManifestWrite   = 1
)
