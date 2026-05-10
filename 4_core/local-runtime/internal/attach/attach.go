// internal/attach/attach.go - Agent Attachment Implementation
// Handles writing configuration to agent config files and restarting agents
package attach

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
)

// RuntimeEndpoint returns the OmniMemora runtime endpoint URL
func RuntimeEndpoint(port int) string {
	return fmt.Sprintf("http://127.0.0.1:%d", port)
}

func ProductAdapterPort() int {
	raw := strings.TrimSpace(os.Getenv("OMNIMEMORA_ADAPTER_PORT"))
	if raw == "" {
		return 18011
	}
	parsed, err := strconv.Atoi(raw)
	if err != nil || parsed <= 0 {
		return 18011
	}
	return parsed
}

func ProductAdapterEndpoint() string {
	return RuntimeEndpoint(ProductAdapterPort())
}

func ProductAdapterMCPEndpoint() string {
	return fmt.Sprintf("%s/mcp", ProductAdapterEndpoint())
}

func ProductAdapterOpenClawMCPEndpoint() string {
	return fmt.Sprintf("%s/sse", ProductAdapterEndpoint())
}

func ProductAdapterResponsesEndpoint() string {
	return fmt.Sprintf("%s/v1", ProductAdapterEndpoint())
}

func ProductAdapterAnthropicEndpoint() string {
	return fmt.Sprintf("%s/llm", ProductAdapterEndpoint())
}

// ShimPythonExe returns the python executable to use for MCP shim.
// Tries common names; returns empty string if none found.
func ShimPythonExe() string {
	names := []string{"python", "python3", "py"}
	for _, name := range names {
		if path, err := exec.LookPath(name); err == nil {
			return path
		}
	}
	return ""
}

// GetConfigPath returns the config path for an agent
func GetConfigPath(agent AgentType) (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}

	switch agent {
	case AgentCodex:
		return filepath.Join(home, ".codex", "config.toml"), nil
	case AgentClaude:
		// Prefer ~/.claude/settings.json, fallback to ~/.claude.json
		settingsPath := filepath.Join(home, ".claude", "settings.json")
		if _, err := os.Stat(settingsPath); err == nil {
			return settingsPath, nil
		}
		return filepath.Join(home, ".claude.json"), nil
	case AgentCursor:
		if runtime.GOOS == "windows" {
			return filepath.Join(os.Getenv("APPDATA"), "Cursor", "config", "settings.json"), nil
		}
		return filepath.Join(home, ".cursor", "config", "settings.json"), nil
	case AgentOpenClaw:
		return filepath.Join(home, ".openclaw", "openclaw.json"), nil
	default:
		return "", fmt.Errorf("unknown agent type: %s", agent)
	}
}

// EnsureConfigDir ensures the config directory exists for an agent
func EnsureConfigDir(agent AgentType) error {
	path, err := GetConfigPath(agent)
	if err != nil {
		return err
	}

	dir := filepath.Dir(path)
	return os.MkdirAll(dir, 0755)
}

// ReadConfig reads a JSON config file
func ReadConfig(path string) (map[string]interface{}, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return make(map[string]interface{}), nil
		}
		return nil, err
	}

	var cfg map[string]interface{}
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}

// WriteConfig writes a JSON config file
func WriteConfig(path string, cfg map[string]interface{}) error {
	// Ensure directory exists
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}

	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal config: %w", err)
	}

	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("failed to write config: %w", err)
	}

	return nil
}

// RestartAgent prompts user to manually restart an agent
// No longer force-kills processes as that can cause data loss
func RestartAgent(agent AgentType) error {
	agentName := GetAgentDisplayName(agent)
	fmt.Printf("\n  ⚠ Please manually restart %s to pick up the new configuration.\n", agentName)
	fmt.Printf("  For CLI tools, simply restart your terminal or re-run the command.\n")
	fmt.Printf("  For IDE extensions (Claude Code, Cursor), restart the IDE.\n")
	return nil
}

// DetachAgent removes OmniMemora configuration from an agent
func DetachAgent(agent AgentType, port int) error {
	if restored, err := RestoreBackup(agent); err != nil {
		return err
	} else if restored {
		return nil
	}

	if agent == AgentCodex {
		return DetachCodex()
	}
	if agent == AgentOpenClaw {
		return DetachOpenClaw()
	}

	path, err := GetConfigPath(agent)
	if err != nil {
		return err
	}

	// Read existing config
	cfg, err := ReadConfig(path)
	if err != nil {
		return err
	}

	// Remove omnimemora/memory section based on agent type
	modified := false

	switch agent {
	case AgentClaude:
		if mem, ok := cfg["memory"]; ok {
			if memMap, ok := mem.(map[string]interface{}); ok {
				if provider, ok := memMap["provider"]; ok && provider == "omnimemora" {
					delete(memMap, "provider")
					delete(memMap, "endpoint")
					if len(memMap) == 0 {
						delete(cfg, "memory")
					}
					modified = true
				}
			}
		}
	case AgentCursor:
		// Cursor may have different config structure
		if mem, ok := cfg["memory"]; ok {
			if memMap, ok := mem.(map[string]interface{}); ok {
				if provider, ok := memMap["provider"]; ok && provider == "omnimemora" {
					delete(memMap, "provider")
					delete(memMap, "endpoint")
					modified = true
				}
			}
		}
	case AgentOpenClaw:
		if mcp, ok := cfg["mcp"].(map[string]interface{}); ok {
			if servers, ok := mcp["servers"].(map[string]interface{}); ok {
				if _, ok := servers["omnimemora"]; ok {
					delete(servers, "omnimemora")
					modified = true
				}
			}
		}
		if _, ok := cfg["omnimemora"]; ok {
			delete(cfg, "omnimemora") // legacy cleanup
			modified = true
		}
	}

	if !modified {
		return nil // Nothing to detach
	}

	// Write back
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(path, data, 0644)
}

// IsAttached checks if OmniMemora is already attached to an agent
func IsAttached(agent AgentType, port int) bool {
	path, err := GetConfigPath(agent)
	if err != nil {
		return false
	}

	// Codex uses TOML config — check raw content for MCP block
	if agent == AgentCodex {
		if codexManagedProfileExists() {
			return true
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return false
		}
		return codexConfigContainsOmniMemora(string(data))
	}

	cfg, err := ReadConfig(path)
	if err != nil {
		return false
	}

	switch agent {
	case AgentClaude:
		if mem, ok := cfg["memory"]; ok {
			if memMap, ok := mem.(map[string]interface{}); ok {
				if provider, ok := memMap["provider"]; ok && provider == "omnimemora" {
					// Drift guard: third-party edits may repoint Claude LLM traffic directly
					// upstream while memory still says "omnimemora". Treat that as detached
					// so UI status can surface "attach no longer effective".
					if envCfg, ok := cfg["env"].(map[string]interface{}); ok {
						if baseURL, ok := envCfg["ANTHROPIC_BASE_URL"].(string); ok && strings.TrimSpace(baseURL) != "" && !isProductAdapterBaseURL(baseURL) {
							return false
						}
					}
					return true
				}
			}
		}
	case AgentCursor:
		if mem, ok := cfg["memory"]; ok {
			if memMap, ok := mem.(map[string]interface{}); ok {
				if provider, ok := memMap["provider"]; ok && provider == "omnimemora" {
					return true
				}
			}
		}
	case AgentOpenClaw:
		return isOpenClawAttached(port)
	}

	return false
}
