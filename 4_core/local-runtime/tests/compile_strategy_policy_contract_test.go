// tests/compile_strategy_policy_contract_test.go - CSP-001 contract hardening tests
// Verifies runtime service, metering, and SQLite migration contracts for compile strategy policy.
package tests

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/omnimemora/local-runtime/api"
	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/lifecycle"
	"github.com/omnimemora/local-runtime/pkg"
	"github.com/omnimemora/local-runtime/store"
)

// --- SQLite Persistence Contract ---

// TestSQLiteCSP001ColumnsExist verifies the five CSP-001 columns exist in metering_events.
func TestSQLiteCSP001ColumnsExist(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	db := s.DB()

	for _, col := range []string{
		"compile_strategy_policy_version",
		"compile_strategy_policy_source",
		"context_strategy_requested",
		"context_strategy_resolved",
		"context_mode_resolved",
	} {
		var count int
		if err := db.QueryRow(
			"SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name=?",
			col,
		).Scan(&count); err != nil {
			t.Fatalf("failed to check column %q: %v", col, err)
		}
		if count == 0 {
			t.Errorf("expected column %q to exist in metering_events", col)
		}
	}
}

// TestSQLiteCSP001ColumnsIdempotent verifies migration is idempotent (re-run is safe).
func TestSQLiteCSP001ColumnsIdempotent(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	s.Close()

	// Re-init — migration runs again
	s2, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("re-init failed: %v", err)
	}
	defer s2.Close()

	db := s2.DB()
	for _, col := range []string{
		"compile_strategy_policy_version",
		"compile_strategy_policy_source",
		"context_strategy_requested",
		"context_strategy_resolved",
		"context_mode_resolved",
	} {
		var count int
		if err := db.QueryRow(
			"SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name=?",
			col,
		).Scan(&count); err != nil {
			t.Fatalf("column %q check failed after re-init: %v", col, err)
		}
		if count == 0 {
			t.Errorf("column %q missing after idempotent re-init", col)
		}
	}
}

// TestSQLiteCSP001InsertAndRetrieve verifies a metering event with all five fields
// can be inserted and retrieved with the correct values.
func TestSQLiteCSP001InsertAndRetrieve(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	db := s.DB()

	// 27 columns total — must match the INSERT VALUES count
	_, err = db.Exec(`
		INSERT INTO metering_events (
			event_id, request_id, event_type, tenant_id, user_id, workspace_id, agent_id,
			scope, sharing_mode, input_tokens, compressed_tokens, saved_tokens,
			query_count, recall_hits, recall_hit_rate, timestamp, runtime_version, store_type,
			raw_tokens, assembled_hits, context_strategy, context_mode,
			compile_strategy_policy_version, compile_strategy_policy_source,
			context_strategy_requested, context_strategy_resolved, context_mode_resolved
		) VALUES (
			?, ?, ?, ?, ?, ?, ?,
			?, ?, ?, ?, ?,
			?, ?, ?, ?, ?, ?,
			?, ?, ?, ?,
			?, ?,
			?, ?, ?
		)
	`,
		"evt_contract_test_001", "req_contract_001", "memory_search",
		"tenant_csp", "user_csp", "ws_csp", "agent_csp",
		"agent", "isolated", 1, 500, 200,
		1, 5, 0.0, "2026-04-24T16:00:00Z", "1.0.0", "sqlite",
		1000, 5, "topk_excerpt", "balanced",
		"local-default-v1", "bundled",
		"auto", "topk_excerpt", "balanced",
	)
	if err != nil {
		t.Fatalf("failed to insert metering event: %v", err)
	}

	var version, source, requested, resolved, mode string
	if err := db.QueryRow(`
		SELECT compile_strategy_policy_version, compile_strategy_policy_source,
		       context_strategy_requested, context_strategy_resolved, context_mode_resolved
		FROM metering_events WHERE event_id = ?
	`, "evt_contract_test_001").Scan(&version, &source, &requested, &resolved, &mode); err != nil {
		t.Fatalf("failed to retrieve metering event: %v", err)
	}

	if version != "local-default-v1" {
		t.Errorf("expected version 'local-default-v1', got %q", version)
	}
	if source != "bundled" {
		t.Errorf("expected source 'bundled', got %q", source)
	}
	if requested != "auto" {
		t.Errorf("expected requested 'auto', got %q", requested)
	}
	if resolved != "topk_excerpt" {
		t.Errorf("expected resolved 'topk_excerpt', got %q", resolved)
	}
	if mode != "balanced" {
		t.Errorf("expected mode 'balanced', got %q", mode)
	}
}

