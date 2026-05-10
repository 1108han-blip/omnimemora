// internal/attach/attach_codex.go - Codex Attachment Implementation
package attach

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

const (
	codexProviderName = "omnimemora"
)

// AttachCodex prepares an OmniMemora-managed Codex profile without changing
// Codex's official ~/.codex/config.toml. The managed profile is the product
// carrier; the user's primary Codex UI/config remains the clean fallback.
func AttachCodex() *AttachResult {
	result := &AttachResult{Agent: AgentCodex, Success: false}

	configPath, err := GetConfigPath(AgentCodex)
	if err != nil {
		result.Message = "Failed to resolve Codex config path"
		return result
	}

	content := ""
	if data, err := os.ReadFile(configPath); err == nil {
		content = string(data)
	}

	if err := writeManagedCodexProfile(content, ProductAdapterResponsesEndpoint()); err != nil {
		result.Message = "Failed to prepare managed Codex profile"
		return result
	}

	result.Success = true
	result.ConfigWriten = true
	result.Message = "Managed Codex profile prepared; official Codex config was not modified"

	return result
}

// DetachCodex removes the managed Codex profile. If a legacy Codex provider
// attach is present, it is restored/cleaned for backwards compatibility.
func DetachCodex() error {
	managedRemoved, managedErr := removeManagedCodexProfile()
	if managedErr != nil {
		return managedErr
	}

	configPath, err := GetConfigPath(AgentCodex)
	if err != nil {
		return err
	}

	data, err := os.ReadFile(configPath)
	if err != nil {
		if os.IsNotExist(err) && managedRemoved {
			return nil
		}
		return err
	}

	if !codexConfigContainsOmniMemora(string(data)) {
		if managedRemoved {
			return nil
		}
		return fmt.Errorf("config not found")
	}

	if restored, err := RestoreBackup(AgentCodex); err != nil {
		return err
	} else if restored {
		return nil
	}

	updated := removeCodexProviderConfig(string(data))
	if updated == string(data) {
		return fmt.Errorf("config not found")
	}

	return os.WriteFile(configPath, []byte(updated), 0644)
}

func codexManagedDir() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ".omnimemora", "managed", "codex"), nil
}

func codexManagedConfigPath() (string, error) {
	dir, err := codexManagedDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "home", ".codex", "config.toml"), nil
}

func codexManagedMarkerPath() (string, error) {
	dir, err := codexManagedDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, ".omnimemora.attach.marker"), nil
}

func codexManagedLauncherPath() (string, error) {
	dir, err := codexManagedDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "bin", "codex-omnimemora"), nil
}

func codexManagedHomeDir() (string, error) {
	dir, err := codexManagedDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, "home"), nil
}

func writeManagedCodexProfile(originalContent string, baseURL string) error {
	configPath, err := codexManagedConfigPath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(configPath), 0755); err != nil {
		return err
	}

	managedContent := upsertCodexProviderConfig(originalContent, baseURL)
	if err := os.WriteFile(configPath, []byte(managedContent), 0644); err != nil {
		return err
	}

	if err := linkManagedCodexAuthStore(); err != nil {
		return err
	}
	if err := writeManagedCodexLauncher(); err != nil {
		return err
	}

	markerPath, err := codexManagedMarkerPath()
	if err != nil {
		return err
	}
	launcherPath, err := codexManagedLauncherPath()
	if err != nil {
		return err
	}
	marker := fmt.Sprintf("managed_profile_ready\nlauncher=%s\n", launcherPath)
	return os.WriteFile(markerPath, []byte(marker), 0644)
}

func linkManagedCodexAuthStore() error {
	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}
	source := filepath.Join(home, ".codex", "auth.json")
	if _, err := os.Stat(source); os.IsNotExist(err) {
		return nil
	}
	managedHome, err := codexManagedHomeDir()
	if err != nil {
		return err
	}
	target := filepath.Join(managedHome, ".codex", "auth.json")
	if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
		return err
	}
	if existing, err := os.Lstat(target); err == nil {
		if existing.Mode()&os.ModeSymlink == 0 {
			return nil
		}
		if err := os.Remove(target); err != nil {
			return err
		}
	}
	return os.Symlink(source, target)
}

