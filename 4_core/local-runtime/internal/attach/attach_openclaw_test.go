package attach

import (
	"encoding/json"
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
		if got := ProductAdapterOpenClawMCPEndpoint(); got != "http://127.0.0.1:18011/sse" {
			t.Fatalf("expected default OpenClaw mcp endpoint, got %s", got)
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
		if got := ProductAdapterOpenClawMCPEndpoint(); got != "http://127.0.0.1:18041/sse" {
			t.Fatalf("expected overridden OpenClaw mcp endpoint, got %s", got)
		}
		if got := ProductAdapterResponsesEndpoint(); got != "http://127.0.0.1:18041/v1" {
			t.Fatalf("expected overridden responses endpoint, got %s", got)
		}
	})
}

func TestAttachOpenClawInheritedMainUpdatesGlobalLayerOnly(t *testing.T) {
	tmpHome := t.TempDir()
	t.Setenv("HOME", tmpHome)
	t.Setenv("OMNIMEMORA_ADAPTER_PORT", "18041")
	installFakeOpenClawCLI(t, tmpHome)

	globalPath := filepath.Join(tmpHome, ".openclaw", "openclaw.json")
	agentModelsPath := filepath.Join(tmpHome, ".openclaw", "agents", "main", "agent", "models.json")

	originalGlobal := map[string]interface{}{
		"agents": map[string]interface{}{
			"defaults": map[string]interface{}{
				"model": map[string]interface{}{"primary": "minimax/MiniMax-M2.7"},
			},
			"list": []interface{}{
				map[string]interface{}{"id": "main", "model": "minimax/MiniMax-M2.7"},
			},
		},
		"models": map[string]interface{}{
			"providers": map[string]interface{}{
				"minimax": map[string]interface{}{
					"api":     "anthropic-messages",
					"baseUrl": "https://api.minimaxi.com/anthropic/v1",
				},
			},
		},
	}
	originalAgent := map[string]interface{}{
		"providers": map[string]interface{}{
			"openai-codex": map[string]interface{}{"baseUrl": "https://chatgpt.com/backend-api/codex"},
		},
	}
	writeJSONFile(t, globalPath, originalGlobal)
	writeJSONFile(t, agentModelsPath, originalAgent)

	result := AttachOpenClaw()
	if !result.Success {
		t.Fatalf("attach failed: %s", result.Message)
	}
	if !BackupExists(AgentOpenClaw) {
		t.Fatalf("expected backup to exist after attach")
	}

	updatedGlobal := readJSONFile(t, globalPath)
	updatedAgent := readJSONFile(t, agentModelsPath)

	if !hasOpenClawMCPAttachment(updatedGlobal, 18041) {
		t.Fatalf("expected global config to contain omnimemora MCP attachment")
	}
	globalMCP := (((updatedGlobal["mcp"].(map[string]interface{}))["servers"].(map[string]interface{}))["omnimemora"].(map[string]interface{}))["url"]
	if globalMCP != "http://127.0.0.1:18041/sse" {
		t.Fatalf("expected OpenClaw MCP attachment to use /sse, got %v", globalMCP)
	}

	globalProviders := openClawGlobalProviders(updatedGlobal)
	minimax, ok := asStringMap(globalProviders["minimax"])
	if !ok {
		t.Fatalf("expected minimax provider in global config")
	}
	if got := minimax["baseUrl"]; got != "http://127.0.0.1:18041/llm" {
		t.Fatalf("expected inherited provider to route via product ingress, got %v", got)
	}

	agentProviders := openClawAgentProviders(updatedAgent)
	if _, ok := agentProviders["minimax"]; ok {
		t.Fatalf("expected no new agent override for inherited provider")
	}

	if !isOpenClawAttached(18041) {
		t.Fatalf("expected OpenClaw attach detection to require both MCP and effective ingress")
	}

	if err := DetachOpenClaw(); err != nil {
		t.Fatalf("detach failed: %v", err)
	}
	assertJSONFileEquals(t, globalPath, originalGlobal)
	assertJSONFileEquals(t, agentModelsPath, originalAgent)
}

