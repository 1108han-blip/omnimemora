// internal/attach/attach_codex.go - Codex Attachment Implementation
package attach

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// AttachCodex attaches OmniMemora to Codex via MCP shim.
// Codex uses a TOML config at ~/.codex/config.toml.
// The MCP shim (tools/mcp_omnimemora.py) proxies stdio JSON-RPC to adapter :18011.
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

	// Detect python executable for the shim
	pyExe := ShimPythonExe()
	if pyExe == "" {
		result.Message = "Python executable not found in PATH — cannot launch MCP shim"
		return result
	}

	// Resolve absolute path to the shim relative to the omnimemora binary
	shimPath := resolveShimPath()
	if shimPath == "" {
		result.Message = "Cannot resolve path to tools/mcp_omnimemora.py — run from project root"
		return result
	}

	// Read existing TOML content
	content := ""
	if data, err := os.ReadFile(configPath); err == nil {
		content = string(data)
	}

	updated := upsertCodexMCPBlock(content, pyExe, shimPath)

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

// DetachCodex removes OmniMemora MCP server from Codex config
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

	updated := removeCodexMCPBlock(string(data))
	if updated == string(data) {
		return fmt.Errorf("config not found")
	}

	return os.WriteFile(configPath, []byte(updated), 0644)
}

// resolveShimPath returns an absolute path to tools/mcp_omnimemora.py.
// It is computed relative to the directory containing the running omnimemora binary.
func resolveShimPath() string {
	execPath, err := os.Executable()
	if err != nil {
		return ""
	}
	// omnimemora.exe lives in tools/; shim is in tools/mcp_omnimemora.py
	toolsDir := filepath.Dir(execPath)
	shimPath := filepath.Join(toolsDir, "mcp_omnimemora.py")
	if _, err := os.Stat(shimPath); err == nil {
		return shimPath
	}
	// Fallback: try relative to current working directory
	cwd, _ := os.Getwd()
	fallback := filepath.Join(cwd, "tools", "mcp_omnimemora.py")
	if _, err := os.Stat(fallback); err == nil {
		return fallback
	}
	return shimPath
}

// upsertCodexMCPBlock replaces or inserts the [mcp.servers.omnimemora] TOML block.
// Codex MCP config format: mcp_servers.omnimemora = { command = "python", args = [...] }
func upsertCodexMCPBlock(content string, pyExe string, shimPath string) string {
	trimmed := strings.TrimRight(content, "\r\n\t ")
	if trimmed != "" {
		trimmed += "\n\n"
	}

	block := fmt.Sprintf(`[mcp_servers.omnimemora]
command = "%s"
args = ["%s"]
env = { OMNIMEMORA_ADAPTER_URL = "http://127.0.0.1:18011" }
`, pyExe, strings.ReplaceAll(shimPath, "\\", "\\\\"))

	without := removeCodexMCPBlock(trimmed)
	without = strings.TrimRight(without, "\r\n\t ")
	if without != "" {
		without += "\n\n"
	}
	return without + block
}

// removeCodexMCPBlock removes the [mcp_servers.omnimemora] section from TOML content.
// Handles both TOML section and legacy [omnimemora] block.
func removeCodexMCPBlock(content string) string {
	// Remove [mcp_servers.omnimemora] section
	lines := strings.Split(content, "\n")
	out := make([]string, 0, len(lines))
	inBlock := false

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		// Start of a new section
		if strings.HasPrefix(trimmed, "[") && strings.HasSuffix(trimmed, "]") {
			if trimmed == "[mcp_servers.omnimemora]" || trimmed == "[omnimemora]" {
				inBlock = true
				continue
			}
			inBlock = false
		}
		if !inBlock {
			out = append(out, line)
		}
	}

	return strings.TrimRight(strings.Join(out, "\n"), "\n") + "\n"
}
