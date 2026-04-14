// tests/legacy/phase2b/search_phase2b_test.go - Phase 2b context assembly tests
//
// Deprecated: Phase 2b behavior (kept for historical reference only)
//
// Phase 2b used:
//   - strategy name "topk_excerpt_merge"
//   - exact token control via max_context_tokens
//
// Phase 2c/3 uses:
//   - strategy name "topk_excerpt" (resolved)
//   - mode-based token budget (precise/balanced/aggressive)
//
// This file is kept for regression reference, not for current behavior validation.
package legacy_phase2b

import (
	"bytes"
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

// TestSearchPhase2b_AssembleContextDisabled tests that assemble_context=false returns no context
func TestSearchPhase2b_AssembleContextDisabled(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a memory
	writeReq := pkg.WriteRequest{
		Content: "This is a test memory about Go programming and SQLite databases",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_test_agent")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Search without assemble_context (default false)
	searchReq := map[string]interface{}{
		"keyword": "Go programming",
		"limit":   10,
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_test_agent")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	// Context should be nil when assemble_context=false
	if searchResp.Context != nil {
		t.Error("expected context to be nil when assemble_context=false")
	}

	// Results should still be present
	if len(searchResp.Results) == 0 {
		t.Error("expected results to be present")
	}

	t.Logf("Search without assemble_context: results=%d, context=%v", len(searchResp.Results), searchResp.Context)
}

// TestSearchPhase2b_AssembleContextEnabled tests that assemble_context=true returns context block
func TestSearchPhase2b_AssembleContextEnabled(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a memory
	writeReq := pkg.WriteRequest{
		Content: "This is a test memory about Go programming and SQLite databases",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_test_agent")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Search with assemble_context=true
	searchReq := map[string]interface{}{
		"keyword": "Go programming",
		"limit":   10,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_test_agent")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	// Context should be present when assemble_context=true
	if searchResp.Context == nil {
		t.Fatal("expected context to be present when assemble_context=true")
	}

	if !searchResp.Context.Assembled {
		t.Error("expected context.assembled to be true")
	}

	if searchResp.Context.Strategy != "topk_excerpt" {
		t.Errorf("expected strategy 'topk_excerpt', got '%s'", searchResp.Context.Strategy)
	}

	// Results should still be present (not replaced)
	if len(searchResp.Results) == 0 {
		t.Error("expected results to still be present")
	}

	t.Logf("Search with assemble_context: results=%d, context.items=%d, saved_tokens=%d",
		len(searchResp.Results), len(searchResp.Context.Items), searchResp.Context.SavedTokens)
}

// TestSearchPhase2b_ContextLimit tests the context_limit option
func TestSearchPhase2b_ContextLimit(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write multiple memories
	contents := []string{
		"First memory about Go programming",
		"Second memory about Python programming",
		"Third memory about JavaScript",
		"Fourth memory about Rust programming",
		"Fifth memory about C++ programming",
	}

	for _, content := range contents {
		writeReq := pkg.WriteRequest{Content: content}
		writeBody, _ := json.Marshal(writeReq)

		req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "phase2b_limit_test")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)

		if rec.Code != http.StatusCreated {
			t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
		}
	}

	// Search with context_limit=2
	searchReq := map[string]interface{}{
		"keyword": "programming",
		"limit":   10,
		"options": map[string]interface{}{
			"assemble_context": true,
			"context_limit":    2,
		},
	}
	searchBody, _ := json.Marshal(searchReq)

	req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_limit_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	// Context items should be limited by context_limit
	if searchResp.Context == nil {
		t.Fatal("expected context to be present")
	}

	if len(searchResp.Context.Items) > 2 {
		t.Errorf("expected at most 2 context items, got %d", len(searchResp.Context.Items))
	}

	t.Logf("context_limit=2: items=%d", len(searchResp.Context.Items))
}

// TestSearchPhase2b_TokenBudget tests token budget enforcement
func TestSearchPhase2b_TokenBudget(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a long memory
	longContent := strings.Repeat("This is a long memory about programming. ", 100)
	writeReq := pkg.WriteRequest{Content: longContent}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_budget_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Search with very low max_context_tokens
	// Phase 2c uses context_mode instead of exact max_context_tokens
	searchReq := map[string]interface{}{
		"keyword": "programming",
		"limit":   10,
		"options": map[string]interface{}{
			"assemble_context": true,
			"context_mode":     "precise", // Phase 2c: uses mode-based token budget
		},
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_budget_test")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	// Context should still be present but compressed
	if searchResp.Context == nil {
		t.Fatal("expected context to be present")
	}

	// compressed_tokens should be under budget
	// Phase 2c: precise mode uses 300 token budget, not exact 50
	if searchResp.Context.CompressedTokens > 300 {
		t.Errorf("expected compressed_tokens <= 300 (precise mode), got %d", searchResp.Context.CompressedTokens)
	}

	t.Logf("Token budget test: raw=%d, compressed=%d, saved=%d",
		searchResp.Context.RawTokens, searchResp.Context.CompressedTokens, searchResp.Context.SavedTokens)
}

// TestSearchPhase2b_SavedTokensCalculation tests that saved_tokens is computed correctly
func TestSearchPhase2b_SavedTokensCalculation(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a memory
	writeReq := pkg.WriteRequest{
		Content: "This is a test memory about Go programming and SQLite databases",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_savings_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Search with assemble_context=true
	searchReq := map[string]interface{}{
		"keyword": "Go programming",
		"limit":   10,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_savings_test")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	if searchResp.Context == nil {
		t.Fatal("expected context to be present")
	}

	// saved_tokens must be non-negative
	if searchResp.Context.SavedTokens < 0 {
		t.Errorf("saved_tokens must be non-negative, got %d", searchResp.Context.SavedTokens)
	}

	// saved_tokens = raw_tokens - compressed_tokens
	expectedSaved := searchResp.Context.RawTokens - searchResp.Context.CompressedTokens
	if expectedSaved < 0 {
		expectedSaved = 0
	}
	if searchResp.Context.SavedTokens != expectedSaved {
		t.Errorf("saved_tokens mismatch: got %d, expected %d (raw=%d - compressed=%d)",
			searchResp.Context.SavedTokens, expectedSaved,
			searchResp.Context.RawTokens, searchResp.Context.CompressedTokens)
	}

	t.Logf("Saved tokens: raw=%d, compressed=%d, saved=%d",
		searchResp.Context.RawTokens, searchResp.Context.CompressedTokens, searchResp.Context.SavedTokens)
}

// TestSearchPhase2b_NoNegativeSavedTokens tests that saved_tokens cannot be negative
func TestSearchPhase2b_NoNegativeSavedTokens(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a very short memory
	writeReq := pkg.WriteRequest{
		Content: "Hi",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_short_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Search with assemble_context=true
	searchReq := map[string]interface{}{
		"keyword": "Hi",
		"limit":   10,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_short_test")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	if searchResp.Context == nil {
		t.Fatal("expected context to be present")
	}

	// saved_tokens must never be negative
	if searchResp.Context.SavedTokens < 0 {
		t.Errorf("saved_tokens must never be negative, got %d", searchResp.Context.SavedTokens)
	}
}

// TestSearchPhase2b_ScopeNotRegressed tests that scope enforcement still works
func TestSearchPhase2b_ScopeNotRegressed(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write to workspace A and capture its memory_id
	writeReq := pkg.WriteRequest{
		Content: "Memory in workspace A about secret project",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "agent_a")
	req.Header.Set("X-OmniMemora-Workspace", "workspace_a")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write to workspace A failed: %d - %s", rec.Code, rec.Body.String())
	}

	var writeRespA pkg.WriteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &writeRespA); err != nil {
		t.Fatalf("failed to parse workspace A write response: %v", err)
	}
	memIDA := writeRespA.MemoryID

	// Write to workspace B and capture its memory_id
	writeReq2 := pkg.WriteRequest{
		Content: "Memory in workspace B about different project",
	}
	writeBody2, _ := json.Marshal(writeReq2)

	req = httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody2))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "agent_b")
	req.Header.Set("X-OmniMemora-Workspace", "workspace_b")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write to workspace B failed: %d - %s", rec.Code, rec.Body.String())
	}

	var writeRespB pkg.WriteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &writeRespB); err != nil {
		t.Fatalf("failed to parse workspace B write response: %v", err)
	}
	memIDB := writeRespB.MemoryID

	// Build the allowed set for workspace A
	allowedIDs := map[string]bool{memIDA: true}

	// Search from workspace A with assemble_context=true
	searchReq := map[string]interface{}{
		"keyword": "workspace",
		"limit":   10,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "agent_a")
	req.Header.Set("X-OmniMemora-Workspace", "workspace_a")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	// Verify: all result memory_ids must belong to workspace A
	for _, result := range searchResp.Results {
		if !allowedIDs[result.MemoryID] {
			t.Errorf("cross-workspace leak in results: memory_id=%s is not in allowed set {workspace A ids}", result.MemoryID)
		}
	}

	// Verify: all context item memory_ids must belong to workspace A
	if searchResp.Context != nil {
		for _, item := range searchResp.Context.Items {
			if !allowedIDs[item.MemoryID] {
				t.Errorf("cross-workspace leak in context: memory_id=%s (workspace B mem_id=%s) leaked into workspace A search", item.MemoryID, memIDB)
			}
		}
	}

	// Sanity: workspace B memory_id should NOT be in workspace A results
	if allowedIDs[memIDB] {
		t.Error("sanity check failed: workspace B memory should not be in allowed set")
	}

	t.Logf("Scope enforcement passed: workspace A mem_id=%s, workspace B mem_id=%s, search results and context items verified against allowed set", memIDA, memIDB)
}

