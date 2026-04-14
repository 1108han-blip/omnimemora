// tests/health_test.go - Health endpoint tests
package tests

import (
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

// TestHealthEndpoint tests GET /health
func TestHealthEndpoint(t *testing.T) {
	// Create a temporary store
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	// Create runtime context
	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	// Create server
	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Create request
	req := httptest.NewRequest("GET", "/health", nil)
	rec := httptest.NewRecorder()

	// Serve
	server.Handler().ServeHTTP(rec, req)

	// Check status
	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200, got %d", rec.Code)
	}

	// Parse response
	var health pkg.HealthResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &health); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}

	// Verify fields
	if health.Status != "ok" {
		t.Errorf("expected status 'ok', got '%s'", health.Status)
	}
	if health.Version != "1.0.0" {
		t.Errorf("expected version '1.0.0', got '%s'", health.Version)
	}
	if health.Mode != "local" {
		t.Errorf("expected mode 'local', got '%s'", health.Mode)
	}
	if health.StoreType != "sqlite" {
		t.Errorf("expected store_type 'sqlite', got '%s'", health.StoreType)
	}
}

// TestHealthUnauthenticated tests that health works without API key
func TestHealthUnauthenticated(t *testing.T) {
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

	// Request without any headers (no API key)
	req := httptest.NewRequest("GET", "/health", nil)
	rec := httptest.NewRecorder()

	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected status 200 without API key, got %d", rec.Code)
	}
}
