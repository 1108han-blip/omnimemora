// policy/cloud_source.go - CSP-001 Real Cloud Candidate Source
// Pull-style fetch from configurable URL; no auto-promote, no compile hot-path.
package policy

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// CloudCandidateFetcher fetches a candidate pack from an HTTP URL.
// It implements the CandidateFetcher interface. Each call makes one HTTP GET.
// No background polling; each Fetch is a discrete operator-triggered action.
type CloudCandidateFetcher struct {
	Client  *http.Client
	BaseURL string
}

// NewCloudCandidateFetcher creates a fetcher rooted at baseURL.
// The caller is responsible for ensuring baseURL points to the correct
// candidate distribution endpoint. baseURL may include a trailing slash.
func NewCloudCandidateFetcher(baseURL string) *CloudCandidateFetcher {
	if !strings.HasSuffix(baseURL, "/") {
		baseURL += "/"
	}
	return &CloudCandidateFetcher{
		Client: &http.Client{
			Timeout: 30 * time.Second,
		},
		BaseURL: baseURL,
	}
}

// Fetch fetches a candidate pack from baseURL/<candidateID>.json.
// It validates the pack, computes the canonical SHA-256, and returns
// a CandidatePack with Source=cloud and FetchedAt=now.
// Returns an error on HTTP failure, non-200 status, JSON parse failure,
// or pack validation failure.
func (f *CloudCandidateFetcher) Fetch(candidateID string, policyJSON []byte) (*CandidatePack, error) {
	url := f.BaseURL + candidateID + ".json"

	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("fetch: cannot build request for %q: %w", url, err)
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "OmniMemora-CloudCandidateFetcher/1.0")

	resp, err := f.Client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetch: HTTP request failed for %q: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return nil, fmt.Errorf("fetch: HTTP %d from %q (body: %q)", resp.StatusCode, url, string(body))
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("fetch: cannot read response body from %q: %w", url, err)
	}

	var raw struct {
		CandidateID     string          `json:"candidate_id"`
		PolicyVersion   string          `json:"policy_version"`
		Policy          json.RawMessage `json:"policy"`
		SHA256          string          `json:"sha256"`
		Signature       *string         `json:"signature,omitempty"`
		SignatureStatus string          `json:"signature_status"`
		Source          string          `json:"source"`
		FetchedAt       string          `json:"fetched_at"`
	}
	if err := json.Unmarshal(body, &raw); err != nil {
		return nil, fmt.Errorf("fetch: cannot parse JSON from %q: %w", url, err)
	}

	// Parse the embedded policy object
	var policy CompileStrategyPolicy
	if err := json.Unmarshal(raw.Policy, &policy); err != nil {
		return nil, fmt.Errorf("fetch: cannot parse policy from %q: %w", url, err)
	}

	// Verify policy.Version matches policy_version field
	if policy.Version != raw.PolicyVersion {
		return nil, fmt.Errorf("fetch: policy.Version %q != policy_version %q", policy.Version, raw.PolicyVersion)
	}

	// Re-marshal canonical policy and verify SHA-256
	canonical, err := json.Marshal(&policy)
	if err != nil {
		return nil, fmt.Errorf("fetch: cannot re-marshal policy for hash: %w", err)
	}
	h := sha256.Sum256(canonical)
	hexHash := hex.EncodeToString(h[:])
	if hexHash != raw.SHA256 {
		return nil, fmt.Errorf("fetch: sha256 mismatch for candidate %q (expected %s, got %s)", candidateID, raw.SHA256, hexHash)
	}

	pack := &CandidatePack{
		CandidateID:   raw.CandidateID,
		PolicyVersion: raw.PolicyVersion,
		Policy:        &policy,
		SHA256:        raw.SHA256,
		Source:        CandidateSourceCloud,
		FetchedAt:     time.Now(),
	}

	if raw.Signature != nil {
		pack.Signature = raw.Signature
	}
	if raw.SignatureStatus != "" {
		pack.SignatureStatus = SignatureStatus(raw.SignatureStatus)
	} else {
		pack.SignatureStatus = SignatureStatusNotRequired
	}

	return pack, nil
}

// FetchWithManager fetches a candidate pack and accepts it via manager.AcceptCandidate.
// This is the canonical entry point for the CLI; it combines fetch + accept.
// On any error the manifest and candidate file are left unchanged.
func FetchWithManager(baseURL, candidateID, policyDir string) (*CandidatePack, error) {
	fetcher := NewCloudCandidateFetcher(baseURL)
	// policyJSON is unused by CloudCandidateFetcher (it reads from the network)
	pack, err := fetcher.Fetch(candidateID, nil)
	if err != nil {
		return nil, err
	}

	manager := NewManager(policyDir)
	if err := manager.AcceptCandidate(pack); err != nil {
		return nil, err
	}

	return pack, nil
}
