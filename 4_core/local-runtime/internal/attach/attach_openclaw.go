// internal/attach/attach_openclaw.go - OpenClaw Attachment Implementation
package attach

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// AttachOpenClaw attaches OmniMemora to OpenClaw
func AttachOpenClaw() *AttachResult {
	result := &AttachResult{Agent: AgentOpenClaw, Success: false}

	configPath, err := GetConfigPath(AgentOpenClaw)
	if err != nil {
		result.Message = "Failed to resolve OpenClaw config path"
		return result
	}

	if err := EnsureConfigDir(AgentOpenClaw); err != nil {
		result.Message = "Failed to create OpenClaw config directory"
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

	// Remove legacy non-schema key if present.
	// OpenClaw schema rejects unknown top-level keys like "omnimemora".
	delete(cfg, "omnimemora")

	// Schema-driven attachment: register OmniMemora as an MCP server endpoint.
	mcp, ok := cfg["mcp"].(map[string]interface{})
	if !ok || mcp == nil {
		mcp = make(map[string]interface{})
	}
	servers, ok := mcp["servers"].(map[string]interface{})
	if !ok || servers == nil {
		servers = make(map[string]interface{})
	}
	// OmniMemora Python Adapter (port 18011) — full control plane with token savings
	servers["omnimemora"] = map[string]interface{}{
		"url": "http://127.0.0.1:18011",
	}
	mcp["servers"] = servers
	cfg["mcp"] = mcp

	// Step 1: Write config
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		result.Message = "Failed to marshal config"
		return result
	}

	if err := os.WriteFile(configPath, data, 0644); err != nil {
		result.Message = "Failed to write config"
		return result
	}
	result.ConfigWriten = true

	// Step 2: Read back and verify mcp.servers.omnimemora.url exists
	readBack, err := os.ReadFile(configPath)
	if err != nil {
		result.Message = "Config written but failed to read back for verification"
		return result
	}

	var verifyCfg map[string]interface{}
	if err := json.Unmarshal(readBack, &verifyCfg); err != nil {
		result.Message = "Config written but failed to parse written config"
		return result
	}

	mcpVerify, ok := verifyCfg["mcp"].(map[string]interface{})
	if !ok {
		result.Message = "Config written but mcp section missing"
		return result
	}
	serversVerify, ok := mcpVerify["servers"].(map[string]interface{})
	if !ok {
		result.Message = "Config written but mcp.servers missing"
		return result
	}
	omniVerify, ok := serversVerify["omnimemora"].(map[string]interface{})
	if !ok {
		result.Message = "Config written but mcp.servers.omnimemora missing"
		return result
	}
	urlVerify, ok := omniVerify["url"].(string)
	if !ok || urlVerify == "" {
		result.Message = "Config written but mcp.servers.omnimemora.url missing or empty"
		return result
	}

	// Step 3: Run openclaw config validate
	validateCmd := exec.Command("openclaw", "config", "validate")
	output, err := validateCmd.CombinedOutput()
	if err != nil {
		result.Message = fmt.Sprintf("Config written and verified, but openclaw config validate failed: %s", strings.TrimSpace(string(output)))
		return result
	}

	result.Success = true
	result.Message = "Attached successfully"

	// Note: Restart is a best-effort operation
	_ = RestartAgent(AgentOpenClaw)

	return result
}

// DetachOpenClaw removes OmniMemora from OpenClaw config
func DetachOpenClaw() error {
	configPath, err := GetConfigPath(AgentOpenClaw)
	if err != nil {
		return err
	}

	// Read existing config
	var cfg map[string]interface{}
	if data, err := os.ReadFile(configPath); err == nil {
		if err := json.Unmarshal(data, &cfg); err == nil {
			modified := false

			// Remove legacy invalid key if present
			if _, ok := cfg["omnimemora"]; ok {
				delete(cfg, "omnimemora")
				modified = true
			}

			// Remove MCP attachment entry
			if mcp, ok := cfg["mcp"].(map[string]interface{}); ok {
				if servers, ok := mcp["servers"].(map[string]interface{}); ok {
					if _, ok := servers["omnimemora"]; ok {
						delete(servers, "omnimemora")
						modified = true
					}
					if len(servers) == 0 {
						delete(mcp, "servers")
					} else {
						mcp["servers"] = servers
					}
				}
				if len(mcp) == 0 {
					delete(cfg, "mcp")
				} else {
					cfg["mcp"] = mcp
				}
			}

			if modified {
				data, err := json.MarshalIndent(cfg, "", "  ")
				if err != nil {
					return err
				}
				return os.WriteFile(configPath, data, 0644)
			}
		}
	}

	return fmt.Errorf("config not found")
}
