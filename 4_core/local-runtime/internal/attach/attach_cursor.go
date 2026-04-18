// internal/attach/attach_cursor.go - Cursor Attachment Implementation
package attach

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
)

// AttachCursor attaches OmniMemora to Cursor
func AttachCursor() *AttachResult {
	result := &AttachResult{Agent: AgentCursor, Success: false}

	var cursorDir string
	if runtime.GOOS == "windows" {
		cursorDir = filepath.Join(os.Getenv("APPDATA"), "Cursor")
	} else {
		home, err := os.UserHomeDir()
		if err != nil {
			result.Message = "Failed to get home directory"
			return result
		}
		cursorDir = filepath.Join(home, ".cursor")
	}

	configDir := filepath.Join(cursorDir, "config")
	configPath := filepath.Join(configDir, "settings.json")

	// Ensure directory exists
	if err := os.MkdirAll(configDir, 0755); err != nil {
		result.Message = "Failed to create Cursor config directory"
		return result
	}
	if err := BackupConfig(AgentCursor); err != nil {
		result.Message = "Failed to back up Cursor config"
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
		"endpoint":         "http://127.0.0.1:18011",
		"assemble_context": true,
		"context_strategy": "auto",
		"context_mode":     "balanced",
	}

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
	_ = RestartAgent(AgentCursor)

	return result
}

// DetachCursor removes OmniMemora from Cursor config
func DetachCursor() error {
	if restored, err := RestoreBackup(AgentCursor); err != nil {
		return err
	} else if restored {
		return nil
	}

	var cursorDir string
	if runtime.GOOS == "windows" {
		cursorDir = filepath.Join(os.Getenv("APPDATA"), "Cursor")
	} else {
		home, err := os.UserHomeDir()
		if err != nil {
			return err
		}
		cursorDir = filepath.Join(home, ".cursor")
	}

	configPath := filepath.Join(cursorDir, "config", "settings.json")

	// Read existing config
	var cfg map[string]interface{}
	if data, err := os.ReadFile(configPath); err == nil {
		if err := json.Unmarshal(data, &cfg); err == nil {
			// Remove memory section if it points to omnimemora
			if mem, ok := cfg["memory"]; ok {
				if memMap, ok := mem.(map[string]interface{}); ok {
					if provider, ok := memMap["provider"]; ok && provider == "omnimemora" {
						delete(cfg, "memory")

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