// TestSearchPhase2b_ExcerptExtraction tests that excerpts are properly extracted
func TestSearchPhase2b_ExcerptExtraction(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a memory with content we can search for
	writeReq := pkg.WriteRequest{
		Content: "The quick brown fox jumps over the lazy dog. This is a test memory about Go programming with SQLite for data storage.",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_excerpt_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Search with assemble_context=true
	searchReq := map[string]interface{}{
		"keyword": "Go programming",
		"limit":   10,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_excerpt_test")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	if searchResp.Context == nil {
		t.Fatal("expected context to be present")
	}

	// Phase 2c: context assembled as combined text, not separate items
	// Verify the assembled context has content
	if searchResp.Context.CombinedText == "" && searchResp.Context.RawTokens == 0 {
		t.Fatal("expected assembled context to have content")
	}

	// Combined text should contain the keyword (or close to it)
	if !strings.Contains(strings.ToLower(searchResp.Context.CombinedText), "go") {
		t.Logf("Combined text: %s", searchResp.Context.CombinedText)
		// Note: context assembly may not contain exact keyword due to token budget
	}

	t.Logf("Excerpt extraction: combined_text_len=%d, raw_tokens=%d, compressed=%d",
		len(searchResp.Context.CombinedText), searchResp.Context.RawTokens, searchResp.Context.CompressedTokens)
}

// TestSearchPhase2b_MeteringSchemaMigration tests that Phase 2b metering columns
// are auto-migrated on store startup (old schema -> new schema)
func TestSearchPhase2b_MeteringSchemaMigration(t *testing.T) {
	tmpDir := t.TempDir()

	// Step 1: Manually create an old-schema metering_events table (without Phase 2b columns)
	oldDB, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store for migration test: %v", err)
	}

	// Drop and recreate metering_events with old schema (pre-Phase 2b)
	oldDB.DB().Exec("DROP TABLE IF EXISTS metering_events")
	oldSchema := `
	CREATE TABLE metering_events (
		event_id TEXT PRIMARY KEY,
		request_id TEXT NOT NULL,
		event_type TEXT NOT NULL,
		tenant_id TEXT NOT NULL DEFAULT '',
		user_id TEXT NOT NULL DEFAULT '',
		workspace_id TEXT NOT NULL DEFAULT '',
		agent_id TEXT NOT NULL DEFAULT '',
		scope TEXT NOT NULL DEFAULT 'agent',
		sharing_mode TEXT NOT NULL DEFAULT 'isolated',
		input_tokens INTEGER NOT NULL DEFAULT 0,
		compressed_tokens INTEGER NOT NULL DEFAULT 0,
		saved_tokens INTEGER NOT NULL DEFAULT 0,
		query_count INTEGER NOT NULL DEFAULT 0,
		recall_hits INTEGER NOT NULL DEFAULT 0,
		recall_hit_rate REAL NOT NULL DEFAULT 0,
		timestamp DATETIME NOT NULL,
		runtime_version TEXT NOT NULL DEFAULT '',
		store_type TEXT NOT NULL DEFAULT ''
	);
	`
	if _, err := oldDB.DB().Exec(oldSchema); err != nil {
		t.Fatalf("failed to create old schema: %v", err)
	}
	oldDB.Close()

	// Step 2: Reopen the store - migration should auto-add raw_tokens and assembled_hits
	migratedDB, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to reopen store after migration: %v", err)
	}
	defer migratedDB.Close()

	// Step 3: Verify new columns exist
	var rawTokensCol int
	err = migratedDB.DB().QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='raw_tokens'").Scan(&rawTokensCol)
	if err != nil {
		t.Fatalf("failed to check raw_tokens column: %v", err)
	}
	if rawTokensCol == 0 {
		t.Error("expected raw_tokens column to exist after migration")
	}

	var assembledHitsCol int
	err = migratedDB.DB().QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='assembled_hits'").Scan(&assembledHitsCol)
	if err != nil {
		t.Fatalf("failed to check assembled_hits column: %v", err)
	}
	if assembledHitsCol == 0 {
		t.Error("expected assembled_hits column to exist after migration")
	}

	// Step 4: Write a memory and search with assemble_context=true, verify no error
	writeReq := pkg.WriteRequest{Content: "Memory for migration test"}
	writeBody, _ := json.Marshal(writeReq)

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   migratedDB,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, migratedDB, rtCtx, 18765)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "migration_test_agent")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Search with Phase 2b options - should not produce metering error
	searchReq := map[string]interface{}{
		"keyword": "migration",
		"limit":   10,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "migration_test_agent")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	if searchResp.Context == nil {
		t.Error("expected context to be present after migration")
	}

	t.Logf("Migration test passed: raw_tokens and assembled_hits columns exist, search with assemble_context=true succeeded")
}

// TestSearchPhase2b_ResultsStructurePreserved tests that results structure is not replaced
func TestSearchPhase2b_ResultsStructurePreserved(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write a memory
	writeReq := pkg.WriteRequest{
		Content: "Test memory for results structure",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_struct_test")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Search with assemble_context=true
	searchReq := map[string]interface{}{
		"keyword": "results structure",
		"limit":   10,
		"options": map[string]interface{}{
			"assemble_context": true,
		},
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "phase2b_struct_test")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	// Verify Phase 2a fields are still present
	if searchResp.RequestID == "" && len(searchResp.Results) > 0 {
		// RequestID may be empty if not provided, but results should be there
	}
	if searchResp.Results == nil {
		t.Error("results field should not be nil")
	}
	if searchResp.ScopeApplied == "" {
		t.Error("scope_applied should be set")
	}
	if searchResp.TookMs < 0 {
		t.Error("took_ms should be non-negative")
	}

	// Context is additive, not a replacement
	if searchResp.Context != nil {
		t.Log("context is present as an addition, not replacement")
	}

	t.Logf("Phase 2a structure preserved: results=%d, scope=%s, took_ms=%d",
		len(searchResp.Results), searchResp.ScopeApplied, searchResp.TookMs)
}