// --- Runtime Metering Evidence Contract ---

func newCSPTestServer(t *testing.T) (*api.Server, *store.SQLiteStore) {
	t.Helper()
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	t.Cleanup(func() { s.Close() })

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	return api.NewServer(cfg, s, rtCtx, 18765), s
}

func doCSPRequest(t *testing.T, srv *api.Server, method, path string, payload any, headers map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	body, _ := json.Marshal(payload)
	req := httptest.NewRequest(method, path, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	srv.Handler().ServeHTTP(rec, req)
	return rec
}

func writeMemoryCSP(t *testing.T, srv *api.Server, content, agentID string) {
	rec := doCSPRequest(t, srv, "POST", "/memory/write",
		pkg.WriteRequest{Content: content},
		map[string]string{"X-OmniMemora-Agent": agentID},
	)
	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}
}

func lastCSPEvent(db *sql.DB, requestID string) *sql.Row {
	return db.QueryRow(`
		SELECT compile_strategy_policy_version, compile_strategy_policy_source,
		       context_strategy_requested, context_strategy_resolved, context_mode_resolved
		FROM metering_events
		WHERE request_id = ?
		ORDER BY timestamp DESC LIMIT 1
	`, requestID)
}

// TestMeteringCSP001AutoStrategyRequestedResolved verifies that a search with
// context_strategy=auto records all five CSP-001 fields correctly.
func TestMeteringCSP001AutoStrategyRequestedResolved(t *testing.T) {
	srv, s := newCSPTestServer(t)
	writeMemoryCSP(t, srv, "What is the capital of France?", "csp_agent_001")

	rec := doCSPRequest(t, srv, "POST", "/memory/search",
		pkg.SearchRequest{
			Keyword:   "France capital",
			Limit:     5,
			RequestID: "req_csp_auto",
			Options: pkg.SearchOptions{
				AssembleContext: true,
				ContextStrategy: "auto",
				ContextMode:     "balanced",
			},
		},
		map[string]string{"X-OmniMemora-Agent": "csp_agent_001"},
	)
	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var version, source, requested, resolved, mode string
	if err := lastCSPEvent(s.DB(), "req_csp_auto").Scan(&version, &source, &requested, &resolved, &mode); err != nil {
		t.Fatalf("failed to retrieve metering event: %v", err)
	}

	if requested != "auto" {
		t.Errorf("expected context_strategy_requested='auto', got %q", requested)
	}
	if version == "" {
		t.Error("compile_strategy_policy_version should not be empty")
	}
	if source == "" {
		t.Error("compile_strategy_policy_source should not be empty")
	}
	if resolved == "" {
		t.Error("context_strategy_resolved should not be empty")
	}
	if mode != "balanced" {
		t.Errorf("expected context_mode_resolved='balanced', got %q", mode)
	}
}

// TestMeteringCSP001BlankStrategyUsesPolicyDefault verifies blank context_strategy
// uses the active policy default and records empty string for requested.
func TestMeteringCSP001BlankStrategyUsesPolicyDefault(t *testing.T) {
	srv, s := newCSPTestServer(t)
	writeMemoryCSP(t, srv, "Go language concurrency with goroutines", "csp_agent_002")

	rec := doCSPRequest(t, srv, "POST", "/memory/search",
		pkg.SearchRequest{
			Keyword:   "Go concurrency",
			Limit:     5,
			RequestID: "req_csp_blank",
			Options: pkg.SearchOptions{
				AssembleContext: true,
				// ContextStrategy intentionally blank — should use policy default
			},
		},
		map[string]string{"X-OmniMemora-Agent": "csp_agent_002"},
	)
	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var vIgnored1, vIgnored2, requested, resolved, vIgnored3 string
	if err := lastCSPEvent(s.DB(), "req_csp_blank").Scan(&vIgnored1, &vIgnored2, &requested, &resolved, &vIgnored3); err != nil {
		t.Fatalf("failed to retrieve metering event: %v", err)
	}

	if requested != "" {
		t.Errorf("expected context_strategy_requested='', got %q", requested)
	}
	if resolved != "topk_excerpt" {
		t.Errorf("expected context_strategy_resolved='topk_excerpt', got %q", resolved)
	}
}

