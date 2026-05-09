package api

import (
	"encoding/json"
	"testing"
)

func TestAgentControlStatusIncludesRunning(t *testing.T) {
	status := agentControlStatus{
		FamilyID:    "claude_code",
		DisplayName: "Claude Code",
		Detected:    true,
		Installed:   true,
		Running:     true,
	}

	raw, err := json.Marshal(status)
	if err != nil {
		t.Fatalf("marshal status: %v", err)
	}

	var decoded map[string]any
	if err := json.Unmarshal(raw, &decoded); err != nil {
		t.Fatalf("unmarshal status: %v", err)
	}
	if got, ok := decoded["running"].(bool); !ok || !got {
		t.Fatalf("expected running=true in JSON, got %#v", decoded["running"])
	}
}
