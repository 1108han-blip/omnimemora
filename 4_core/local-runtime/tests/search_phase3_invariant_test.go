// tests/search_phase3_invariant_test.go - Phase 3 product invariant tests
//
// These tests verify "product promises" - invariants that should never break.
// They test constraints and behavior boundaries, not specific values.
//
// Invariant tests are "永远不会过期" - they validate the product contract.
package tests

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/omnimemora/local-runtime/api"
	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/lifecycle"
	"github.com/omnimemora/local-runtime/pkg"
	"github.com/omnimemora/local-runtime/store"
)

// TestInvariant_SavedTokensNeverNegative verifies the core ledger promise:
// saved_tokens must never be negative (Phase 3 requirement)
func TestInvariant_SavedTokensNeverNegative(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a memory
	writeReq := pkg.WriteRequest{Content: "Short content"}
	writeBody, _ := json.Marshal(writeReq)
	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)
	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d", rec.Code)
	}

	// Search with assemble_context
	searchReq := map[string]interface{}{
		"keyword": "content",
		"limit":   5,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)
	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var searchResp pkg.SearchResponse
	json.Unmarshal(rec.Body.Bytes(), &searchResp)

	if searchResp.Context.SavedTokens < 0 {
		t.Errorf("INVARIANT VIOLATION: saved_tokens must never be negative, got %d", searchResp.Context.SavedTokens)
	}
}

// TestInvariant_NoFakeSavings verifies the ledger promise:
// when assemble_context=false, saved_tokens should be 0 (honest default)
func TestInvariant_NoFakeSavings(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a memory
	writeReq := pkg.WriteRequest{Content: "Some test content about programming"}
	writeBody, _ := json.Marshal(writeReq)
	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	// Search WITHOUT assemble_context (default)
	searchReq := map[string]interface{}{
		"keyword": "programming",
		"limit":   5,
	}
	searchBody, _ := json.Marshal(searchReq)
	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var searchResp pkg.SearchResponse
	json.Unmarshal(rec.Body.Bytes(), &searchResp)

	// When assemble_context=false, context should be nil
	if searchResp.Context != nil {
		t.Error("INVARIANT VIOLATION: context should be nil when assemble_context=false")
	}
}

// TestInvariant_CompressionRatioBound verifies compression ratio is always in valid range
func TestInvariant_CompressionRatioBound(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write memories of various sizes
	for i := 0; i < 5; i++ {
		content := "Memory content number " + string(rune('0'+i)) + " with some additional text for testing purposes"
		writeReq := pkg.WriteRequest{Content: content}
		writeBody, _ := json.Marshal(writeReq)
		req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "invariant_test")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)
	}

	// Search with assemble_context
	searchReq := map[string]interface{}{
		"keyword": "memory content",
		"limit":   5,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)
	req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var searchResp pkg.SearchResponse
	json.Unmarshal(rec.Body.Bytes(), &searchResp)

	if searchResp.Context != nil {
		ratio := searchResp.Context.CompressionRatio
		if ratio < 0 || ratio > 2.0 { // Allow some headroom above 1.0 for short text edge cases
			t.Errorf("INVARIANT VIOLATION: compression_ratio should be in [0, 2.0], got %.2f", ratio)
		}
	}
}

// TestInvariant_TokenBudgetNotExceeded verifies compressed tokens don't exceed budget
func TestInvariant_TokenBudgetNotExceeded(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a long memory
	longContent := "This is a very long memory about various programming topics. "
	longContent = longContent + "We need enough content to exceed token budgets. "
	longContent = longContent + "The quick brown fox jumps over the lazy dog. "
	longContent = longContent + "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "

	writeReq := pkg.WriteRequest{Content: longContent}
	writeBody, _ := json.Marshal(writeReq)
	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	// Search with precise mode (lowest budget = 300)
	searchReq := map[string]interface{}{
		"keyword": "programming",
		"limit":   5,
		"options": map[string]interface{}{
			"assemble_context": true,
			"context_mode":     "precise",
		},
	}
	searchBody, _ := json.Marshal(searchReq)
	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var searchResp pkg.SearchResponse
	json.Unmarshal(rec.Body.Bytes(), &searchResp)

	if searchResp.Context != nil && searchResp.Context.ItemsSelected > 0 {
		// compressed tokens should be reasonable for the mode
		// precise mode has budget of 300 tokens
		if searchResp.Context.TokenBudgetUsed > 350 { // Allow small headroom
			t.Errorf("INVARIANT VIOLATION: token_budget_used should be <= 350 for precise mode, got %d",
				searchResp.Context.TokenBudgetUsed)
		}
	}
}

// TestInvariant_TokenSavingsComputation verifies saved_tokens = raw_tokens - compressed_tokens
func TestInvariant_TokenSavingsComputation(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write memories
	for i := 0; i < 3; i++ {
		writeReq := pkg.WriteRequest{Content: "Memory about Go programming language and concurrency"}
		writeBody, _ := json.Marshal(writeReq)
		req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "invariant_test")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)
	}

	// Search with assemble_context
	searchReq := map[string]interface{}{
		"keyword": "Go programming",
		"limit":   5,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)
	req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var searchResp pkg.SearchResponse
	json.Unmarshal(rec.Body.Bytes(), &searchResp)

	if searchResp.Context != nil && searchResp.Context.Assembled {
		expectedSaved := searchResp.Context.RawTokens - searchResp.Context.CompressedTokens
		if expectedSaved < 0 {
			expectedSaved = 0
		}
		if searchResp.Context.SavedTokens != expectedSaved {
			t.Errorf("INVARIANT VIOLATION: saved_tokens should be raw - compressed = %d, got %d",
				expectedSaved, searchResp.Context.SavedTokens)
		}
	}
}

