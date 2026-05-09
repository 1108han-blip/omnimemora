// internal/attach/detect.go - Agent Detection for OmniMemora
// Detects installed AI agents: Codex, Claude Code, Cursor, OpenClaw
package attach

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

// AgentType represents a detected AI agent
type AgentType string

const (
	AgentCodex    AgentType = "codex"
	AgentClaude   AgentType = "claude"
	AgentCursor   AgentType = "cursor"
	AgentOpenClaw AgentType = "openclaw"
)

// AgentInfo contains information about a detected agent
type AgentInfo struct {
	Type       AgentType
	Name       string
	ConfigPath string
	Installed  bool
	Running    bool
}

// DetectAgents scans the system for installed AI agents
func DetectAgents() []AgentInfo {
	var agents []AgentInfo

	// Detect each agent type
	agents = append(agents, detectCodex())
	agents = append(agents, detectClaude())
	agents = append(agents, detectCursor())
	agents = append(agents, detectOpenClaw())

	// Filter to only installed agents
	var installed []AgentInfo
	for _, a := range agents {
		if a.Installed {
			installed = append(installed, a)
		}
	}

	return installed
}

// detectCodex detects Codex agent
func detectCodex() AgentInfo {
	info := AgentInfo{Type: AgentCodex, Name: "Codex", Installed: false}
	info.Running = isProcessRunning("codex")

	home, err := os.UserHomeDir()
	if err != nil {
		return info
	}

	// Check for .codex directory (OpenAI Codex / OpenAI CLI)
	codexPath := filepath.Join(home, ".codex")
	if _, err := os.Stat(codexPath); err == nil {
		info.Installed = true
		info.ConfigPath = filepath.Join(codexPath, "config.toml")
	}

	// Also check for codex CLI in PATH
	if isCommandInPath("codex") {
		info.Installed = true
	}

	return info
}

// detectClaude detects Claude Code agent
func detectClaude() AgentInfo {
	info := AgentInfo{Type: AgentClaude, Name: "Claude Code", Installed: false}
	info.Running = isProcessRunning("claude") || isProcessRunning("claude-code") || isProcessRunning("claude_code")

	home, err := os.UserHomeDir()
	if err != nil {
		return info
	}

	// Check for Claude Code config - prefer ~/.claude/settings.json, fallback to ~/.claude.json
	settingsPath := filepath.Join(home, ".claude", "settings.json")
	if _, err := os.Stat(settingsPath); err == nil {
		info.Installed = true
		info.ConfigPath = settingsPath
	} else {
		claudeJsonPath := filepath.Join(home, ".claude.json")
		if _, err := os.Stat(claudeJsonPath); err == nil {
			info.Installed = true
			info.ConfigPath = claudeJsonPath
		}
	}

	// Also check for claude CLI in PATH
	if isCommandInPath("claude") {
		info.Installed = true
	}

	return info
}

// detectCursor detects Cursor AI agent
func detectCursor() AgentInfo {
	info := AgentInfo{Type: AgentCursor, Name: "Cursor", Installed: false}
	info.Running = isProcessRunning("cursor") || isProcessRunning("Cursor")

	home, err := os.UserHomeDir()
	if err != nil {
		return info
	}

	// Check for Cursor config directory
	var cursorPath string
	if runtime.GOOS == "windows" {
		cursorPath = filepath.Join(os.Getenv("APPDATA"), "Cursor")
	} else {
		cursorPath = filepath.Join(home, ".cursor")
	}

	if _, err := os.Stat(cursorPath); err == nil {
		info.Installed = true
		info.ConfigPath = filepath.Join(cursorPath, "config", "settings.json")
	}

	// Also check for cursor CLI in PATH
	if isCommandInPath("cursor") {
		info.Installed = true
	}

	return info
}

// detectOpenClaw detects OpenClaw agent
func detectOpenClaw() AgentInfo {
	info := AgentInfo{Type: AgentOpenClaw, Name: "OpenClaw", Installed: false}

	// Check if openclaw process is running
	info.Running = isProcessRunning("openclaw")

	home, err := os.UserHomeDir()
	if err != nil {
		// Still check PATH even without home dir
		if isCommandInPath("openclaw") {
			info.Installed = true
		}
		return info
	}

	// Check for OpenClaw config directory - ~/.openclaw/openclaw.json
	openclawPath := filepath.Join(home, ".openclaw")
	if _, err := os.Stat(openclawPath); err == nil {
		info.Installed = true
		info.ConfigPath = filepath.Join(openclawPath, "openclaw.json")
	}

	// Also check for openclaw CLI in PATH
	if isCommandInPath("openclaw") {
		info.Installed = true
	}

	return info
}

// isCommandInPath checks if a command exists in PATH
func isCommandInPath(cmd string) bool {
	_, err := exec.LookPath(cmd)
	return err == nil
}

// isProcessRunning checks if a process with given name is running
func isProcessRunning(name string) bool {
	var cmd *exec.Cmd
	if runtime.GOOS == "windows" {
		cmd = exec.Command("tasklist", "/FI", "IMAGENAME eq "+name+".exe")
	} else {
		cmd = exec.Command("pgrep", "-x", name)
	}

	output, err := cmd.Output()
	if err != nil {
		return false
	}

	// On Windows, tasklist returns process list
	// On Unix, pgrep returns PID if found
	if runtime.GOOS == "windows" {
		return strings.Contains(string(output), name+".exe")
	}
	return len(strings.TrimSpace(string(output))) > 0
}

// GetAgentDisplayName returns a human-readable name for an agent
func GetAgentDisplayName(agent AgentType) string {
	switch agent {
	case AgentCodex:
		return "Codex"
	case AgentClaude:
		return "Claude Code"
	case AgentCursor:
		return "Cursor"
	case AgentOpenClaw:
		return "OpenClaw"
	default:
		return string(agent)
	}
}