func writeManagedCodexLauncher() error {
	managedHome, err := codexManagedHomeDir()
	if err != nil {
		return err
	}
	launcherPath, err := codexManagedLauncherPath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(launcherPath), 0755); err != nil {
		return err
	}
	script := fmt.Sprintf(`#!/bin/sh
set -eu
export HOME=%q
exec codex "$@"
`, managedHome)
	return os.WriteFile(launcherPath, []byte(script), 0755)
}

func removeManagedCodexProfile() (bool, error) {
	dir, err := codexManagedDir()
	if err != nil {
		return false, err
	}
	if _, err := os.Stat(dir); os.IsNotExist(err) {
		return false, nil
	}
	if err := os.RemoveAll(dir); err != nil {
		return false, err
	}
	return true, nil
}

func codexManagedProfileExists() bool {
	markerPath, err := codexManagedMarkerPath()
	if err != nil {
		return false
	}
	if _, err := os.Stat(markerPath); err == nil {
		return true
	}
	return false
}

func codexConfigContainsOmniMemora(content string) bool {
	return strings.Contains(content, `model_provider = "omnimemora"`) ||
		strings.Contains(content, "[model_providers.omnimemora]") ||
		strings.Contains(content, "[mcp_servers.omnimemora]")
}

func upsertCodexProviderConfig(content string, baseURL string) string {
	updated := removeCodexProviderConfig(content)
	updated = setTopLevelTomlString(updated, "model_provider", codexProviderName)

	providerBlock := fmt.Sprintf(`[model_providers.%s]
name = "OmniMemora"
base_url = "%s"
wire_api = "responses"
http_headers = { "X-OmniMemora-Agent" = "codex_cli" }
env_http_headers = { "X-Provider-Base-URL" = "OMNIMEMORA_CODEX_UPSTREAM_BASE_URL", "Authorization" = "OMNIMEMORA_CODEX_AUTHORIZATION" }
`, codexProviderName, baseURL)

	trimmed := strings.TrimRight(updated, "\r\n\t ")
	if trimmed != "" {
		trimmed += "\n\n"
	}
	return trimmed + providerBlock
}

func removeCodexProviderConfig(content string) string {
	updated := removeTomlSections(content,
		"[model_providers.omnimemora]",
		"[mcp_servers.omnimemora]",
		"[omnimemora]",
	)
	updated = removeTopLevelTomlString(updated, "model_provider", codexProviderName)
	return normalizeTomlTrailingNewline(updated)
}

func setTopLevelTomlString(content string, key string, value string) string {
	pattern := regexp.MustCompile(fmt.Sprintf(`(?m)^%s\s*=\s*"[^"]*"\s*$`, regexp.QuoteMeta(key)))
	line := fmt.Sprintf(`%s = "%s"`, key, value)
	if pattern.MatchString(content) {
		return pattern.ReplaceAllString(content, line)
	}

	trimmed := strings.TrimLeft(content, "\r\n")
	if trimmed == "" {
		return line + "\n"
	}
	return line + "\n" + trimmed
}

func removeTopLevelTomlString(content string, key string, value string) string {
	pattern := regexp.MustCompile(
		fmt.Sprintf(`(?m)^%s\s*=\s*"%s"\s*(\r?\n)?`, regexp.QuoteMeta(key), regexp.QuoteMeta(value)),
	)
	return pattern.ReplaceAllString(content, "")
}

func removeTomlSections(content string, sectionNames ...string) string {
	targets := make(map[string]struct{}, len(sectionNames))
	for _, name := range sectionNames {
		targets[name] = struct{}{}
	}

	lines := strings.Split(content, "\n")
	out := make([]string, 0, len(lines))
	inBlock := false

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if strings.HasPrefix(trimmed, "[") && strings.HasSuffix(trimmed, "]") {
			_, removeThis := targets[trimmed]
			if removeThis {
				inBlock = true
				continue
			}
			inBlock = false
		}
		if !inBlock {
			out = append(out, line)
		}
	}

	return strings.Join(out, "\n")
}

func normalizeTomlTrailingNewline(content string) string {
	return strings.TrimRight(content, "\n") + "\n"
}