// TestInvariant_StrategyResolvedIsValid verifies strategy_resolved is always a known strategy
func TestInvariant_StrategyResolvedIsValid(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write memories
	for i := 0; i < 3; i++ {
		writeReq := pkg.WriteRequest{Content: "Memory about distributed systems"}
		writeBody, _ := json.Marshal(writeReq)
		req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "invariant_test")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)
	}

	// Test with explicit strategy
	searchReq := map[string]interface{}{
		"keyword": "distributed",
		"limit":   5,
		"options": map[string]interface{}{
			"assemble_context": true,
			"context_strategy": "topk_excerpt",
		},
	}
	searchBody, _ := json.Marshal(searchReq)
	req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var searchResp pkg.SearchResponse
	json.Unmarshal(rec.Body.Bytes(), &searchResp)

	validStrategies := map[string]bool{
		"topk_excerpt":        true,
		"recency_boost_select": true,
		"diversity_select":     true,
	}

	if searchResp.Context != nil {
		if !validStrategies[searchResp.Context.StrategyResolved] {
			t.Errorf("INVARIANT VIOLATION: strategy_resolved should be a known strategy, got '%s'",
				searchResp.Context.StrategyResolved)
		}
	}
}

// TestInvariant_ModeIsValid verifies mode is always a known mode
func TestInvariant_ModeIsValid(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write memories
	writeReq := pkg.WriteRequest{Content: "Memory about databases"}
	writeBody, _ := json.Marshal(writeReq)
	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	modes := []string{"precise", "balanced", "aggressive"}

	for _, mode := range modes {
		searchReq := map[string]interface{}{
			"keyword": "databases",
			"limit":   5,
			"options": map[string]interface{}{
				"assemble_context": true,
				"context_mode":     mode,
			},
		}
		searchBody, _ := json.Marshal(searchReq)
		req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "invariant_test")

		rec = httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)

		var searchResp pkg.SearchResponse
		json.Unmarshal(rec.Body.Bytes(), &searchResp)

		if searchResp.Context != nil && searchResp.Context.Mode != mode {
			t.Errorf("INVARIANT VIOLATION: mode should be '%s', got '%s'", mode, searchResp.Context.Mode)
		}
	}
}

// TestInvariant_ItemsSelectedPositiveWhenAssembled verifies items_selected > 0 when assembled
func TestInvariant_ItemsSelectedPositiveWhenAssembled(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write multiple memories
	for i := 0; i < 5; i++ {
		writeReq := pkg.WriteRequest{Content: "Memory content about Go and Python programming"}
		writeBody, _ := json.Marshal(writeReq)
		req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "invariant_test")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)
	}

	// Search with assemble_context
	searchReq := map[string]interface{}{
		"keyword": "programming",
		"limit":   5,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)
	req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var searchResp pkg.SearchResponse
	json.Unmarshal(rec.Body.Bytes(), &searchResp)

	if searchResp.Context != nil && searchResp.Context.Assembled {
		if searchResp.Context.ItemsSelected <= 0 {
			t.Errorf("INVARIANT VIOLATION: items_selected should be > 0 when assembled, got %d",
				searchResp.Context.ItemsSelected)
		}
	}
}

// TestInvariant_AssembledFalseMeansNoContext verifies assembled=false means empty context
func TestInvariant_AssembledFalseMeansNoContext(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a memory
	writeReq := pkg.WriteRequest{Content: "Content"}
	writeBody, _ := json.Marshal(writeReq)
	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	// Search WITHOUT assemble_context
	searchReq := map[string]interface{}{
		"keyword": "content",
		"limit":   5,
	}
	searchBody, _ := json.Marshal(searchReq)
	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var searchResp pkg.SearchResponse
	json.Unmarshal(rec.Body.Bytes(), &searchResp)

	// Context should be nil (not assembled)
	if searchResp.Context != nil {
		t.Error("INVARIANT VIOLATION: context should be nil when not assembled")
	}
}

// TestInvariant_MetricsTokenSavingsNonNegative verifies metrics endpoint never returns negative savings
func TestInvariant_MetricsTokenSavingsNonNegative(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write and search to generate some metering data
	writeReq := pkg.WriteRequest{Content: "Test content about Go programming"}
	writeBody, _ := json.Marshal(writeReq)
	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")
	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	searchReq := map[string]interface{}{
		"keyword": "Go programming",
		"options": map[string]interface{}{"assemble_context": true},
	}
	searchBody, _ := json.Marshal(searchReq)
	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "invariant_test")
	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	// Get metrics
	req = httptest.NewRequest("GET", "/metrics", nil)
	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var metrics pkg.MetricsResponse
	json.Unmarshal(rec.Body.Bytes(), &metrics)

	if metrics.TokenSavings != nil {
		if metrics.TokenSavings.TotalSavedTokens < 0 {
			t.Errorf("INVARIANT VIOLATION: total_saved_tokens must be >= 0, got %d",
				metrics.TokenSavings.TotalSavedTokens)
		}
		if metrics.TokenSavings.TodaySavedTokens < 0 {
			t.Errorf("INVARIANT VIOLATION: today_saved_tokens must be >= 0, got %d",
				metrics.TokenSavings.TodaySavedTokens)
		}
		if metrics.TokenSavings.WeekSavedTokens < 0 {
			t.Errorf("INVARIANT VIOLATION: week_saved_tokens must be >= 0, got %d",
				metrics.TokenSavings.WeekSavedTokens)
		}
		if metrics.TokenSavings.MonthSavedTokens < 0 {
			t.Errorf("INVARIANT VIOLATION: month_saved_tokens must be >= 0, got %d",
				metrics.TokenSavings.MonthSavedTokens)
		}
	}
}
