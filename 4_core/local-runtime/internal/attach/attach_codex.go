// internal/attach/attach_codex.go - Codex Attachment Implementation
package attach

import (
	"fmt"
	"os"
	"regexp"
	"strings"
)

const (
	codexProviderBaseURL = "http://127.0.0.1:18011/v1"
	codexProviderName    = "omnimemora"
)

// AttachCodex attaches OmniMemora to Codex via the Responses-compatible model provider.
// This keeps Codex's LLM traffic on the product path instead of using MCP as the primary route.
func AttachCodex() *AttachResult {
	result := &AttachResult{Agent: AgentCodex, Success: false}

	configPath, err := GetConfigPath(AgentCodex)
	if err != nil {
		result.Message = "Failed to resolve Codex config path"
		return result
	}

	if err := EnsureConfigDir(AgentCodex); err != nil {
		result.Message = "Failed to create Codex config directory"
		return result
	}
	if err := BackupConfig(AgentCodex); err != nil {
		result.Message = "Failed to back up existing config"
		return result
	}

	content := ""
	if data, err := os.ReadFile(configPath); err == nil {
		content = string(data)
	}

	updated := upsertCodexProviderConfig(content, codexProviderBaseURL)
	if err := os.WriteFile(configPath, []byte(updated), 0644); err != nil {
		result.Message = "Failed to write config"
		return result
	}

	result.Success = true
	result.ConfigWriten = true
	result.Message = "Attached successfully"

	_ = RestartAgent(AgentCodex)

	return result
}

// DetachCodex removes OmniMemora provider and legacy MCP config from Codex config.
func DetachCodex() error {
	if restored, err := RestoreBackup(AgentCodex); err != nil {
		return err
	} else if restored {
		return nil
	}

	configPath, err := GetConfigPath(AgentCodex)
	if err != nil {
		return err
	}

	data, err := os.ReadFile(configPath)
	if err != nil {
		return err
	}

	updated := removeCodexProviderConfig(string(data))
	if updated == string(data) {
		return fmt.Errorf("config not found")
	}

	return os.WriteFile(configPath, []byte(updated), 0644)
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
