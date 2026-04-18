package tests

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/omnimemora/local-runtime/api"
	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/lifecycle"
	"github.com/omnimemora/local-runtime/store"
)

func TestGatewayStatusEndpointDefaultsHealthy(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("OMNIMEMORA_RUNTIME_DATA_DIR", tmpDir)

	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	req := httptest.NewRequest("GET", "/gateway/status", nil)
	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	var payload map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatalf("failed to decode payload: %v", err)
	}
	if payload["status"] != "healthy" {
		t.Fatalf("expected healthy status, got %v", payload["status"])
	}
}

func TestGatewayStatusEndpointReadsTrackBFile(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("OMNIMEMORA_RUNTIME_DATA_DIR", tmpDir)
	err := os.WriteFile(
		filepath.Join(tmpDir, "track_b_status.json"),
		[]byte(`{"status":"user-decision-required","recommended_action":"disable_route_or_uninstall","user_action_required":true}`),
		0644,
	)
	if err != nil {
		t.Fatalf("failed to write status file: %v", err)
	}

	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	req := httptest.NewRequest("GET", "/gateway/status", nil)
	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	body := rec.Body.String()
	if !strings.Contains(body, "user-decision-required") {
		t.Fatalf("expected gateway status body to contain override, got %s", body)
	}
}

func TestDashboardShowsGatewayAlertWhenDecisionRequired(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("OMNIMEMORA_RUNTIME_DATA_DIR", tmpDir)
	err := os.WriteFile(
		filepath.Join(tmpDir, "track_b_status.json"),
		[]byte(`{"status":"user-decision-required","recommended_action":"disable_route_or_uninstall","user_action_required":true,"error_code":"gateway_unreachable"}`),
		0644,
	)
	if err != nil {
		t.Fatalf("failed to write status file: %v", err)
	}

	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	req := httptest.NewRequest("GET", "/dashboard", nil)
	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}

	body := rec.Body.String()
	if !strings.Contains(body, "Gateway status: user-decision-required") {
		t.Fatalf("expected dashboard alert, got body %s", body)
	}
	if !strings.Contains(body, "User decision required before changing install state.") {
		t.Fatalf("expected dashboard decision text, got body %s", body)
	}
}

func TestGatewayDecisionDisableRouteWritesAgentModes(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("OMNIMEMORA_RUNTIME_DATA_DIR", tmpDir)
	agentModesPath := filepath.Join(tmpDir, "agent_modes.json")
	t.Setenv("OMNIMEMORA_AGENT_MODES_PATH", agentModesPath)
	err := os.WriteFile(agentModesPath, []byte(`{"per_agent_modes":{"openclaw":"force_if_possible"},"default_mode":"off"}`), 0644)
	if err != nil {
		t.Fatalf("failed to write agent modes: %v", err)
	}

	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	req := httptest.NewRequest("POST", "/gateway/decision/disable-route", strings.NewReader(`{"family_id":"openclaw"}`))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", rec.Code, rec.Body.String())
	}

	raw, err := os.ReadFile(agentModesPath)
	if err != nil {
		t.Fatalf("failed to read agent modes: %v", err)
	}
	if !strings.Contains(string(raw), `"openclaw": "off"`) {
		t.Fatalf("expected openclaw off in agent modes, got %s", string(raw))
	}
}
