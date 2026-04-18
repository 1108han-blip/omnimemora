package cli

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestResolveRecoverFamily(t *testing.T) {
	familyID, agentType, err := resolveRecoverFamily("claude")
	if err != nil {
		t.Fatalf("expected claude to resolve, got err=%v", err)
	}
	if familyID != "claude_code" {
		t.Fatalf("expected claude_code family, got %q", familyID)
	}
	if string(agentType) == "" {
		t.Fatalf("expected non-empty agent type")
	}
}

func TestRecoverDisableRouteWritesDecisionOffline(t *testing.T) {
	tmpDir := t.TempDir()
	agentModesPath := filepath.Join(tmpDir, "agent_modes.json")
	decisionPath := filepath.Join(tmpDir, "gateway_decision.json")

	t.Setenv("OMNIMEMORA_AGENT_MODES_PATH", agentModesPath)
	t.Setenv("OMNIMEMORA_GATEWAY_DECISION_PATH", decisionPath)

	if err := os.WriteFile(agentModesPath, []byte(`{"per_agent_modes":{"claude_code":"force_if_possible"},"default_mode":"off"}`), 0644); err != nil {
		t.Fatalf("failed to seed agent modes: %v", err)
	}

	if err := Recover([]string{"disable-route", "claude"}); err != nil {
		t.Fatalf("recover disable-route failed: %v", err)
	}

	rawModes, err := os.ReadFile(agentModesPath)
	if err != nil {
		t.Fatalf("failed to read agent modes: %v", err)
	}
	if !strings.Contains(string(rawModes), `"claude_code": "off"`) {
		t.Fatalf("expected claude_code off, got %s", string(rawModes))
	}

	rawDecision, err := os.ReadFile(decisionPath)
	if err != nil {
		t.Fatalf("failed to read gateway decision: %v", err)
	}
	if !strings.Contains(string(rawDecision), `"action": "disable-route"`) {
		t.Fatalf("expected disable-route decision, got %s", string(rawDecision))
	}
}
