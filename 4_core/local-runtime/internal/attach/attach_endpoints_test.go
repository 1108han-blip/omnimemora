package attach

import (
	"os"
	"path/filepath"
	"testing"
)

func TestProductAdapterEndpointsDefaultAndOverride(t *testing.T) {
	t.Run("default", func(t *testing.T) {
		t.Setenv("OMNIMEMORA_ADAPTER_PORT", "")
		if got := ProductAdapterEndpoint(); got != "http://127.0.0.1:18011" {
			t.Fatalf("expected default adapter endpoint, got %s", got)
		}
		if got := ProductAdapterMCPEndpoint(); got != "http://127.0.0.1:18011/mcp" {
			t.Fatalf("expected default mcp endpoint, got %s", got)
		}
		if got := ProductAdapterResponsesEndpoint(); got != "http://127.0.0.1:18011/v1" {
			t.Fatalf("expected default responses endpoint, got %s", got)
		}
	})

	t.Run("override", func(t *testing.T) {
		t.Setenv("OMNIMEMORA_ADAPTER_PORT", "18041")
		if got := ProductAdapterEndpoint(); got != "http://127.0.0.1:18041" {
			t.Fatalf("expected overridden adapter endpoint, got %s", got)
		}
		if got := ProductAdapterMCPEndpoint(); got != "http://127.0.0.1:18041/mcp" {
			t.Fatalf("expected overridden mcp endpoint, got %s", got)
		}
		if got := ProductAdapterResponsesEndpoint(); got != "http://127.0.0.1:18041/v1" {
			t.Fatalf("expected overridden responses endpoint, got %s", got)
		}
	})
}

func TestIsAttachedOpenClawUsesProvidedAdapterPort(t *testing.T) {
	tmpHome := t.TempDir()
	t.Setenv("HOME", tmpHome)

	configDir := filepath.Join(tmpHome, ".openclaw")
	if err := os.MkdirAll(configDir, 0o755); err != nil {
		t.Fatalf("mkdir config dir: %v", err)
	}

	config := `{
  "mcp": {
    "servers": {
      "omnimemora": {
        "url": "http://127.0.0.1:18041/mcp",
        "type": "http"
      }
    }
  }
}`
	if err := os.WriteFile(filepath.Join(configDir, "openclaw.json"), []byte(config), 0o644); err != nil {
		t.Fatalf("write config: %v", err)
	}

	if IsAttached(AgentOpenClaw, 18011) {
		t.Fatalf("expected OpenClaw attach detection to reject mismatched adapter port")
	}
	if !IsAttached(AgentOpenClaw, 18041) {
		t.Fatalf("expected OpenClaw attach detection to accept matching adapter port")
	}
}
