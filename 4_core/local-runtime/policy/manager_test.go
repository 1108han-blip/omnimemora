// policy/manager_test.go - Compile Strategy Policy Manager tests
// Covers all 7 acceptance tests from SPEC-COMPILE-STRATEGY-POLICY-001.md
package policy

import (
	"os"
	"path/filepath"
	"testing"

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
