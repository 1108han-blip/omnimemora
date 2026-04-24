// policy/cloud_source_test.go - CSP-001 Real Cloud Candidate Source tests
package policy

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

// makeTestPackFromPolicy builds a CandidatePack with correct SHA-256 from a policy JSON string.
// policyJSON must be a valid CompileStrategyPolicy JSON (no extra fields).
func makeTestPackFromPolicy(t *testing.T, policyJSON string) *CandidatePack {
	var cleanPolicy CompileStrategyPolicy
	if err := json.Unmarshal([]byte(policyJSON), &cleanPolicy); err != nil {
		t.Fatalf("failed to parse policy JSON: %v", err)
	}
	canonical, err := json.Marshal(&cleanPolicy)
	if err != nil {
		t.Fatalf("failed to marshal policy for hash: %v", err)
	}
	h := sha256.Sum256(canonical)
	return &CandidatePack{
		CandidateID:     cleanPolicy.Version,
		PolicyVersion:   cleanPolicy.Version,
		Policy:          &cleanPolicy,
		SHA256:          hex.EncodeToString(h[:]),
		SignatureStatus: SignatureStatusNotRequired,
		Source:          CandidateSourceCloud,
		FetchedAt:       time.Now(),
	}
}

// writeActivePolicy creates a temp dir with an active policy file and manifest.
func writeActivePolicy(t *testing.T, version, defaultStrategy string) (string, func()) {
	dir, cleanup := tempPolicyDir(t)
	policyJSON := fmt.Sprintf(`{
  "version": %q,
  "default_context_strategy": %q,
  "allowed_strategies": ["topk_excerpt", "recency_boost_select", "diversity_select"],
  "auto_resolution": {
    "enabled": true,
    "rules": {
      "question_patterns": "topk_excerpt",
      "long_query_threshold_chars": 50,
      "long_query_strategy": "diversity_select",
      "default_strategy": "recency_boost_select"
    }
  },
  "mode_defaults": {
    "precise":   { "token_budget": 300, "max_items": 3 },
    "balanced":  { "token_budget": 800, "max_items": 6 },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`, version, defaultStrategy)
	writeFile(t, dir, "manifest.json", fmt.Sprintf(`{
  "active_version": %q,
  "candidate_version": null,
  "versions": [
    {
      "version": %q,
      "status": "active",
      "policy_file": %q,
      "source": "bundled"
    }
  ]
}`, version, version, version+".json"))
	writeFile(t, dir, version+".json", policyJSON)
	return dir, cleanup
}

// makeServer returns a httptest.Server that calls handler(responseBody, statusCode).
func makeServer(t *testing.T, responseBody string, statusCode int) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(statusCode)
		w.Write([]byte(responseBody))
	}))
}

// --- Test 1: Valid pack ---

func TestCloudFetch_ValidPack(t *testing.T) {
	dir, cleanup := writeActivePolicy(t, "active-v1", "topk_excerpt")
	defer cleanup()

	// Build a valid candidate pack JSON server-side
	policyJSON := `{
  "version": "cloud-v2",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"],
  "auto_resolution": {
    "enabled": true,
    "rules": {
      "question_patterns": "topk_excerpt",
      "long_query_threshold_chars": 50,
      "long_query_strategy": "diversity_select",
      "default_strategy": "recency_boost_select"
    }
  },
  "mode_defaults": {
    "precise":   { "token_budget": 300, "max_items": 3 },
    "balanced":  { "token_budget": 800, "max_items": 6 },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`
	pack := makeTestPackFromPolicy(t, policyJSON)
	candJSON, _ := json.Marshal(pack)

	server := makeServer(t, string(candJSON), http.StatusOK)
	defer server.Close()

	// Fetch via FetchWithManager
	result, err := FetchWithManager(server.URL, "cloud-v2", dir)
	if err != nil {
		t.Fatalf("FetchWithManager failed: %v", err)
	}
	if result.PolicyVersion != "cloud-v2" {
		t.Errorf("expected policy_version cloud-v2, got %s", result.PolicyVersion)
	}
	if result.Source != CandidateSourceCloud {
		t.Errorf("expected source cloud, got %s", result.Source)
	}

	// Verify manifest updated
	manifest, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("failed to read manifest: %v", err)
	}
	if manifest.ActiveVersion != "active-v1" {
		t.Errorf("active_version should remain active-v1, got %s", manifest.ActiveVersion)
	}
	if manifest.CandidateVersion == nil || *manifest.CandidateVersion != "cloud-v2" {
		t.Errorf("candidate_version should be cloud-v2, got %v", manifest.CandidateVersion)
	}
}

// --- Test 2: Hash mismatch ---