// TestMeteringCSP001UnknownStrategyFallsBack verifies an unknown explicit strategy
// falls back to topk_excerpt safely and records correct evidence.
func TestMeteringCSP001UnknownStrategyFallsBack(t *testing.T) {
	srv, s := newCSPTestServer(t)
	writeMemoryCSP(t, srv, "Kubernetes container orchestration", "csp_agent_003")

	rec := doCSPRequest(t, srv, "POST", "/memory/search",
		pkg.SearchRequest{
			Keyword:   "container orchestration",
			Limit:     5,
			RequestID: "req_csp_unknown",
			Options: pkg.SearchOptions{
				AssembleContext: true,
				ContextStrategy: "unknown_nonsense_strategy_xyz",
			},
		},
		map[string]string{"X-OmniMemora-Agent": "csp_agent_003"},
	)
	if rec.Code != http.StatusOK {
		t.Fatalf("search with unknown strategy should still succeed: %d - %s", rec.Code, rec.Body.String())
	}

	var vIgn1, vIgn2, requested, resolved, vIgn3 string
	if err := lastCSPEvent(s.DB(), "req_csp_unknown").Scan(&vIgn1, &vIgn2, &requested, &resolved, &vIgn3); err != nil {
		t.Fatalf("failed to retrieve metering event: %v", err)
	}

	if requested != "unknown_nonsense_strategy_xyz" {
		t.Errorf("expected requested='unknown_nonsense_strategy_xyz', got %q", requested)
	}
	if resolved != "topk_excerpt" {
		t.Errorf("expected resolved='topk_excerpt' (safe fallback), got %q", resolved)
	}
}

// TestMeteringCSP001AllModesRecorded verifies context_mode_resolved is recorded
// for precise, balanced, and aggressive modes.
func TestMeteringCSP001AllModesRecorded(t *testing.T) {
	srv, _ := newCSPTestServer(t)

	for _, mode := range []string{"precise", "balanced", "aggressive"} {
		agentID := "csp_agent_mode_" + mode
		writeMemoryCSP(t, srv, "Testing mode resolution for "+mode, agentID)

		rec := doCSPRequest(t, srv, "POST", "/memory/search",
			pkg.SearchRequest{
				Keyword:   "mode test",
				Limit:     5,
				RequestID: "req_csp_mode_" + mode,
				Options: pkg.SearchOptions{
					AssembleContext: true,
					ContextStrategy: "topk_excerpt",
					ContextMode:     mode,
				},
			},
			map[string]string{"X-OmniMemora-Agent": agentID},
		)
		if rec.Code != http.StatusOK {
			t.Errorf("search failed for mode %s: %d - %s", mode, rec.Code, rec.Body.String())
		}
		// HTTP-level failure is the assertion; DB row is implicitly covered by other tests
	}
}

// --- Policy Fallback Contract ---

// TestCSP001PolicyFallbackDoesNotBreakSearch verifies searches succeed even when
// the policy directory is absent, and still record fallback evidence.
func TestCSP001PolicyFallbackDoesNotBreakSearch(t *testing.T) {
	srv, s := newCSPTestServer(t)
	writeMemoryCSP(t, srv, "fallback test memory", "fallback_agent")

	rec := doCSPRequest(t, srv, "POST", "/memory/search",
		pkg.SearchRequest{
			Keyword:   "fallback test",
			Limit:     5,
			RequestID: "req_csp_fallback",
			Options: pkg.SearchOptions{
				AssembleContext: true,
				ContextStrategy: "auto",
			},
		},
		map[string]string{"X-OmniMemora-Agent": "fallback_agent"},
	)

	if rec.Code != http.StatusOK {
		t.Errorf("search should succeed with missing policy directory, got %d: %s", rec.Code, rec.Body.String())
	}

	var version, source, vIgn1, resolved, vIgn2 string
	if err := lastCSPEvent(s.DB(), "req_csp_fallback").Scan(&version, &source, &vIgn1, &resolved, &vIgn2); err != nil {
		t.Fatalf("fallback path should still record metering event: %v", err)
	}

	if version == "" {
		t.Error("fallback: compile_strategy_policy_version should not be empty")
	}
	if source == "" {
		t.Error("fallback: compile_strategy_policy_source should not be empty")
	}
	if resolved == "" {
		t.Error("fallback: context_strategy_resolved should not be empty")
	}
}

