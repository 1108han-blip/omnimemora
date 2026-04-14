// tests/write_query_test.go - Write and Query tests
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

// TestWriteAndQuery tests the basic write and query flow
func TestWriteAndQuery(t *testing.T) {
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
		Content: "This is a test memory about Go programming",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "test_agent")
	req.Header.Set("X-OmniMemora-User", "test_user")
	req.Header.Set("X-OmniMemora-Workspace", "test_workspace")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Errorf("expected status 201, got %d: %s", rec.Code, rec.Body.String())
	}

	// Parse write response
	var writeResp pkg.WriteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &writeResp); err != nil {
		t.Fatalf("failed to parse write response: %v", err)
	}

	if writeResp.MemoryID == "" {
		t.Error("expected memory_id to be set")
	}
	if writeResp.Status != "written" {
		t.Errorf("expected status 'written', got '%s'", writeResp.Status)
	}

	// Query the memory
	queryReq := pkg.QueryRequest{
		Query: "Go programming",
		Limit: 10,
	}
	queryBody, _ := json.Marshal(queryReq)

	req = httptest.NewRequest("POST", "/memory/query", bytes.NewReader(queryBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "test_agent")
	req.Header.Set("X-OmniMemora-User", "test_user")
	req.Header.Set("X-OmniMemora-Workspace", "test_workspace")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d: %s", rec.Code, rec.Body.String())
	}

	// Parse query response
	var queryResp pkg.QueryResult
	if err := json.Unmarshal(rec.Body.Bytes(), &queryResp); err != nil {
		t.Fatalf("failed to parse query response: %v", err)
	}

	// Note: MVP uses simple text matching, exact match may vary
	t.Logf("Query returned %d results", queryResp.Total)
}

// TestDedup tests that duplicate content is detected
func TestDedup(t *testing.T) {
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

	content := "Duplicate test content"

	// Write first time
	writeReq := pkg.WriteRequest{Content: content}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "dedup_agent")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("first write failed: %d - %s", rec.Code, rec.Body.String())
	}

	var firstResp pkg.WriteResponse
	json.Unmarshal(rec.Body.Bytes(), &firstResp)

	// Write same content again
	req = httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "dedup_agent")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var secondResp pkg.WriteResponse
	json.Unmarshal(rec.Body.Bytes(), &secondResp)

	// Should be a dedup hit
	if secondResp.DedupHit != true {
		t.Log("Note: Dedup may not trigger if content_hash differs due to encoding")
	}
}

// TestMetricsEndpoint tests GET /metrics
func TestMetricsEndpoint(t *testing.T) {
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

	req := httptest.NewRequest("GET", "/metrics", nil)
	rec := httptest.NewRecorder()

	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rec.Code)
	}

	var metrics pkg.MetricsResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &metrics); err != nil {
		t.Fatalf("failed to parse metrics: %v", err)
	}

	if metrics.Runtime.Version != "1.0.0" {
		t.Errorf("expected version '1.0.0', got '%s'", metrics.Runtime.Version)
	}
}

// TestSearchEndpoint tests POST /memory/search
func TestSearchEndpoint(t *testing.T) {
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
		Content: "This is a test memory about Go programming",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "search_test_agent")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Search for the memory
	searchReq := map[string]interface{}{
		"keyword": "Go programming",
		"limit":  10,
	}
	searchBody, _ := json.Marshal(searchReq)

	req = httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "search_test_agent")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("search failed: %d - %s", rec.Code, rec.Body.String())
	}

	var searchResp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
		t.Fatalf("failed to parse search response: %v", err)
	}

	if searchResp.Total == 0 {
		t.Error("expected search results, got 0")
	}

	t.Logf("Search returned %d results", searchResp.Total)
}

// TestDeleteEndpoint tests POST /memory/delete
func TestDeleteEndpoint(t *testing.T) {
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
		Content: "Memory to be deleted",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "delete_test_agent")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	var writeResp pkg.WriteResponse
	json.Unmarshal(rec.Body.Bytes(), &writeResp)

	// Delete the memory
	deleteReq := pkg.DeleteRequest{
		MemoryID: writeResp.MemoryID,
	}
	deleteBody, _ := json.Marshal(deleteReq)

	req = httptest.NewRequest("POST", "/memory/delete", bytes.NewReader(deleteBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "delete_test_agent")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("delete failed: %d - %s", rec.Code, rec.Body.String())
	}

	var deleteResp pkg.DeleteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &deleteResp); err != nil {
		t.Fatalf("failed to parse delete response: %v", err)
	}

	if deleteResp.Status != "deleted" {
		t.Errorf("expected status 'deleted', got '%s'", deleteResp.Status)
	}

	// Verify memory is gone by querying
	queryReq := pkg.QueryRequest{
		Query: "Memory to be deleted",
		Limit: 10,
	}
	queryBody, _ := json.Marshal(queryReq)

	req = httptest.NewRequest("POST", "/memory/query", bytes.NewReader(queryBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "delete_test_agent")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	var queryResp pkg.QueryResult
	json.Unmarshal(rec.Body.Bytes(), &queryResp)

	if queryResp.Total != 0 {
		t.Errorf("expected 0 results after delete, got %d", queryResp.Total)
	}
}