func TestCloudFetch_HashMismatch(t *testing.T) {
	dir, cleanup := writeActivePolicy(t, "active-v1", "topk_excerpt")
	defer cleanup()

	policyJSON := `{
  "version": "cloud-v2",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"]
}`
	badHash := "deadbeef00000000000000000000000000000000000000000000000000000000"
	// Return a pack with a wrong SHA-256
	candJSON := fmt.Sprintf(`{
  "candidate_id": "cloud-v2",
  "policy_version": "cloud-v2",
  "policy": %s,
  "sha256": "%s",
  "signature_status": "not_required",
  "source": "cloud",
  "fetched_at": "2026-04-24T10:00:00Z"
}`, policyJSON, badHash)

	server := makeServer(t, candJSON, http.StatusOK)
	defer server.Close()

	_, err := FetchWithManager(server.URL, "cloud-v2", dir)
	if err == nil {
		t.Error("FetchWithManager should fail on hash mismatch")
	}

	// Manifest unchanged
	manifest, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("failed to read manifest: %v", err)
	}
	if manifest.CandidateVersion != nil {
		t.Error("candidate_version should still be nil after hash mismatch")
	}
}

// --- Test 3: HTTP/Network failure ---

func TestCloudFetch_HTTPFailure(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	// Server that always returns 500
	server := makeServer(t, `{"error":"internal error"}`, http.StatusInternalServerError)
	serverURL := server.URL
	server.Close()

	_, err := FetchWithManager(serverURL, "cloud-v2", dir)
	if err == nil {
		t.Error("FetchWithManager should fail on HTTP 500")
	}

	// Manifest unchanged: if a manifest was created, candidate_version must still be nil
	manifestPath := filepath.Join(dir, "manifest.json")
	if _, err := os.Stat(manifestPath); err == nil {
		// Manifest exists — check candidate_version is still nil
		manifest, err := readManifestFromPath(manifestPath)
		if err != nil {
			t.Fatalf("failed to read manifest: %v", err)
		}
		if manifest.CandidateVersion != nil {
			t.Error("candidate_version should still be nil after HTTP failure")
		}
	}
	// If manifest does not exist, that's correct — nothing was written
}

func TestCloudFetch_ConnectionRefused(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	// No server listening on this port — connection refused
	_, err := FetchWithManager("http://127.0.0.1:59999", "cloud-v2", dir)
	if err == nil {
		t.Error("FetchWithManager should fail on connection refused")
	}
}

// --- Test 4: Malformed JSON ---

func TestCloudFetch_MalformedJSON(t *testing.T) {
	dir, cleanup := writeActivePolicy(t, "active-v1", "topk_excerpt")
	defer cleanup()

	server := makeServer(t, `{ not valid json }`, http.StatusOK)
	defer server.Close()

	_, err := FetchWithManager(server.URL, "cloud-v2", dir)
	if err == nil {
		t.Error("FetchWithManager should fail on malformed JSON")
	}
}

func TestCloudFetch_MissingRequiredFields(t *testing.T) {
	dir, cleanup := writeActivePolicy(t, "active-v1", "topk_excerpt")
	defer cleanup()

	// Missing sha256
	malformedJSON := `{
  "candidate_id": "cloud-v2",
  "policy_version": "cloud-v2",
  "policy": {"version": "cloud-v2", "default_context_strategy": "topk_excerpt"},
  "signature_status": "not_required",
  "source": "cloud",
  "fetched_at": "2026-04-24T10:00:00Z"
}`
	server := makeServer(t, malformedJSON, http.StatusOK)
	defer server.Close()

	_, err := FetchWithManager(server.URL, "cloud-v2", dir)
	if err == nil {
		t.Error("FetchWithManager should fail on missing sha256")
	}
}

// --- Test 5: Active overwrite attempt ---

func TestCloudFetch_ActiveOverwriteAttempt(t *testing.T) {
	dir, cleanup := writeActivePolicy(t, "active-v1", "topk_excerpt")
	defer cleanup()

	// Try to fetch a candidate with the same version as the active policy
	policyJSON := fmt.Sprintf(`{
  "version": "active-v1",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"]
}`)
	pack := makeTestPackFromPolicy(t, policyJSON)
	candJSON, _ := json.Marshal(pack)

	server := makeServer(t, string(candJSON), http.StatusOK)
	defer server.Close()

	_, err := FetchWithManager(server.URL, "active-v1", dir)
	if err == nil {
		t.Error("FetchWithManager should fail when candidate version matches active version")
	}

	// Manifest unchanged
	manifest, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("failed to read manifest: %v", err)
	}
	if manifest.CandidateVersion != nil {
		t.Error("candidate_version should still be nil after active-overwrite attempt")
	}
}

// --- Test 6: No manifest (new manifest created) ---

