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
	"github.com/omnimemora/local-runtime/internal/attach"
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

func TestGatewayDecisionUninstallRestoresClaudeConfigAndDisablesRoute(t *testing.T) {
	tmpDir := t.TempDir()
	homeDir := filepath.Join(tmpDir, "home")
	configPath := filepath.Join(homeDir, ".claude", "settings.json")
	agentModesPath := filepath.Join(tmpDir, "agent_modes.json")

	t.Setenv("HOME", homeDir)
	t.Setenv("OMNIMEMORA_RUNTIME_DATA_DIR", tmpDir)
	t.Setenv("OMNIMEMORA_AGENT_MODES_PATH", agentModesPath)

	if err := os.MkdirAll(filepath.Dir(configPath), 0755); err != nil {
		t.Fatalf("failed to create config dir: %v", err)
	}
	if err := os.WriteFile(configPath, []byte("{\n  \"theme\": \"dark\"\n}\n"), 0644); err != nil {
		t.Fatalf("failed to seed claude config: %v", err)
	}
	if err := os.WriteFile(agentModesPath, []byte(`{"per_agent_modes":{"claude_code":"force_if_possible"},"default_mode":"off"}`), 0644); err != nil {
		t.Fatalf("failed to write agent modes: %v", err)
	}

	result := attach.AttachClaude()
	if !result.Success {
		t.Fatalf("expected attach success, got message: %s", result.Message)
	}

	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{Config: cfg, Store: s, Version: "1.0.0"}
	server := api.NewServer(cfg, s, rtCtx, 18765)

	req := httptest.NewRequest("POST", "/gateway/decision/uninstall", strings.NewReader(`{"family_id":"claude_code"}`))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d body=%s", rec.Code, rec.Body.String())
	}

	rawConfig, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatalf("failed to read restored claude config: %v", err)
	}
	if strings.Contains(string(rawConfig), "\"provider\": \"omnimemora\"") {
		t.Fatalf("expected omnimemora provider removed after uninstall, got %s", string(rawConfig))
	}
	if !strings.Contains(string(rawConfig), "\"theme\": \"dark\"") {
		t.Fatalf("expected original claude config restored, got %s", string(rawConfig))
	}

	rawModes, err := os.ReadFile(agentModesPath)
	if err != nil {
		t.Fatalf("failed to read agent modes: %v", err)
	}
	if !strings.Contains(string(rawModes), `"claude_code": "off"`) {
		t.Fatalf("expected claude_code off after uninstall, got %s", string(rawModes))
	}

	backupRoot := filepath.Join(homeDir, ".omnimemora", "agent-control", "backups")
	entries, err := os.ReadDir(backupRoot)
	if err != nil {
		t.Fatalf("failed to read backup root: %v", err)
	}
	if len(entries) != 0 {
		t.Fatalf("expected backup dir to be empty after restore, got %d entries", len(entries))
	}
}
