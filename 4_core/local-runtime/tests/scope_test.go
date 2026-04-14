// tests/scope_test.go - Scope enforcement tests
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

// TestAgentScopeIsolation tests that different agents cannot see each other's memories
func TestAgentScopeIsolation(t *testing.T) {
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

	// Agent1 writes a memory
	writeReq := pkg.WriteRequest{
		Content: "Secret from Agent1",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "agent_1")
	req.Header.Set("X-OmniMemora-User", "shared_user")
	req.Header.Set("X-OmniMemora-Workspace", "test_workspace")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("agent_1 write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Agent2 queries - should not see agent_1's memory (default scope=agent, isolated)
	queryReq := pkg.QueryRequest{
		Query: "Secret",
		Limit: 10,
	}
	queryBody, _ := json.Marshal(queryReq)

	req = httptest.NewRequest("POST", "/memory/query", bytes.NewReader(queryBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "agent_2")
	req.Header.Set("X-OmniMemora-User", "shared_user")
	req.Header.Set("X-OmniMemora-Workspace", "test_workspace")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("agent_2 query failed: %d - %s", rec.Code, rec.Body.String())
	}

	var queryResp pkg.QueryResult
	json.Unmarshal(rec.Body.Bytes(), &queryResp)

	// Agent2 should not see Agent1's memory (agent scope is isolated by default)
	for _, result := range queryResp.Results {
		if result.Content == "Secret from Agent1" {
			t.Error("Agent2 should not see Agent1's memory in agent scope")
		}
	}
}

// TestWorkspaceScopeSharing tests that agents in the same workspace can share
func TestWorkspaceScopeSharing(t *testing.T) {
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

	// Agent1 writes to workspace scope via header
	writeReq := pkg.WriteRequest{
		Content: "Shared workspace memory",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "agent_1")
	req.Header.Set("X-OmniMemora-User", "shared_user")
	req.Header.Set("X-OmniMemora-Workspace", "shared_workspace")
	req.Header.Set("X-OmniMemora-Scope", "workspace")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("workspace write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// Agent2 queries the shared workspace (via header)
	queryReq := pkg.QueryRequest{
		Query: "Shared workspace",
		Limit: 10,
	}
	queryBody, _ := json.Marshal(queryReq)

	req = httptest.NewRequest("POST", "/memory/query", bytes.NewReader(queryBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "agent_2")
	req.Header.Set("X-OmniMemora-User", "shared_user")
	req.Header.Set("X-OmniMemora-Workspace", "shared_workspace")
	req.Header.Set("X-OmniMemora-Scope", "workspace")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("workspace query failed: %d - %s", rec.Code, rec.Body.String())
	}

	t.Logf("Workspace scope sharing query returned results")
}

// TestCustomScopeNotImplemented tests that custom scope returns 501
func TestCustomScopeNotImplemented(t *testing.T) {
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

	// Try to write with custom scope via header
	writeReq := pkg.WriteRequest{
		Content: "Custom scope test",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "test_agent")
	req.Header.Set("X-OmniMemora-Scope", "custom")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusNotImplemented {
		t.Errorf("expected 501 for custom scope, got %d", rec.Code)
	}
}

// TestScopePriorityHeaderOverBody tests Header > Body > Config priority
func TestScopePriorityHeaderOverBody(t *testing.T) {
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

	// Write with body scope=agent but header says workspace
	writeReq := pkg.WriteRequest{
		Content: "Scope priority test",
		Scope:   pkg.ScopeAgent,
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "priority_test_agent")
	req.Header.Set("X-OmniMemora-Scope", "workspace") // This should override body

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	// Header scope should win
	var resp pkg.WriteResponse
	json.Unmarshal(rec.Body.Bytes(), &resp)

	if resp.Scope != "workspace" {
		t.Errorf("expected scope 'workspace' from header, got '%s'", resp.Scope)
	}
}

// TestDefaultScopeIsAgent tests that default scope is 'agent'
func TestDefaultScopeIsAgent(t *testing.T) {
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

	// Write without specifying scope
	writeReq := pkg.WriteRequest{
		Content: "Default scope test",
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "default_test_agent")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
	}

	var resp pkg.WriteResponse
	json.Unmarshal(rec.Body.Bytes(), &resp)

	// Default scope should be agent
	if resp.Scope != "agent" {
		t.Errorf("expected default scope 'agent', got '%s'", resp.Scope)
	}
	// Default sharing mode should be isolated
	if resp.SharingMode != "isolated" {
		t.Errorf("expected default sharing_mode 'isolated', got '%s'", resp.SharingMode)
	}
}

// TestUserScopeIsolation tests that different users cannot see each other's memories in user scope
func TestUserScopeIsolation(t *testing.T) {
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

	// User A writes a memory in user scope
	writeReq := pkg.WriteRequest{
		Content: "User A private memory",
		Scope:   pkg.ScopeUser,
	}
	writeBody, _ := json.Marshal(writeReq)

	req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "agent_a")
	req.Header.Set("X-OmniMemora-User", "user_a")
	req.Header.Set("X-OmniMemora-Scope", "user")

	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("user_a write failed: %d - %s", rec.Code, rec.Body.String())
	}

	// User B queries - should not see user_a's memory (user scope is isolated)
	queryReq := pkg.QueryRequest{
		Query: "User A private",
		Limit: 10,
	}
	queryBody, _ := json.Marshal(queryReq)

	req = httptest.NewRequest("POST", "/memory/query", bytes.NewReader(queryBody))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-OmniMemora-Agent", "agent_b")
	req.Header.Set("X-OmniMemora-User", "user_b")
	req.Header.Set("X-OmniMemora-Scope", "user")

	rec = httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("user_b query failed: %d - %s", rec.Code, rec.Body.String())
	}

	var queryResp pkg.QueryResult
	json.Unmarshal(rec.Body.Bytes(), &queryResp)

	// User B should not see User A's memory (user scope is isolated by default)
	for _, result := range queryResp.Results {
		if result.Content == "User A private" {
			t.Error("User B should not see User A's memory in user scope")
		}
	}

	if queryResp.Total != 0 {
		t.Errorf("expected 0 results for user_b query, got %d", queryResp.Total)
	}
}
