// policy/manager_test.go - Compile Strategy Policy Manager tests
// Covers all 7 acceptance tests from SPEC-COMPILE-STRATEGY-POLICY-001.md
package policy

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/omnimemora/local-runtime/app/context"
)

// tempPolicyDir creates a temp directory for testing and returns its path.
// The caller is responsible for removing it after the test.
func tempPolicyDir(t *testing.T) (string, func()) {
	tmp, err := os.MkdirTemp("", "policy_test")
	if err != nil {
		t.Fatalf("failed to create temp dir: %v", err)
	}
	return tmp, func() { os.RemoveAll(tmp) }
}

func writeFile(t *testing.T, dir, name, content string) {
	if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0644); err != nil {
		t.Fatalf("failed to write %s: %v", name, err)
	}
}

// --- Test 1: Local default policy loads and matches current hardcoded behavior ---

func TestLoadActive_DefaultPolicy(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	// Write a valid manifest and policy file
	writeFile(t, dir, "manifest.json", `{
  "active_version": "local-default-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "local-default-v1",
      "status": "active",
      "policy_file": "local-default-v1.json",
      "source": "bundled",
      "verified_at": "2026-04-24T00:00:00Z"
    }
  ]
}`)
	writeFile(t, dir, "local-default-v1.json", `{
  "version": "local-default-v1",
  "default_context_strategy": "topk_excerpt",
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Verify defaults match
	resolved := m.GetResolved()
	if resolved.DefaultStrategy != "topk_excerpt" {
		t.Errorf("expected default strategy topk_excerpt, got %s", resolved.DefaultStrategy)
	}
	if resolved.PolicyVersion != "local-default-v1" {
		t.Errorf("expected version local-default-v1, got %s", resolved.PolicyVersion)
	}
	if resolved.PolicySource != PolicySourceBundled {
		t.Errorf("expected source bundled, got %s", resolved.PolicySource)
	}

	// Verify mode defaults
	tb, mi := m.GetModeDefaults("precise")
	if tb != 300 || mi != 3 {
		t.Errorf("precise: expected (300, 3), got (%d, %d)", tb, mi)
	}
	tb, mi = m.GetModeDefaults("balanced")
	if tb != 800 || mi != 6 {
		t.Errorf("balanced: expected (800, 6), got (%d, %d)", tb, mi)
	}
	tb, mi = m.GetModeDefaults("aggressive")
	if tb != 1500 || mi != 10 {
		t.Errorf("aggressive: expected (1500, 10), got (%d, %d)", tb, mi)
	}
}

// --- Test 2: Missing/invalid policy falls back to built-in defaults ---

func TestLoadActive_MissingManifest_FallsBack(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	// dir exists but manifest is missing

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive should not error on missing manifest: %v", err)
	}

	resolved := m.GetResolved()
	if resolved.DefaultStrategy != context.DefaultStrategy {
		t.Errorf("expected builtin default %s, got %s", context.DefaultStrategy, resolved.DefaultStrategy)
	}
	if resolved.PolicySource != PolicySourceBuiltIn {
		t.Errorf("expected source builtin, got %s", resolved.PolicySource)
	}
}

func TestLoadActive_InvalidManifest_FallsBack(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	writeFile(t, dir, "manifest.json", `{ invalid json }`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive should not error on invalid manifest: %v", err)
	}

	resolved := m.GetResolved()
	if resolved.PolicySource != PolicySourceBuiltIn {
		t.Errorf("expected source builtin on invalid manifest, got %s", resolved.PolicySource)
	}
}

func TestLoadActive_MissingPolicyFile_FallsBack(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	writeFile(t, dir, "manifest.json", `{
  "active_version": "local-default-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "local-default-v1",
      "status": "active",
      "policy_file": "local-default-v1.json",
      "source": "bundled"
    }
  ]
}`)
	// local-default-v1.json is intentionally missing

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive should not error on missing policy file: %v", err)
	}

	resolved := m.GetResolved()
	if resolved.PolicySource != PolicySourceBuiltIn {
		t.Errorf("expected source builtin on missing policy file, got %s", resolved.PolicySource)
	}
}

func TestLoadActive_InvalidPolicyJSON_FallsBack(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	writeFile(t, dir, "manifest.json", `{
  "active_version": "local-default-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "local-default-v1",
      "status": "active",
      "policy_file": "local-default-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "local-default-v1.json", `{ not valid json }`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive should not error on invalid policy JSON: %v", err)
	}

	resolved := m.GetResolved()
	if resolved.PolicySource != PolicySourceBuiltIn {
		t.Errorf("expected source builtin on invalid policy JSON, got %s", resolved.PolicySource)
	}
}

// --- Test 3: Candidate policy does not affect active execution before promotion ---

