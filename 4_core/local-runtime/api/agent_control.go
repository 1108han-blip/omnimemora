package api

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/omnimemora/local-runtime/internal/attach"
)

func registerInstallControlRoutes(mux *http.ServeMux, server *Server) {
	mux.HandleFunc("GET /agents/control", server.handleAgentControlList)
	mux.HandleFunc("POST /agents/control/rescan", server.handleAgentControlRescan)
	mux.HandleFunc("POST /agents/control/install", server.handleAgentControlInstall)
	mux.HandleFunc("POST /agents/control/uninstall", server.handleAgentControlUninstall)
}

type agentControlStatus struct {
	FamilyID        string `json:"family_id"`
	DisplayName     string `json:"display_name"`
	Detected        bool   `json:"detected"`
	Installed       bool   `json:"installed"`
	BackupAvailable bool   `json:"backup_available"`
	ConfigPath      string `json:"config_path,omitempty"`
	Message         string `json:"message,omitempty"`
}

type agentControlRequest struct {
	FamilyID string `json:"family_id"`
}

func controlFamilyID(agent attach.AgentType) string {
	switch agent {
	case attach.AgentCodex:
		return "codex_cli"
	case attach.AgentClaude:
		return "claude_code"
	case attach.AgentCursor:
		return "cursor"
	case attach.AgentOpenClaw:
		return "openclaw"
	default:
		return string(agent)
	}
}

func controlAgentByFamily(familyID string) (attach.AgentType, error) {
	switch familyID {
	case "codex", "codex_cli":
		return attach.AgentCodex, nil
	case "claude", "claude_code":
		return attach.AgentClaude, nil
	case "cursor":
		return attach.AgentCursor, nil
	case "openclaw":
		return attach.AgentOpenClaw, nil
	default:
		return "", fmt.Errorf("unknown family_id: %s", familyID)
	}
}

func buildAgentControlStatuses() []agentControlStatus {
	detected := attach.DetectAgents()
	statuses := make([]agentControlStatus, 0, len(detected))
	for _, info := range detected {
		configPath := info.ConfigPath
		if configPath == "" {
			if resolved, err := attach.GetConfigPath(info.Type); err == nil {
				configPath = resolved
			}
		}
		statuses = append(statuses, agentControlStatus{
			FamilyID:        controlFamilyID(info.Type),
			DisplayName:     info.Name,
			Detected:        true,
			Installed:       attach.IsAttached(info.Type, 8765),
			BackupAvailable: attach.BackupExists(info.Type),
			ConfigPath:      configPath,
		})
	}
	return statuses
}

func statusForAgent(agentType attach.AgentType) agentControlStatus {
	desiredFamily := controlFamilyID(agentType)
	for _, status := range buildAgentControlStatuses() {
		if status.FamilyID == desiredFamily {
			return status
		}
	}
	displayName := attach.GetAgentDisplayName(agentType)
	configPath, _ := attach.GetConfigPath(agentType)
	return agentControlStatus{
		FamilyID:        desiredFamily,
		DisplayName:     displayName,
		Detected:        false,
		Installed:       attach.IsAttached(agentType, 8765),
		BackupAvailable: attach.BackupExists(agentType),
		ConfigPath:      configPath,
		Message:         "agent not detected on this machine",
	}
}

func (s *Server) handleAgentControlList(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, 200, map[string]any{
		"agents": buildAgentControlStatuses(),
		"count":  len(buildAgentControlStatuses()),
	})
}

func (s *Server) handleAgentControlRescan(w http.ResponseWriter, r *http.Request) {
	s.handleAgentControlList(w, r)
}

// Runtime agent control remains the low-frequency install layer only.
// Product routing and product-facing control semantics stay at :18011.
func (s *Server) handleAgentControlInstall(w http.ResponseWriter, r *http.Request) {
	var req agentControlRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}

	agentType, err := controlAgentByFamily(req.FamilyID)
	if err != nil {
		writeError(w, 400, "UNKNOWN_AGENT", err.Error())
		return
	}

	var result *attach.AttachResult
	switch agentType {
	case attach.AgentCodex:
		result = attach.AttachCodex()
	case attach.AgentClaude:
		result = attach.AttachClaude()
	case attach.AgentCursor:
		result = attach.AttachCursor()
	case attach.AgentOpenClaw:
		result = attach.AttachOpenClaw()
	default:
		writeError(w, 400, "UNKNOWN_AGENT", "unsupported agent")
		return
	}

	status := statusForAgent(agentType)
	status.Message = result.Message
	if !result.Success {
		writeJSON(w, 500, status)
		return
	}
	writeJSON(w, 200, status)
}

func (s *Server) handleAgentControlUninstall(w http.ResponseWriter, r *http.Request) {
	var req agentControlRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}

	agentType, err := controlAgentByFamily(req.FamilyID)
	if err != nil {
		writeError(w, 400, "UNKNOWN_AGENT", err.Error())
		return
	}

	if err := attach.DetachAgent(agentType, 8765); err != nil {
		writeError(w, 500, "UNINSTALL_FAILED", err.Error())
		return
	}

	status := statusForAgent(agentType)
	status.Message = "detached and restored backup"
	writeJSON(w, 200, status)
}
