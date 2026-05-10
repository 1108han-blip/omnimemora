package attach

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestUpsertCodexProviderConfigSetsResponsesProvider(t *testing.T) {
	updated := upsertCodexProviderConfig(`model = "gpt-5.4"

[mcp_servers.omnimemora]
command = "python"
`, ProductAdapterResponsesEndpoint())

	if !strings.Contains(updated, `model_provider = "omnimemora"`) {
		t.Fatalf("expected model_provider to be set to omnimemora, got:\n%s", updated)
	}
	if !strings.Contains(updated, `[model_providers.omnimemora]`) {
		t.Fatalf("expected omnimemora provider block, got:\n%s", updated)
	}
	if !strings.Contains(updated, `wire_api = "responses"`) {
		t.Fatalf("expected responses wire API, got:\n%s", updated)
	}
	if strings.Contains(updated, `env_key = "OMNIMEMORA_OPENAI_API_KEY"`) {
		t.Fatalf("expected no product-scoped env key requirement, got:\n%s", updated)
	}
	if !strings.Contains(updated, `http_headers = { "X-OmniMemora-Agent" = "codex_cli" }`) {
		t.Fatalf("expected codex agent attribution header, got:\n%s", updated)
	}
	if !strings.Contains(updated, `env_http_headers = { "X-Provider-Base-URL" = "OMNIMEMORA_CODEX_UPSTREAM_BASE_URL", "Authorization" = "OMNIMEMORA_CODEX_AUTHORIZATION" }`) {
		t.Fatalf("expected env_http_headers bridge, got:\n%s", updated)
	}
	if strings.Contains(updated, `[mcp_servers.omnimemora]`) {
		t.Fatalf("expected legacy mcp block to be removed, got:\n%s", updated)
	}
}

func TestRemoveCodexProviderConfigRemovesProviderSpecificEntries(t *testing.T) {
	content := `model_provider = "omnimemora"
model = "gpt-5.4"

[model_providers.omnimemora]
name = "OmniMemora"
base_url = "http://127.0.0.1:18011/v1"
wire_api = "responses"
`

	updated := removeCodexProviderConfig(content)

	if strings.Contains(updated, `model_provider = "omnimemora"`) {
		t.Fatalf("expected model_provider line removed, got:\n%s", updated)
	}
	if strings.Contains(updated, `[model_providers.omnimemora]`) {
		t.Fatalf("expected provider block removed, got:\n%s", updated)
	}
	if !strings.Contains(updated, `model = "gpt-5.4"`) {
		t.Fatalf("expected unrelated config to remain, got:\n%s", updated)
	}
}

func TestAttachThenDetachCodexUsesManagedProfileAndPreservesOriginalConfig(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("HOME", tmpDir)

	configDir := filepath.Join(tmpDir, ".codex")
	if err := os.MkdirAll(configDir, 0755); err != nil {
		t.Fatalf("mkdir failed: %v", err)
	}

	original := "model_provider = \"openai\"\nmodel = \"gpt-5.4\"\n"
	configPath := filepath.Join(configDir, "config.toml")
	if err := os.WriteFile(configPath, []byte(original), 0644); err != nil {
		t.Fatalf("write original config failed: %v", err)
	}

	result := AttachCodex()
	if !result.Success {
		t.Fatalf("attach failed: %s", result.Message)
	}

	afterAttach, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatalf("read config after attach failed: %v", err)
	}
	if string(afterAttach) != original {
		t.Fatalf("expected official Codex config to remain unchanged, got:\n%s", string(afterAttach))
	}
	if BackupExists(AgentCodex) {
		t.Fatalf("expected no backup for managed-profile attach")
	}

	managedConfig, err := codexManagedConfigPath()
	if err != nil {
		t.Fatalf("managed config path failed: %v", err)
	}
	managedRaw, err := os.ReadFile(managedConfig)
	if err != nil {
		t.Fatalf("expected managed Codex config to be written: %v", err)
	}
	if !strings.Contains(string(managedRaw), `model_provider = "omnimemora"`) {
		t.Fatalf("expected managed config to contain OmniMemora provider, got:\n%s", string(managedRaw))
	}
	if strings.Contains(managedConfig, filepath.Join(tmpDir, ".codex", "config.toml")) {
		t.Fatalf("managed config must not point at official Codex config: %s", managedConfig)
	}

	launcherPath, err := codexManagedLauncherPath()
	if err != nil {
		t.Fatalf("managed launcher path failed: %v", err)
	}
	launcherRaw, err := os.ReadFile(launcherPath)
	if err != nil {
		t.Fatalf("expected managed Codex launcher to be written: %v", err)
	}
	if !strings.Contains(string(launcherRaw), "exec codex") {
		t.Fatalf("expected launcher to exec codex, got:\n%s", string(launcherRaw))
	}
	markerPath, err := codexManagedMarkerPath()
	if err != nil {
		t.Fatalf("managed marker path failed: %v", err)
	}
	markerRaw, err := os.ReadFile(markerPath)
	if err != nil {
		t.Fatalf("expected managed marker to be written: %v", err)
	}
	if !strings.Contains(string(markerRaw), "launcher=") {
		t.Fatalf("expected marker to include launcher path, got:\n%s", string(markerRaw))
	}

	if err := DetachCodex(); err != nil {
		t.Fatalf("detach failed: %v", err)
	}

	restored, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatalf("read restored config failed: %v", err)
	}
	if string(restored) != original {
		t.Fatalf("expected original config restored, got:\n%s", string(restored))
	}
	if BackupExists(AgentCodex) {
		t.Fatalf("expected backup to be removed after restore")
	}
	if codexManagedProfileExists() {
		t.Fatalf("expected managed profile marker to be removed after detach")
	}
}

func TestIsAttachedCodexRecognizesManagedProfile(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("HOME", tmpDir)

	if err := writeManagedCodexProfile(`model = "gpt-5.4"`+"\n", ProductAdapterResponsesEndpoint()); err != nil {
		t.Fatalf("write managed profile failed: %v", err)
	}

	if !IsAttached(AgentCodex, 8765) {
		t.Fatalf("expected managed Codex profile to count as attached")
	}
}

func TestIsAttachedCodexStillRecognizesLegacyProviderConfig(t *testing.T) {
	tmpDir := t.TempDir()
	t.Setenv("HOME", tmpDir)

	configDir := filepath.Join(tmpDir, ".codex")
	if err := os.MkdirAll(configDir, 0755); err != nil {
		t.Fatalf("mkdir failed: %v", err)
	}

	configPath := filepath.Join(configDir, "config.toml")
	content := `model_provider = "omnimemora"
model = "gpt-5.4"

[model_providers.omnimemora]
name = "OmniMemora"
base_url = "http://127.0.0.1:18011/v1"
wire_api = "responses"
`
	if err := os.WriteFile(configPath, []byte(content), 0644); err != nil {
		t.Fatalf("write config failed: %v", err)
	}

	if !IsAttached(AgentCodex, 8765) {
		t.Fatalf("expected codex provider config to count as attached")
	}
}