func TestCandidate_DoesNotAffectActive(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	// Write active policy with balanced=800/6
	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": "candidate-v1",
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    },
    {
      "version": "candidate-v1",
      "status": "candidate",
      "policy_file": "candidate-v1.json",
      "source": "local"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)
	// Candidate would change everything if it were active
	writeFile(t, dir, "candidate-v1.json", `{
  "version": "candidate-v1",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"],
  "auto_resolution": {
    "enabled": true,
    "rules": {
      "question_patterns": "topk_excerpt",
      "long_query_threshold_chars": 30,
      "long_query_strategy": "topk_excerpt",
      "default_strategy": "diversity_select"
    }
  },
  "mode_defaults": {
    "precise":   { "token_budget": 100,  "max_items": 1  },
    "balanced":  { "token_budget": 200,  "max_items": 2  },
    "aggressive": { "token_budget": 400, "max_items": 4  }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Candidate is loaded but does NOT affect active behavior
	candidate, err := m.LoadCandidate()
	if err != nil {
		t.Fatalf("LoadCandidate failed: %v", err)
	}
	if candidate == nil {
		t.Fatal("candidate should be loaded")
	}
	if candidate.DefaultContextStrategy != "diversity_select" {
		t.Errorf("expected candidate default strategy diversity_select, got %s", candidate.DefaultContextStrategy)
	}

	// Active defaults remain unchanged
	resolved := m.GetResolved()
	if resolved.DefaultStrategy != "topk_excerpt" {
		t.Errorf("active strategy should be topk_excerpt (not candidate's diversity_select)")
	}
	tb, mi := m.GetModeDefaults("balanced")
	if tb != 800 || mi != 6 {
		t.Errorf("active mode should be (800, 6) (not candidate's 200/2)")
	}
}

// --- Test 4: Manual promotion switches active policy version ---

func TestPromoteCandidate_SwitchesActive(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "v1",
  "candidate_version": "v2",
  "versions": [
    {
      "version": "v1",
      "status": "active",
      "policy_file": "v1.json",
      "source": "bundled"
    },
    {
      "version": "v2",
      "status": "candidate",
      "policy_file": "v2.json",
      "source": "local"
    }
  ]
}`)
	writeFile(t, dir, "v1.json", `{
  "version": "v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)
	writeFile(t, dir, "v2.json", `{
  "version": "v2",
  "default_context_strategy": "recency_boost_select",
  "allowed_strategies": ["recency_boost_select"],
  "auto_resolution": {
    "enabled": true,
    "rules": {
      "question_patterns": "topk_excerpt",
      "long_query_threshold_chars": 50,
      "long_query_strategy": "diversity_select",
      "default_strategy": "topk_excerpt"
    }
  },
  "mode_defaults": {
    "precise":   { "token_budget": 400,  "max_items": 4  },
    "balanced":  { "token_budget": 900,  "max_items": 7  },
    "aggressive": { "token_budget": 1800, "max_items": 12 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}
	if _, err := m.LoadCandidate(); err != nil {
		t.Fatalf("LoadCandidate failed: %v", err)
	}

	// Verify pre-promotion state
	if m.GetDefaultStrategy() != "topk_excerpt" {
		t.Fatalf("pre-promotion default should be topk_excerpt")
	}

	// Promote
	if err := m.PromoteCandidate(); err != nil {
		t.Fatalf("PromoteCandidate failed: %v", err)
	}

	// Verify post-promotion state
	if m.GetDefaultStrategy() != "recency_boost_select" {
		t.Errorf("post-promotion default should be recency_boost_select, got %s", m.GetDefaultStrategy())
	}
	tb, mi := m.GetModeDefaults("balanced")
	if tb != 900 || mi != 7 {
		t.Errorf("post-promotion balanced should be (900, 7), got (%d, %d)", tb, mi)
	}

	// Verify candidate is cleared
	candidate, _ := m.LoadCandidate()
	if candidate != nil {
		t.Errorf("candidate should be cleared after promotion")
	}
}

func TestPromoteCandidate_NoCandidate_ReturnsError(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	writeFile(t, dir, "manifest.json", `{
  "active_version": "v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "v1",
      "status": "active",
      "policy_file": "v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "v1.json", `{
  "version": "v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	err := m.PromoteCandidate()
	if err == nil {
		t.Error("PromoteCandidate should return error when no candidate is loaded")
	}
}

// --- Test 5: auto resolves according to active policy rules ---

func TestResolveAuto_QuestionPattern(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	writeFile(t, dir, "manifest.json", `{
  "active_version": "v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "v1",
      "status": "active",
      "policy_file": "v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "v1.json", `{
  "version": "v1",
  "default_context_strategy": "recency_boost_select",
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Question query
	result := m.ResolveAuto("What is the capital of France?")
	if result != "topk_excerpt" {
		t.Errorf("expected topk_excerpt for question, got %s", result)
	}

	// Long query (over threshold)
	result = m.ResolveAuto("this is a very long query that definitely exceeds the fifty character threshold and should trigger diversity selection")
	if result != "diversity_select" {
		t.Errorf("expected diversity_select for long query, got %s", result)
	}

	// Short non-question query -> default
	result = m.ResolveAuto("hello world")
	if result != "recency_boost_select" {
		t.Errorf("expected recency_boost_select for short non-question, got %s", result)
	}
}

func TestResolveAuto_FallsBackWhenNoPolicy(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	// No manifest, uses built-in

	m := NewManager(dir)
	// LoadActive on missing manifest

	// Question query -> built-in fallback
	result := m.ResolveAuto("What is the capital?")
	if result != context.ResolveAutoStrategy("What is the capital?") {
		t.Errorf("ResolveAuto should fall back to context.ResolveAutoStrategy when no policy")
	}
}

// --- Test 6: Mode defaults from active policy ---

func TestGetModeDefaults_FromPolicy(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	writeFile(t, dir, "manifest.json", `{
  "active_version": "v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "v1",
      "status": "active",
      "policy_file": "v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "v1.json", `{
  "version": "v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 250,  "max_items": 2  },
    "balanced":  { "token_budget": 700,  "max_items": 5  },
    "aggressive": { "token_budget": 1200, "max_items": 8  }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	tb, mi := m.GetModeDefaults("precise")
	if tb != 250 || mi != 2 {
		t.Errorf("precise: expected (250, 2), got (%d, %d)", tb, mi)
	}
	tb, mi = m.GetModeDefaults("balanced")
	if tb != 700 || mi != 5 {
		t.Errorf("balanced: expected (700, 5), got (%d, %d)", tb, mi)
	}
	tb, mi = m.GetModeDefaults("aggressive")
	if tb != 1200 || mi != 8 {
		t.Errorf("aggressive: expected (1200, 8), got (%d, %d)", tb, mi)
	}
}

func TestGetModeDefaults_UnknownMode_BuiltInFallback(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	// No manifest

	m := NewManager(dir)

	// Unknown mode should fall back to balanced defaults
	tb, mi := m.GetModeDefaults("unknown-mode")
	if tb != 800 || mi != 6 {
		t.Errorf("unknown mode: expected (800, 6), got (%d, %d)", tb, mi)
	}
}

// --- Test 7: Cloud disabled/unreachable irrelevant (no network path) ---

func TestNoNetworkCalls(t *testing.T) {
	// Policy manager has no network calls — it only reads local files.
	// This test documents the boundary: Manager never makes HTTP calls.
	m := NewManager("/nonexistent/path")
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive should not error even on nonexistent path: %v", err)
	}
	resolved := m.GetResolved()
	if resolved.PolicySource != PolicySourceBuiltIn {
		t.Errorf("nonexistent path should fall back to builtin, got %s", resolved.PolicySource)
	}
	// Try to resolve auto — should never call network
	result := m.ResolveAuto("any query")
	if result == "" {
		t.Error("ResolveAuto should always return a strategy name")
	}
}

// --- Additional tests: unknown strategy falls back to topk_excerpt ---

func TestGetDefaultStrategy_UnknownInPolicy_FallsBack(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	writeFile(t, dir, "manifest.json", `{
  "active_version": "v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "v1",
      "status": "active",
      "policy_file": "v1.json",
      "source": "bundled"
    }
  ]
}`)
	// Policy specifies an unknown strategy
	writeFile(t, dir, "v1.json", `{
  "version": "v1",
  "default_context_strategy": "unknown_strategy_xyz",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Unknown strategy in policy should fall back to DefaultStrategy
	if m.GetDefaultStrategy() != context.DefaultStrategy {
		t.Errorf("unknown strategy in policy should fall back to %s, got %s", context.DefaultStrategy, m.GetDefaultStrategy())
	}
}

// --- InvalidateCache ---

func TestInvalidateCache_DoesNotLoseBuiltinBaseline(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	// No manifest — builtin baseline only

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	baselineVersion := m.GetResolved().PolicyVersion

	m.InvalidateCache()

	// After invalidation + re-LoadActive, should still have builtin baseline
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive after InvalidateCache failed: %v", err)
	}
	if m.GetResolved().PolicyVersion != baselineVersion {
		t.Errorf("after InvalidateCache+LoadActive, version should be %s, got %s", baselineVersion, m.GetResolved().PolicyVersion)
	}
}

// --- Bundle-path tests (CSP-001 promotion bundle) ---

// TestLoadActive_BundleLayout verifies the manager can load a policy from a
// service-current-style bundle path (binary_dir/config/compile_strategy_policies/).
func TestLoadActive_BundleLayout(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	// Simulate service-current/tools/config/compile_strategy_policies/ layout
	bundleDir := filepath.Join(dir, "config", "compile_strategy_policies")
	if err := os.MkdirAll(bundleDir, 0755); err != nil {
		t.Fatalf("failed to create bundle dir: %v", err)
	}
	writeFile(t, bundleDir, "manifest.json", `{
  "active_version": "local-default-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "local-default-v1",
      "status": "active",
      "policy_file": "local-default-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, bundleDir, "local-default-v1.json", `{
  "version": "local-default-v1",
  "default_context_strategy": "topk_excerpt",
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	// Explicit path (simulates promotion-bundle layout)
	m := NewManager(filepath.Join(dir, "config", "compile_strategy_policies"))
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	resolved := m.GetResolved()
	if resolved.PolicyVersion != "local-default-v1" {
		t.Errorf("expected version local-default-v1, got %s", resolved.PolicyVersion)
	}
	if resolved.PolicySource != PolicySourceBundled {
		t.Errorf("expected source bundled, got %s", resolved.PolicySource)
	}
	if resolved.DefaultStrategy != "topk_excerpt" {
		t.Errorf("expected default strategy topk_excerpt, got %s", resolved.DefaultStrategy)
	}
}

// TestLoadActive_MissingBundlePath_FallsBack verifies that when the policy
// directory does not exist (neither bundle nor CWD layout), the manager falls
// back to built-in defaults and does not return an error.
func TestLoadActive_MissingBundlePath_FallsBack(t *testing.T) {
	// NewManager("") with no valid policy directory should return a manager
	// that falls back to built-in without error.
	m := NewManager("")
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive should not error on missing bundle: %v", err)
	}

	resolved := m.GetResolved()
	if resolved.PolicyVersion != "builtin" {
		t.Errorf("expected builtin fallback, got %s", resolved.PolicyVersion)
	}
	if resolved.PolicySource != PolicySourceBuiltIn {
		t.Errorf("expected source builtin, got %s", resolved.PolicySource)
	}
}

// TestResolveAuto_BundlePolicy verifies auto resolution works when the policy
// is loaded from a bundle path.
func TestResolveAuto_BundlePolicy(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	bundleDir := filepath.Join(dir, "config", "compile_strategy_policies")
	if err := os.MkdirAll(bundleDir, 0755); err != nil {
		t.Fatalf("failed to create bundle dir: %v", err)
	}
	writeFile(t, bundleDir, "manifest.json", `{
  "active_version": "local-default-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "local-default-v1",
      "status": "active",
      "policy_file": "local-default-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, bundleDir, "local-default-v1.json", `{
  "version": "local-default-v1",
  "default_context_strategy": "topk_excerpt",
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(filepath.Join(dir, "config", "compile_strategy_policies"))
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Question query
	result := m.ResolveAuto("What is Docker?")
	if result != "topk_excerpt" {
		t.Errorf("expected topk_excerpt for question, got %s", result)
	}

	// Long query (>50 chars)
	result = m.ResolveAuto("this query is definitely longer than fifty characters and should trigger long query logic")
	if result != "diversity_select" {
		t.Errorf("expected diversity_select for long query, got %s", result)
	}

	// Short non-question
	result = m.ResolveAuto("hello world")
	if result != "recency_boost_select" {
		t.Errorf("expected recency_boost_select for short non-question, got %s", result)
	}
}

// --- CandidatePack type tests ---

func TestCandidatePack_Validate_Valid(t *testing.T) {
	policy := &CompileStrategyPolicy{
		Version:                "cloud-v1",
		DefaultContextStrategy: "diversity_select",
		AllowedStrategies:      []string{"diversity_select"},
	}
	pack := &CandidatePack{
		CandidateID:     "cloud-candidate-001",
		PolicyVersion:   "cloud-v1",
		Policy:          policy,
		SignatureStatus: SignatureStatusNotRequired,
		Source:          CandidateSourceCloud,
		FetchedAt:       time.Now(),
	}
	// Compute correct SHA256
	canonical, _ := json.Marshal(policy)
	h := sha256.Sum256(canonical)
	pack.SHA256 = hex.EncodeToString(h[:])

	if err := pack.Validate(); err != nil {
		t.Errorf("valid pack should pass: %v", err)
	}
}

func TestCandidatePack_Validate_MissingCandidateID(t *testing.T) {
	policy := &CompileStrategyPolicy{Version: "v1", DefaultContextStrategy: "topk_excerpt"}
	pack := &CandidatePack{
		CandidateID:   "", // empty
		PolicyVersion: "v1",
		Policy:        policy,
		SHA256:        "abc123",
	}
	if err := pack.Validate(); err == nil {
		t.Error("expected error for missing candidate_id")
	}
}

func TestCandidatePack_Validate_MissingPolicyVersion(t *testing.T) {
	policy := &CompileStrategyPolicy{Version: "v1", DefaultContextStrategy: "topk_excerpt"}
	pack := &CandidatePack{
		CandidateID:   "id-001",
		PolicyVersion: "", // empty
		Policy:        policy,
		SHA256:        "abc123",
	}
	if err := pack.Validate(); err == nil {
		t.Error("expected error for missing policy_version")
	}
}

func TestCandidatePack_Validate_NilPolicy(t *testing.T) {
	pack := &CandidatePack{
		CandidateID:   "id-001",
		PolicyVersion: "v1",
		Policy:        nil,
		SHA256:        "abc123",
	}
	if err := pack.Validate(); err == nil {
		t.Error("expected error for nil policy")
	}
}

func TestCandidatePack_Validate_VersionMismatch(t *testing.T) {
	policy := &CompileStrategyPolicy{Version: "v2", DefaultContextStrategy: "topk_excerpt"}
	pack := &CandidatePack{
		CandidateID:   "id-001",
		PolicyVersion: "v1", // differs from policy.Version
		Policy:        policy,
		SHA256:        "abc123",
	}
	if err := pack.Validate(); err == nil {
		t.Error("expected error for version mismatch")
	}
}

func TestCandidatePack_Validate_MissingSHA256(t *testing.T) {
	policy := &CompileStrategyPolicy{Version: "v1", DefaultContextStrategy: "topk_excerpt"}
	pack := &CandidatePack{
		CandidateID:   "id-001",
		PolicyVersion: "v1",
		Policy:        policy,
		SHA256:        "", // empty
	}
	if err := pack.Validate(); err == nil {
		t.Error("expected error for missing sha256")
	}
}

func makeTestPack(t *testing.T, version, defaultStrategy string, sha256Override string) *CandidatePack {
	t.Helper()
	policy := &CompileStrategyPolicy{
		Version:                version,
		DefaultContextStrategy: defaultStrategy,
		AllowedStrategies:      []string{"topk_excerpt", "recency_boost_select", "diversity_select"},
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
			"precise":    {TokenBudget: 300, MaxItems: 3},
			"balanced":   {TokenBudget: 800, MaxItems: 6},
			"aggressive": {TokenBudget: 1500, MaxItems: 10},
		},
	}
	canonical, err := json.Marshal(policy)
	if err != nil {
		t.Fatalf("failed to marshal policy: %v", err)
	}
	h := sha256.Sum256(canonical)
	pack := &CandidatePack{
		CandidateID:     version,
		PolicyVersion:   version,
		Policy:          policy,
		SHA256:          hex.EncodeToString(h[:]),
		SignatureStatus: SignatureStatusNotRequired,
		Source:          CandidateSourceCloud,
		FetchedAt:       time.Now(),
	}
	if sha256Override != "" {
		pack.SHA256 = sha256Override
	}
	return pack
}

// --- AcceptCandidate tests ---

func TestAcceptCandidate_ValidPackWritesCandidateFileAndUpdatesCandidateVersion(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	// Pre-write an active version so manifest exists
	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Accept a candidate pack
	pack := makeTestPack(t, "candidate-cloud-v2", "diversity_select", "")
	if err := m.AcceptCandidate(pack); err != nil {
		t.Fatalf("AcceptCandidate failed: %v", err)
	}

	// Candidate file should exist
	candidatePath := filepath.Join(dir, "candidate-cloud-v2.json")
	if _, err := os.Stat(candidatePath); os.IsNotExist(err) {
		t.Error("candidate file should have been written")
	}

	// Manifest should have candidate_version set but active_version unchanged
	manifest, err := m.readManifest()
	if err != nil {
		t.Fatalf("failed to read manifest: %v", err)
	}
	if manifest.ActiveVersion != "active-v1" {
		t.Errorf("active_version should remain active-v1, got %s", manifest.ActiveVersion)
	}
	if manifest.CandidateVersion == nil || *manifest.CandidateVersion != "candidate-cloud-v2" {
		t.Errorf("candidate_version should be candidate-cloud-v2, got %v", manifest.CandidateVersion)
	}
}

func TestAcceptCandidate_InvalidHashRejected(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Wrong SHA256
	pack := makeTestPack(t, "candidate-cloud-v2", "diversity_select", "deadbeef00000000000000000000000000000000000000000000000000000000")
	err := m.AcceptCandidate(pack)
	if err == nil {
		t.Error("AcceptCandidate should reject wrong SHA256")
	}

	// Manifest should be unchanged
	manifest, _ := m.readManifest()
	if manifest.CandidateVersion != nil {
		t.Error("candidate_version should still be nil after rejected pack")
	}
	// Candidate file should not exist
	candidatePath := filepath.Join(dir, "candidate-cloud-v2.json")
	if _, err := os.Stat(candidatePath); !os.IsNotExist(err) {
		t.Error("candidate file should not exist after rejected pack")
	}
}

func TestAcceptCandidate_InvalidPolicyRejected(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Pack with missing candidate_id
	pack := &CandidatePack{
		CandidateID:     "", // empty — fails Validate()
		PolicyVersion:   "bad-pack-v1",
		Policy:          &CompileStrategyPolicy{Version: "bad-pack-v1", DefaultContextStrategy: "topk_excerpt"},
		SHA256:          "deadbeef00000000000000000000000000000000000000000000000000000000",
		SignatureStatus: SignatureStatusNotRequired,
		Source:          CandidateSourceCloud,
		FetchedAt:       time.Now(),
	}
	err := m.AcceptCandidate(pack)
	if err == nil {
		t.Error("AcceptCandidate should reject pack with empty candidate_id")
	}

	// Manifest unchanged
	manifest, _ := m.readManifest()
	if manifest.CandidateVersion != nil {
		t.Error("candidate_version should still be nil after rejected invalid pack")
	}
}

func TestAcceptCandidate_CannotOverwriteActiveVersion(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Try to accept a pack with the same version as the active policy
	pack := makeTestPack(t, "active-v1", "topk_excerpt", "")
	err := m.AcceptCandidate(pack)
	if err == nil {
		t.Error("AcceptCandidate should reject overwriting active version")
	}
}

func TestAcceptCandidate_CandidateDoesNotAffectLoadActive(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	// Write active and candidate in manifest (simulating a prior AcceptCandidate)
	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": "candidate-v1",
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    },
    {
      "version": "candidate-v1",
      "status": "candidate",
      "policy_file": "candidate-v1.json",
      "source": "cloud"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)
	writeFile(t, dir, "candidate-v1.json", `{
  "version": "candidate-v1",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"],
  "auto_resolution": {
    "enabled": true,
    "rules": {
      "question_patterns": "topk_excerpt",
      "long_query_threshold_chars": 30,
      "long_query_strategy": "topk_excerpt",
      "default_strategy": "diversity_select"
    }
  },
  "mode_defaults": {
    "precise":   { "token_budget": 100,  "max_items": 1  },
    "balanced":  { "token_budget": 200,  "max_items": 2  },
    "aggressive": { "token_budget": 400,  "max_items": 4  }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Active behavior must come from active-v1, not candidate-v1
	resolved := m.GetResolved()
	if resolved.DefaultStrategy != "topk_excerpt" {
		t.Errorf("active strategy should be topk_excerpt (from active-v1), got %s", resolved.DefaultStrategy)
	}
	tb, mi := m.GetModeDefaults("balanced")
	if tb != 800 || mi != 6 {
		t.Errorf("active mode should be (800, 6), got (%d, %d)", tb, mi)
	}

	// Candidate is also loadable but does not affect active
	candidate, _ := m.LoadCandidate()
	if candidate == nil {
		t.Fatal("LoadCandidate should return the candidate")
	}
	if candidate.DefaultContextStrategy != "diversity_select" {
		t.Errorf("candidate strategy should be diversity_select, got %s", candidate.DefaultContextStrategy)
	}
	// Active still unchanged
	if resolved.DefaultStrategy != "topk_excerpt" {
		t.Errorf("active strategy still topk_excerpt, got %s", resolved.DefaultStrategy)
	}
}

func TestPromoteCandidate_ActivatesCandidateOnlyAfterExplicitCall(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": "candidate-v1",
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    },
    {
      "version": "candidate-v1",
      "status": "candidate",
      "policy_file": "candidate-v1.json",
      "source": "cloud"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)
	writeFile(t, dir, "candidate-v1.json", `{
  "version": "candidate-v1",
  "default_context_strategy": "recency_boost_select",
  "allowed_strategies": ["recency_boost_select"],
  "auto_resolution": {
    "enabled": true,
    "rules": {
      "question_patterns": "topk_excerpt",
      "long_query_threshold_chars": 50,
      "long_query_strategy": "diversity_select",
      "default_strategy": "topk_excerpt"
    }
  },
  "mode_defaults": {
    "precise":   { "token_budget": 400,  "max_items": 4  },
    "balanced":  { "token_budget": 900,  "max_items": 7  },
    "aggressive": { "token_budget": 1800, "max_items": 12 }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Pre-promotion: active is v1
	if m.GetDefaultStrategy() != "topk_excerpt" {
		t.Fatalf("pre-promotion default should be topk_excerpt")
	}

	// Load candidate
	if _, err := m.LoadCandidate(); err != nil {
		t.Fatalf("LoadCandidate failed: %v", err)
	}

	// Promote
	if err := m.PromoteCandidate(); err != nil {
		t.Fatalf("PromoteCandidate failed: %v", err)
	}

	// Post-promotion: active is candidate-v1
	if m.GetDefaultStrategy() != "recency_boost_select" {
		t.Errorf("post-promotion default should be recency_boost_select, got %s", m.GetDefaultStrategy())
	}
	tb, mi := m.GetModeDefaults("balanced")
	if tb != 900 || mi != 7 {
		t.Errorf("post-promotion balanced should be (900, 7), got (%d, %d)", tb, mi)
	}

	// Verify manifest state
	manifest, err := m.readManifest()
	if err != nil {
		t.Fatalf("readManifest failed: %v", err)
	}
	if manifest.ActiveVersion != "candidate-v1" {
		t.Errorf("active_version should be candidate-v1, got %s", manifest.ActiveVersion)
	}
	if manifest.CandidateVersion != nil {
		t.Errorf("candidate_version should be nil after promotion, got %v", manifest.CandidateVersion)
	}
}

func TestGetCandidateInfo_ReturnsMetadata(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": "candidate-v1",
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    },
    {
      "version": "candidate-v1",
      "status": "candidate",
      "policy_file": "candidate-v1.json",
      "source": "cloud"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)
	writeFile(t, dir, "candidate-v1.json", `{
  "version": "candidate-v1",
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	m := NewManager(dir)

	info, err := m.GetCandidateInfo()
	if err != nil {
		t.Fatalf("GetCandidateInfo failed: %v", err)
	}
	if info == nil {
		t.Fatal("GetCandidateInfo should return info when candidate is present")
	}
	if info.PolicyVersion != "candidate-v1" {
		t.Errorf("expected candidate version candidate-v1, got %s", info.PolicyVersion)
	}
	if info.Source != CandidateSourceCloud {
		t.Errorf("expected source cloud, got %s", info.Source)
	}
	if info.SignatureStatus != SignatureStatusNotRequired {
		t.Errorf("expected signature_status not_required, got %s", info.SignatureStatus)
	}
}

func TestGetCandidateInfo_NoCandidate_ReturnsNil(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	// No manifest

	m := NewManager(dir)

	info, err := m.GetCandidateInfo()
	if err != nil {
		t.Fatalf("GetCandidateInfo should not error on no candidate: %v", err)
	}
	if info != nil {
		t.Error("GetCandidateInfo should return nil when no candidate")
	}
}

func TestAcceptCandidate_NewManifestCreated(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()
	// No manifest at all

	m := NewManager(dir)
	pack := makeTestPack(t, "cloud-v1", "diversity_select", "")
	if err := m.AcceptCandidate(pack); err != nil {
		t.Fatalf("AcceptCandidate failed: %v", err)
	}

	// Manifest should have been created
	manifest, err := m.readManifest()
	if err != nil {
		t.Fatalf("manifest should be created: %v", err)
	}
	if manifest.ActiveVersion != "builtin" {
		t.Errorf("active_version should default to builtin, got %s", manifest.ActiveVersion)
	}
	if manifest.CandidateVersion == nil || *manifest.CandidateVersion != "cloud-v1" {
		t.Errorf("candidate_version should be cloud-v1, got %v", manifest.CandidateVersion)
	}
}

// --- ImportCandidate (file-based import) tests ---

func TestImportCandidate_ValidPackFile(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	// Write active policy first
	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	// Write a candidate pack JSON file. policyJSON is the valid policy object
	// (without extra fields) — the hash is computed from the canonical JSON
	// after parsing to ensure it matches what AcceptCandidate will re-marshal.
	policyJSON := `{
  "version": "imported-v2",
  "default_context_strategy": "recency_boost_select",
  "allowed_strategies": ["recency_boost_select", "topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`
	packPath := filepath.Join(dir, "candidate-pack.json")
	if err := os.WriteFile(packPath, []byte(policyJSON), 0644); err != nil {
		t.Fatalf("failed to write pack file: %v", err)
	}

	// Parse the policy JSON to get a clean *CompileStrategyPolicy, then
	// re-marshal it to get the canonical bytes for SHA-256. This mirrors the
	// exact computation AcceptCandidate does.
	var cleanPolicy CompileStrategyPolicy
	if err := json.Unmarshal([]byte(policyJSON), &cleanPolicy); err != nil {
		t.Fatalf("failed to parse policy JSON: %v", err)
	}
	canonical, err := json.Marshal(&cleanPolicy)
	if err != nil {
		t.Fatalf("failed to marshal policy for hash: %v", err)
	}
	h := sha256.Sum256(canonical)
	shaHex := hex.EncodeToString(h[:])

	// Write the full candidate pack JSON with hash and metadata
	candJSON := fmt.Sprintf(`{
  "candidate_id": "test-candidate-001",
  "policy_version": "imported-v2",
  "policy": %s,
  "sha256": "%s",
  "signature_status": "not_required",
  "source": "local",
  "fetched_at": "2026-04-24T10:00:00Z"
}`, policyJSON, shaHex)
	if err := os.WriteFile(packPath, []byte(candJSON), 0644); err != nil {
		t.Fatalf("failed to write candidate pack: %v", err)
	}

	// Import via ImportCandidate
	pack, err := ImportCandidate(packPath, dir)
	if err != nil {
		t.Fatalf("ImportCandidate failed: %v", err)
	}
	if pack.CandidateID != "test-candidate-001" {
		t.Errorf("expected candidate_id test-candidate-001, got %s", pack.CandidateID)
	}
	if pack.PolicyVersion != "imported-v2" {
		t.Errorf("expected policy_version imported-v2, got %s", pack.PolicyVersion)
	}

	// Verify manifest updated
	manifest, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("failed to read manifest: %v", err)
	}
	if manifest.ActiveVersion != "active-v1" {
		t.Errorf("active_version should remain active-v1, got %s", manifest.ActiveVersion)
	}
	if manifest.CandidateVersion == nil || *manifest.CandidateVersion != "imported-v2" {
		t.Errorf("candidate_version should be imported-v2, got %v", manifest.CandidateVersion)
	}

	// Candidate file written to disk
	candFile := filepath.Join(dir, "imported-v2.json")
	if _, err := os.Stat(candFile); os.IsNotExist(err) {
		t.Error("candidate file imported-v2.json should exist on disk")
	}
}

func TestImportCandidate_InvalidHash_FailsManifestUnchanged(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	policyJSON := `{
  "version": "bad-hash-v2",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"]
}`
	badHash := "deadbeef00000000000000000000000000000000000000000000000000000000"
	candJSON := fmt.Sprintf(`{
  "candidate_id": "test-bad-hash",
  "policy_version": "bad-hash-v2",
  "policy": %s,
  "sha256": "%s",
  "signature_status": "not_required",
  "source": "local",
  "fetched_at": "2026-04-24T10:00:00Z"
}`, policyJSON, badHash)
	packPath := filepath.Join(dir, "bad-pack.json")
	if err := os.WriteFile(packPath, []byte(candJSON), 0644); err != nil {
		t.Fatalf("failed to write pack file: %v", err)
	}

	_, err := ImportCandidate(packPath, dir)
	if err == nil {
		t.Error("ImportCandidate should fail on hash mismatch")
	}

	// Manifest unchanged
	manifest, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("failed to read manifest: %v", err)
	}
	if manifest.CandidateVersion != nil {
		t.Error("candidate_version should still be nil")
	}

	// No candidate file written
	candFile := filepath.Join(dir, "bad-hash-v2.json")
	if _, err := os.Stat(candFile); !os.IsNotExist(err) {
		t.Error("candidate file should not exist after failed import")
	}
}

func TestImportCandidate_InvalidPolicy_FailsManifestUnchanged(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	// Missing candidate_id and empty sha256 — fails Validate()
	candJSON := `{
  "candidate_id": "",
  "policy_version": "bad-v2",
  "policy": {"version": "bad-v2", "default_context_strategy": "topk_excerpt"},
  "sha256": "",
  "signature_status": "not_required",
  "source": "local",
  "fetched_at": "2026-04-24T10:00:00Z"
}`
	packPath := filepath.Join(dir, "bad-pack.json")
	if err := os.WriteFile(packPath, []byte(candJSON), 0644); err != nil {
		t.Fatalf("failed to write pack file: %v", err)
	}

	_, err := ImportCandidate(packPath, dir)
	if err == nil {
		t.Error("ImportCandidate should fail on invalid policy")
	}

	// Manifest unchanged
	manifest, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("failed to read manifest: %v", err)
	}
	if manifest.CandidateVersion != nil {
		t.Error("candidate_version should still be nil")
	}
}

func TestImportCandidate_ActiveOverwriteAttempt_Fails(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)

	policyJSON := `{
  "version": "active-v1",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"]
}`
	h := sha256.Sum256([]byte(policyJSON))
	shaHex := hex.EncodeToString(h[:])

	candJSON := fmt.Sprintf(`{
  "candidate_id": "overwrite-attempt",
  "policy_version": "active-v1",
  "policy": %s,
  "sha256": "%s",
  "signature_status": "not_required",
  "source": "local",
  "fetched_at": "2026-04-24T10:00:00Z"
}`, policyJSON, shaHex)
	packPath := filepath.Join(dir, "overwrite-pack.json")
	if err := os.WriteFile(packPath, []byte(candJSON), 0644); err != nil {
		t.Fatalf("failed to write pack file: %v", err)
	}

	_, err := ImportCandidate(packPath, dir)
	if err == nil {
		t.Error("ImportCandidate should fail when trying to overwrite active version")
	}

	// Manifest unchanged
	manifest, err := readManifestFromPath(filepath.Join(dir, "manifest.json"))
	if err != nil {
		t.Fatalf("failed to read manifest: %v", err)
	}
	if manifest.CandidateVersion != nil {
		t.Error("candidate_version should still be nil")
	}
}

func TestImportCandidate_LoadActiveUnaffected(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": "imported-v2",
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    },
    {
      "version": "imported-v2",
      "status": "candidate",
      "policy_file": "imported-v2.json",
      "source": "local"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)
	writeFile(t, dir, "imported-v2.json", `{
  "version": "imported-v2",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"],
  "auto_resolution": {
    "enabled": true,
    "rules": {
      "question_patterns": "topk_excerpt",
      "long_query_threshold_chars": 30,
      "long_query_strategy": "topk_excerpt",
      "default_strategy": "diversity_select"
    }
  },
  "mode_defaults": {
    "precise":   { "token_budget": 100,  "max_items": 1  },
    "balanced":  { "token_budget": 200,  "max_items": 2  },
    "aggressive": { "token_budget": 400,  "max_items": 4  }
  }
}`)

	m := NewManager(dir)
	if err := m.LoadActive(); err != nil {
		t.Fatalf("LoadActive failed: %v", err)
	}

	// Active behavior from active-v1
	resolved := m.GetResolved()
	if resolved.DefaultStrategy != "topk_excerpt" {
		t.Errorf("LoadActive should return active-v1 strategy, got %s", resolved.DefaultStrategy)
	}
	tb, mi := m.GetModeDefaults("balanced")
	if tb != 800 || mi != 6 {
		t.Errorf("LoadActive should return active-v1 mode, got (%d,%d)", tb, mi)
	}

	// Candidate is loadable but irrelevant to LoadActive
	cand, _ := m.LoadCandidate()
	if cand == nil {
		t.Fatal("candidate should be loadable")
	}
	if cand.DefaultContextStrategy != "diversity_select" {
		t.Errorf("candidate strategy should be diversity_select, got %s", cand.DefaultContextStrategy)
	}

	// Active unchanged
	resolved2 := m.GetResolved()
	if resolved2.DefaultStrategy != "topk_excerpt" {
		t.Errorf("active strategy still topk_excerpt, got %s", resolved2.DefaultStrategy)
	}
}

// readManifestFromPath reads a manifest file from a specific path.
func readManifestFromPath(path string) (*Manifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, err
	}
	return &m, nil
}

// --- GetPolicyStatus tests ---

func TestGetPolicyStatus_ActiveOnly(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	status := GetPolicyStatus(dir)
	if status.ActiveVersion == "" {
		t.Error("active_version should not be empty")
	}
	if status.CandidateVersion != nil {
		t.Error("CandidateVersion should be nil when no candidate is staged")
	}
}

func TestGetPolicyStatus_WithCandidate(t *testing.T) {
	dir, cleanup := tempPolicyDir(t)
	defer cleanup()

	writeFile(t, dir, "manifest.json", `{
  "active_version": "active-v1",
  "candidate_version": "cand-v2",
  "versions": [
    {
      "version": "active-v1",
      "status": "active",
      "policy_file": "active-v1.json",
      "source": "bundled"
    },
    {
      "version": "cand-v2",
      "status": "candidate",
      "policy_file": "cand-v2.json",
      "source": "local"
    }
  ]
}`)
	writeFile(t, dir, "active-v1.json", `{
  "version": "active-v1",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": ["topk_excerpt"],
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
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}`)
	writeFile(t, dir, "cand-v2.json", `{
  "version": "cand-v2",
  "default_context_strategy": "diversity_select",
  "allowed_strategies": ["diversity_select"]
}`)

	status := GetPolicyStatus(dir)
	if status.ActiveVersion != "active-v1" {
		t.Errorf("expected active-version active-v1, got %s", status.ActiveVersion)
	}
	if status.CandidateVersion == nil || *status.CandidateVersion != "cand-v2" {
		t.Errorf("expected candidate-version cand-v2, got %v", status.CandidateVersion)
	}
	if status.CandidateSource != "local" {
		t.Errorf("expected candidate source local, got %s", status.CandidateSource)
	}
}