func TestCloudFetch_NewManifestCreated(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	// No manifest at all

	policyJSON := `{
  "version": "cloud-v2",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"]
}`
	pack := makeTestPackFromPolicy(t, policyJSON)
	candJSON, _ := json.Marshal(pack)

	server := makeServer(t, string(candJSON), http.StatusOK)
	defer server.Close()

	result, err := FetchWithManager(server.URL, "cloud-v2", dir)
	if err != nil {
		t.Fatalf("FetchWithManager failed: %v", err)
	}
	if result.PolicyVersion != "cloud-v2" {
		t.Errorf("expected policy_version cloud-v2, got %s", result.PolicyVersion)
	}

	// Manifest should have been created
	manifest, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("manifest should be created: %v", err)
	}
	if manifest.ActiveVersion != "builtin" {
		t.Errorf("active_version should default to builtin, got %s", manifest.ActiveVersion)
	}
	if manifest.CandidateVersion == nil || *manifest.CandidateVersion != "cloud-v2" {
		t.Errorf("candidate_version should be cloud-v2, got %v", manifest.CandidateVersion)
	}
}

// --- Test 7: Fetch does not affect active policy ---

func TestCloudFetch_DoesNotAffectActive(t *testing.T) {
	dir, cleanup := writeActivePolicy(t, "active-v1", "topk_excerpt")
	defer cleanup()

	policyJSON := `{
  "version": "cloud-v2",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"],
  "auto_resolution": {
    "enabled": true,
    "rules": {
      "question_patterns": "topk_excerpt",
      "long_query_threshold_chars": 50,
      "long_query_strategy": "diversity_select",
      "default_strategy": "recency_boost_select"
    }
  },
  "mode_defaults": {
    "precise":   { "token_budget": 100, "max_items": 1 },
    "balanced":  { "token_budget": 200, "max_items": 2 },
    "aggressive": { "token_budget": 400, "max_items": 4 }
  }
}`
	pack := makeTestPackFromPolicy(t, policyJSON)
	candJSON, _ := json.Marshal(pack)

	server := makeServer(t, string(candJSON), http.StatusOK)
	defer server.Close()

	// Fetch the candidate
	_, err := FetchWithManager(server.URL, "cloud-v2", dir)
	if err != nil {
		t.Fatalf("FetchWithManager failed: %v", err)
	}

	// Load active — must still be active-v1
	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}
	resolved := m.GetResolved()
	if resolved.DefaultStrategy != "topk_excerpt" {
		t.Errorf("active strategy should be topk_excerpt (from active-v1), got %s", resolved.DefaultStrategy)
	}
	tb, mi := m.GetModeDefaults("balanced")
	if tb != 800 || mi != 6 {
		t.Errorf("active mode should be (800, 6), got (%d, %d)", tb, mi)
	}
}

// --- Test 8: FetchWithManager error — manifest untouched ---

func TestCloudFetch_ManifestUntouchedOnError(t *testing.T) {
	dir, cleanup := writeActivePolicy(t, "active-v1", "topk_excerpt")
	defer cleanup()

	// Server returns non-200
	server := makeServer(t, `{"error":"not found"}`, http.StatusNotFound)
	defer server.Close()

	// Before: read manifest
	manifestBefore, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("failed to read manifest before: %v", err)
	}
	candVersionBefore := manifestBefore.CandidateVersion

	_, err = FetchWithManager(server.URL, "cloud-v2", dir)
	if err == nil {
		t.Fatal("FetchWithManager should fail on 404")
	}

	// After: manifest must be identical
	manifestAfter, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("failed to read manifest after: %v", err)
	}
	if candVersionBefore == nil && manifestAfter.CandidateVersion != nil {
		t.Error("candidate_version should remain nil after failed fetch")
	}
	if candVersionBefore != nil && manifestAfter.CandidateVersion == nil {
		t.Error("candidate_version should not be cleared after failed fetch")
	}
	if candVersionBefore != nil && manifestAfter.CandidateVersion != nil &&
		*candVersionBefore != *manifestAfter.CandidateVersion {
		t.Error("candidate_version should not change after failed fetch")
	}
}

// --- CloudCandidateFetcher unit tests ---

func TestCloudCandidateFetcher_BuildsCorrectURL(t *testing.T) {
	fetcher := NewCloudCandidateFetcher("https://cdn.example.com/policies")
	if fetcher.BaseURL != "https://cdn.example.com/policies/" {
		t.Errorf("expected trailing slash, got %s", fetcher.BaseURL)
	}
}

func TestCloudCandidateFetcher_TrailingSlashPreserved(t *testing.T) {
	fetcher := NewCloudCandidateFetcher("https://cdn.example.com/policies/")
	if fetcher.BaseURL != "https://cdn.example.com/policies/" {
		t.Errorf("expected preserved trailing slash, got %s", fetcher.BaseURL)
	}
}

func TestCloudCandidateFetcher_Fetch_NonOKStatus(t *testing.T) {
	server := makeServer(t, `{"error":"gone"}`, http.StatusGone)
	defer server.Close()

	fetcher := NewCloudCandidateFetcher(server.URL)
	_, err := fetcher.Fetch("candidate-v3", nil)
	if err == nil {
		t.Error("Fetch should fail on non-200 status")
	}
}
