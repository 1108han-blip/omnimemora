// internal/attach/attach_claude.go - Claude Code Attachment Implementation
package attach

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// AttachClaude attaches OmniMemora to Claude Code
func AttachClaude() *AttachResult {
	result := &AttachResult{Agent: AgentClaude, Success: false}

	// Use GetConfigPath to get the correct Claude config path
	configPath, err := GetConfigPath(AgentClaude)
	if err != nil {
		result.Message = "Failed to get config path: " + err.Error()
		return result
	}

	claudeDir := filepath.Dir(configPath)

	// Ensure directory exists
	if err := os.MkdirAll(claudeDir, 0755); err != nil {
		result.Message = "Failed to create Claude config directory"
		return result
	}
	if err := BackupConfig(AgentClaude); err != nil {
		result.Message = "Failed to back up Claude config"
		return result
	}

	// Read existing config or create new
	var cfg map[string]interface{}
	if data, err := os.ReadFile(configPath); err == nil {
		if err := json.Unmarshal(data, &cfg); err != nil {
			cfg = make(map[string]interface{})
		}
	} else {
		cfg = make(map[string]interface{})
	}

	// Add/Update memory section with omnimemora provider
	// All MCP clients connect to Python Adapter at 18011, not Go Runtime at 8765
	cfg["memory"] = map[string]interface{}{
		"provider":         "omnimemora",
		"endpoint":         ProductAdapterEndpoint(),
		"assemble_context": true,
		"context_strategy": "auto",
		"context_mode":     "balanced",
	}

	// Claude's actual LLM traffic follows ANTHROPIC_BASE_URL, not the memory block.
	// Keep existing auth/model env values intact, but route the API hop through OmniMemora.
	envCfg, _ := cfg["env"].(map[string]interface{})
	if envCfg == nil {
		envCfg = make(map[string]interface{})
	}
	envCfg["ANTHROPIC_BASE_URL"] = ProductAdapterAnthropicEndpoint()
	cfg["env"] = envCfg

	// Write back
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		result.Message = "Failed to marshal config"
		return result
	}

	if err := os.WriteFile(configPath, data, 0644); err != nil {
		result.Message = "Failed to write config"
		return result
	}

	result.Success = true
	result.ConfigWriten = true
	result.Message = "Attached successfully"

	// Note: Restart is a best-effort operation
	_ = RestartAgent(AgentClaude)

	return result
}

// DetachClaude removes OmniMemora from Claude Code config
func DetachClaude() error {
	if restored, err := RestoreBackup(AgentClaude); err != nil {
		return err
	} else if restored {
		return nil
	}

	configPath, err := GetConfigPath(AgentClaude)
	if err != nil {
		return err
	}

	// Read existing config
	var cfg map[string]interface{}
	if data, err := os.ReadFile(configPath); err == nil {
		if err := json.Unmarshal(data, &cfg); err == nil {
			// Remove memory section if it points to omnimemora
			if mem, ok := cfg["memory"]; ok {
				if memMap, ok := mem.(map[string]interface{}); ok {
					if provider, ok := memMap["provider"]; ok && provider == "omnimemora" {
						delete(cfg, "memory")

						if envCfg, ok := cfg["env"].(map[string]interface{}); ok {
							if baseURL, ok := envCfg["ANTHROPIC_BASE_URL"]; ok && baseURL == ProductAdapterAnthropicEndpoint() {
								delete(envCfg, "ANTHROPIC_BASE_URL")
							}
							if len(envCfg) == 0 {
								delete(cfg, "env")
							}
						}

						data, err := json.MarshalIndent(cfg, "", "  ")
						if err != nil {
							return err
						}
						return os.WriteFile(configPath, data, 0644)
					}
				}
			}
		}
	}

	return fmt.Errorf("config not found")
}