func TestAttachOpenClawAgentOverrideUpdatesAgentLayerOnly(t *testing.T) {
	tmpHome := t.TempDir()
	t.Setenv("HOME", tmpHome)
	t.Setenv("OMNIMEMORA_ADAPTER_PORT", "18041")
	installFakeOpenClawCLI(t, tmpHome)

	globalPath := filepath.Join(tmpHome, ".openclaw", "openclaw.json")
	agentModelsPath := filepath.Join(tmpHome, ".openclaw", "agents", "main", "agent", "models.json")

	originalGlobal := map[string]interface{}{
		"agents": map[string]interface{}{
			"defaults": map[string]interface{}{
				"model": map[string]interface{}{"primary": "minimax/MiniMax-M2.7"},
			},
			"list": []interface{}{
				map[string]interface{}{"id": "main", "model": "minimax/MiniMax-M2.7"},
			},
		},
		"models": map[string]interface{}{
			"providers": map[string]interface{}{
				"minimax": map[string]interface{}{
					"api":     "anthropic-messages",
					"baseUrl": "https://api.minimaxi.com/anthropic/v1",
				},
			},
		},
	}
	originalAgent := map[string]interface{}{
		"providers": map[string]interface{}{
			"minimax": map[string]interface{}{
				"api":     "anthropic-messages",
				"baseUrl": "https://override.example.test/anthropic",
			},
		},
	}
	writeJSONFile(t, globalPath, originalGlobal)
	writeJSONFile(t, agentModelsPath, originalAgent)

	result := AttachOpenClaw()
	if !result.Success {
		t.Fatalf("attach failed: %s", result.Message)
	}

	updatedGlobal := readJSONFile(t, globalPath)
	updatedAgent := readJSONFile(t, agentModelsPath)

	if !hasOpenClawMCPAttachment(updatedGlobal, 18041) {
		t.Fatalf("expected global config to contain omnimemora MCP attachment")
	}
	globalMCP := (((updatedGlobal["mcp"].(map[string]interface{}))["servers"].(map[string]interface{}))["omnimemora"].(map[string]interface{}))["url"]
	if globalMCP != "http://127.0.0.1:18041/sse" {
		t.Fatalf("expected OpenClaw MCP attachment to use /sse, got %v", globalMCP)
	}

	globalProviders := openClawGlobalProviders(updatedGlobal)
	globalMinimax, ok := asStringMap(globalProviders["minimax"])
	if !ok {
		t.Fatalf("expected minimax provider in global config")
	}
	if got := globalMinimax["baseUrl"]; got != "https://api.minimaxi.com/anthropic/v1" {
		t.Fatalf("expected global provider to remain unchanged, got %v", got)
	}

	agentProviders := openClawAgentProviders(updatedAgent)
	agentMinimax, ok := asStringMap(agentProviders["minimax"])
	if !ok {
		t.Fatalf("expected agent override to remain present")
	}
	if got := agentMinimax["baseUrl"]; got != "http://127.0.0.1:18041/llm" {
		t.Fatalf("expected agent override to route via product ingress, got %v", got)
	}

	if !isOpenClawAttached(18041) {
		t.Fatalf("expected OpenClaw attach detection to honor agent override layer")
	}

	if err := DetachOpenClaw(); err != nil {
		t.Fatalf("detach failed: %v", err)
	}
	assertJSONFileEquals(t, globalPath, originalGlobal)
	assertJSONFileEquals(t, agentModelsPath, originalAgent)
}

func TestIsAttachedOpenClawRequiresMCPAndEffectiveIngress(t *testing.T) {
	tmpHome := t.TempDir()
	t.Setenv("HOME", tmpHome)
	t.Setenv("OMNIMEMORA_ADAPTER_PORT", "18041")

	globalPath := filepath.Join(tmpHome, ".openclaw", "openclaw.json")
	agentModelsPath := filepath.Join(tmpHome, ".openclaw", "agents", "main", "agent", "models.json")

	writeJSONFile(t, globalPath, map[string]interface{}{
		"agents": map[string]interface{}{
			"defaults": map[string]interface{}{
				"model": map[string]interface{}{"primary": "minimax/MiniMax-M2.7"},
			},
			"list": []interface{}{
				map[string]interface{}{"id": "main", "model": "minimax/MiniMax-M2.7"},
			},
		},
		"models": map[string]interface{}{
			"providers": map[string]interface{}{
				"minimax": map[string]interface{}{
					"api":     "anthropic-messages",
					"baseUrl": "http://127.0.0.1:18041/llm",
				},
			},
		},
	})
	writeJSONFile(t, agentModelsPath, map[string]interface{}{"providers": map[string]interface{}{}})

	if IsAttached(AgentOpenClaw, 18041) {
		t.Fatalf("expected attach detection to fail without MCP")
	}

	globalCfg := readJSONFile(t, globalPath)
	ensureOpenClawMCPAttachment(globalCfg)
	writeJSONFile(t, globalPath, globalCfg)
	if !IsAttached(AgentOpenClaw, 18041) {
		t.Fatalf("expected attach detection to pass when MCP and effective ingress are both present")
	}

	globalCfg = readJSONFile(t, globalPath)
	globalProviders := openClawGlobalProviders(globalCfg)
	minimax, _ := asStringMap(globalProviders["minimax"])
	minimax["baseUrl"] = "https://api.minimaxi.com/anthropic/v1"
	globalProviders["minimax"] = minimax
	writeJSONFile(t, globalPath, globalCfg)
	if IsAttached(AgentOpenClaw, 18041) {
		t.Fatalf("expected attach detection to fail when effective ingress no longer targets product")
	}
}

func installFakeOpenClawCLI(t *testing.T, tmpHome string) {
	t.Helper()
	binDir := filepath.Join(tmpHome, "bin")
	if err := os.MkdirAll(binDir, 0o755); err != nil {
		t.Fatalf("mkdir fake bin: %v", err)
	}
	script := filepath.Join(binDir, "openclaw")
	if err := os.WriteFile(script, []byte("#!/bin/sh\nif [ \"$1\" = \"config\" ] && [ \"$2\" = \"validate\" ]; then exit 0; fi\nexit 0\n"), 0o755); err != nil {
		t.Fatalf("write fake openclaw: %v", err)
	}
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+os.Getenv("PATH"))
}

func writeJSONFile(t *testing.T, path string, value map[string]interface{}) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir %s: %v", path, err)
	}
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		t.Fatalf("marshal %s: %v", path, err)
	}
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

func readJSONFile(t *testing.T, path string) map[string]interface{} {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	var value map[string]interface{}
	if err := json.Unmarshal(data, &value); err != nil {
		t.Fatalf("unmarshal %s: %v", path, err)
	}
	return value
}

func assertJSONFileEquals(t *testing.T, path string, expected map[string]interface{}) {
	t.Helper()
	got := readJSONFile(t, path)
	gotJSON, err := json.Marshal(got)
	if err != nil {
		t.Fatalf("marshal got %s: %v", path, err)
	}
	wantJSON, err := json.Marshal(expected)
	if err != nil {
		t.Fatalf("marshal want %s: %v", path, err)
	}
	if string(gotJSON) != string(wantJSON) {
		t.Fatalf("unexpected JSON at %s\nwant=%s\ngot=%s", path, string(wantJSON), string(gotJSON))
	}
}
