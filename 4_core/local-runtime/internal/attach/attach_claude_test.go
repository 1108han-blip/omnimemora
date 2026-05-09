package attach

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestAttachClaudeDoesNotPinAnthropicBaseURLToProduct(t *testing.T) {
	tmpHome := t.TempDir()
	configPath := filepath.Join(tmpHome, ".claude", "settings.json")

	t.Setenv("HOME", tmpHome)

	if err := os.MkdirAll(filepath.Dir(configPath), 0o755); err != nil {
		t.Fatalf("failed to create config dir: %v", err)
	}

	seed := []byte(`{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "real-token",
    "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
    "ANTHROPIC_MODEL": "MiniMax-M2.7"
  },
  "theme": "light"
}`)
	if err := os.WriteFile(configPath, seed, 0o644); err != nil {
		t.Fatalf("failed to seed config: %v", err)
	}

	result := AttachClaude()
	if !result.Success {
		t.Fatalf("expected attach success, got: %s", result.Message)
	}

	raw, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatalf("failed to read config: %v", err)
	}

	var cfg map[string]interface{}
	if err := json.Unmarshal(raw, &cfg); err != nil {
		t.Fatalf("failed to parse config: %v", err)
	}

	memoryCfg, ok := cfg["memory"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected memory block, got %T", cfg["memory"])
	}
	if memoryCfg["provider"] != "omnimemora" {
		t.Fatalf("expected omnimemora provider, got %#v", memoryCfg["provider"])
	}

	envCfg, ok := cfg["env"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected env block, got %T", cfg["env"])
	}
	if envCfg["ANTHROPIC_BASE_URL"] != "https://api.minimaxi.com/anthropic" {
		t.Fatalf("expected direct ANTHROPIC_BASE_URL preserved, got %#v", envCfg["ANTHROPIC_BASE_URL"])
	}
	if envCfg["ANTHROPIC_AUTH_TOKEN"] != "real-token" {
		t.Fatalf("expected auth token preserved, got %#v", envCfg["ANTHROPIC_AUTH_TOKEN"])
	}
}

func TestAttachClaudeRemovesStaleProductAnthropicBaseURL(t *testing.T) {
	tmpHome := t.TempDir()
	configPath := filepath.Join(tmpHome, ".claude", "settings.json")

	t.Setenv("HOME", tmpHome)

	if err := os.MkdirAll(filepath.Dir(configPath), 0o755); err != nil {
		t.Fatalf("failed to create config dir: %v", err)
	}

	seed := []byte(`{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:18011/llm",
    "ANTHROPIC_MODEL": "MiniMax-M2.7"
  },
  "theme": "light"
}`)
	if err := os.WriteFile(configPath, seed, 0o644); err != nil {
		t.Fatalf("failed to seed config: %v", err)
	}

	result := AttachClaude()
	if !result.Success {
		t.Fatalf("expected attach success, got: %s", result.Message)
	}

	raw, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatalf("failed to read config: %v", err)
	}

	var cfg map[string]interface{}
	if err := json.Unmarshal(raw, &cfg); err != nil {
		t.Fatalf("failed to parse config: %v", err)
	}

	envCfg, ok := cfg["env"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected env block, got %T", cfg["env"])
	}
	if _, exists := envCfg["ANTHROPIC_BASE_URL"]; exists {
		t.Fatalf("expected stale product ANTHROPIC_BASE_URL removed, got %#v", envCfg["ANTHROPIC_BASE_URL"])
	}
	if envCfg["ANTHROPIC_MODEL"] != "MiniMax-M2.7" {
		t.Fatalf("expected model preserved, got %#v", envCfg["ANTHROPIC_MODEL"])
	}
}

func TestIsAttachedClaudeReturnsFalseWhenBaseURLDriftsToDirectUpstream(t *testing.T) {
	tmpHome := t.TempDir()
	configPath := filepath.Join(tmpHome, ".claude", "settings.json")
	t.Setenv("HOME", tmpHome)

	if err := os.MkdirAll(filepath.Dir(configPath), 0o755); err != nil {
		t.Fatalf("failed to create config dir: %v", err)
	}

	seed := []byte(`{
  "memory": {
    "provider": "omnimemora",
    "endpoint": "http://127.0.0.1:18011"
  },
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic"
  }
}`)
	if err := os.WriteFile(configPath, seed, 0o644); err != nil {
		t.Fatalf("failed to seed config: %v", err)
	}

	if IsAttached(AgentClaude, 18011) {
		t.Fatalf("expected drifted direct base_url to be treated as detached")
	}
}

func TestIsAttachedClaudeAllowsAttachedStateWithoutExplicitBaseURL(t *testing.T) {
	tmpHome := t.TempDir()
	configPath := filepath.Join(tmpHome, ".claude", "settings.json")
	t.Setenv("HOME", tmpHome)

	if err := os.MkdirAll(filepath.Dir(configPath), 0o755); err != nil {
		t.Fatalf("failed to create config dir: %v", err)
	}

	seed := []byte(`{
  "memory": {
    "provider": "omnimemora",
    "endpoint": "http://127.0.0.1:18011"
  }
}`)
	if err := os.WriteFile(configPath, seed, 0o644); err != nil {
		t.Fatalf("failed to seed config: %v", err)
	}

	if !IsAttached(AgentClaude, 18011) {
		t.Fatalf("expected attached when memory points to omnimemora and no conflicting base_url exists")
	}
}