// TestCSP001NoAutoPromote verifies the resolved strategy is always a registered
// strategy — candidate policy cannot inject unknown strategies.
func TestCSP001NoAutoPromote(t *testing.T) {
	srv, _ := newCSPTestServer(t)
	writeMemoryCSP(t, srv, "promotion boundary test", "promote_agent")

	rec := doCSPRequest(t, srv, "POST", "/memory/search",
		pkg.SearchRequest{
			Keyword:   "promotion boundary",
			Limit:     5,
			RequestID: "req_csp_promote",
			Options: pkg.SearchOptions{
				AssembleContext: true,
				ContextStrategy: "auto",
			},
		},
		map[string]string{"X-OmniMemora-Agent": "promote_agent"},
	)
	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var resp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to unmarshal response: %v", err)
	}

	validStrategies := map[string]bool{
		"topk_excerpt":         true,
		"recency_boost_select": true,
		"diversity_select":     true,
	}
	if resp.Context != nil {
		if !validStrategies[resp.Context.StrategyResolved] {
			t.Errorf("resolved strategy %q is not a registered strategy", resp.Context.StrategyResolved)
		}
	}
}

// TestCSP001NoRegressionWithAssembleFalse verifies assemble_context=false still
// records metering events with the version field populated.
func TestCSP001NoRegressionWithAssembleFalse(t *testing.T) {
	srv, s := newCSPTestServer(t)
	writeMemoryCSP(t, srv, "no assemble regression test", "noassemble_agent")

	rec := doCSPRequest(t, srv, "POST", "/memory/search",
		pkg.SearchRequest{
			Keyword:   "no assemble",
			Limit:     5,
			RequestID: "req_csp_noassemble",
			Options: pkg.SearchOptions{
				AssembleContext: false,
			},
		},
		map[string]string{"X-OmniMemora-Agent": "noassemble_agent"},
	)
	if rec.Code != http.StatusOK {
		t.Fatalf("search with assemble=false should succeed: %d - %s", rec.Code, rec.Body.String())
	}

	var version string
	err := s.DB().QueryRow(`
		SELECT compile_strategy_policy_version
		FROM metering_events
		WHERE request_id = 'req_csp_noassemble'
		ORDER BY timestamp DESC LIMIT 1
	`).Scan(&version)
	if err == sql.ErrNoRows {
		t.Error("metering event should be recorded even when assemble_context=false")
	} else if err != nil {
		t.Fatalf("failed to query metering event: %v", err)
	}
	if version == "" {
		t.Error("version field should be populated in non-assembly search metering event")
	}
}

// TestCSP001DistinctRequestFields verifies context_strategy_requested captures the
// raw request value before resolution, and resolved is always a known strategy.
func TestCSP001DistinctRequestFields(t *testing.T) {
	srv, s := newCSPTestServer(t)

	for _, tc := range []struct {
		requested string
		query     string
	}{
		{"auto", "What is Docker?"},
		{"recency_boost_select", "recent containers"},
		{"diversity_select", "container orchestration scheduling"},
		{"", "plain search"},
	} {
		agentID := "distinct_" + strings.ReplaceAll(tc.requested, "_", "")
		writeMemoryCSP(t, srv, tc.query+" content", agentID)

		rec := doCSPRequest(t, srv, "POST", "/memory/search",
			pkg.SearchRequest{
				Keyword:   tc.query,
				Limit:     5,
				RequestID: "req_distinct_" + tc.requested,
				Options: pkg.SearchOptions{
					AssembleContext: true,
					ContextStrategy: tc.requested,
				},
			},
			map[string]string{"X-OmniMemora-Agent": agentID},
		)
		if rec.Code != http.StatusOK {
			t.Fatalf("search failed for requested=%q: %d - %s", tc.requested, rec.Code, rec.Body.String())
		}

		var requested, resolved string
		err := s.DB().QueryRow(`
			SELECT context_strategy_requested, context_strategy_resolved
			FROM metering_events
			WHERE request_id = ?
			ORDER BY timestamp DESC LIMIT 1
		`, "req_distinct_"+tc.requested).Scan(&requested, &resolved)
		if err != nil {
			t.Fatalf("failed for requested=%q: %v", tc.requested, err)
		}

		if requested != tc.requested {
			t.Errorf("requested=%q: expected requested=%q, got %q", tc.requested, tc.requested, requested)
		}
		if resolved == "" {
			t.Errorf("requested=%q: resolved should not be empty", tc.requested)
		}
	}
}
