package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/omnimemora/local-runtime/internal/attach"
)

type gatewayDecisionRequest struct {
	FamilyID string `json:"family_id"`
}

type agentModesFile struct {
	Comment       string            `json:"_comment,omitempty"`
	PerAgentModes map[string]string `json:"per_agent_modes"`
	DefaultMode   string            `json:"default_mode"`
}

func agentModesPath() string {
	return strings.TrimSpace(os.Getenv("OMNIMEMORA_AGENT_MODES_PATH"))
}

func loadAgentModes() (*agentModesFile, error) {
	path := agentModesPath()
	if path == "" {
		return nil, fmt.Errorf("OMNIMEMORA_AGENT_MODES_PATH not configured")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return &agentModesFile{
				Comment:       "Per-agent routing control for OmniMemora UI. Keys must be canonical_agent_id.",
				PerAgentModes: map[string]string{},
				DefaultMode:   "off",
			}, nil
		}
		return nil, err
	}
	var cfg agentModesFile
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return nil, err
	}
	if cfg.PerAgentModes == nil {
		cfg.PerAgentModes = map[string]string{}
	}
	if strings.TrimSpace(cfg.DefaultMode) == "" {
		cfg.DefaultMode = "off"
	}
	if strings.TrimSpace(cfg.Comment) == "" {
		cfg.Comment = "Per-agent routing control for OmniMemora UI. Keys must be canonical_agent_id."
	}
	return &cfg, nil
}

func saveAgentModes(cfg *agentModesFile) error {
	path := agentModesPath()
	if path == "" {
		return fmt.Errorf("OMNIMEMORA_AGENT_MODES_PATH not configured")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0644)
}

func disableRouteForFamily(familyID string) error {
	cfg, err := loadAgentModes()
	if err != nil {
		return err
	}
	cfg.PerAgentModes[familyID] = "off"
	return saveAgentModes(cfg)
}

func (s *Server) handleGatewayDecisionDisableRoute(w http.ResponseWriter, r *http.Request) {
	var req gatewayDecisionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}
	agentType, err := controlAgentByFamily(req.FamilyID)
	if err != nil {
		writeError(w, 400, "UNKNOWN_AGENT", err.Error())
		return
	}
	familyID := controlFamilyID(agentType)
	if err := disableRouteForFamily(familyID); err != nil {
		writeError(w, 500, "DISABLE_ROUTE_FAILED", err.Error())
		return
	}
	if err := writeGatewayDecision(gatewayDecisionPayload{
		Action:           "disable-route",
		FamilyID:         familyID,
		DecisionSource:   "user-runtime-action",
		TransitionReason: "user_disabled_route_after_gateway_failure",
	}); err != nil {
		writeError(w, 500, "DISABLE_ROUTE_DECISION_FAILED", err.Error())
		return
	}
	writeJSON(w, 200, map[string]any{
		"family_id": familyID,
		"action":    "disable_route",
		"applied":   true,
		"message":   "route state persisted as off; gateway restart may still be required",
	})
}

func (s *Server) handleGatewayDecisionUninstall(w http.ResponseWriter, r *http.Request) {
	var req gatewayDecisionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}
	agentType, err := controlAgentByFamily(req.FamilyID)
	if err != nil {
		writeError(w, 400, "UNKNOWN_AGENT", err.Error())
		return
	}
	familyID := controlFamilyID(agentType)
	if err := disableRouteForFamily(familyID); err != nil {
		writeError(w, 500, "UNINSTALL_ROUTE_STATE_FAILED", err.Error())
		return
	}
	if err := attach.DetachAgent(agentType, 8765); err != nil {
		writeError(w, 500, "UNINSTALL_FAILED", err.Error())
		return
	}
	if err := writeGatewayDecision(gatewayDecisionPayload{
		Action:           "uninstall",
		FamilyID:         familyID,
		DecisionSource:   "user-runtime-action",
		TransitionReason: "user_uninstalled_after_gateway_failure",
	}); err != nil {
		writeError(w, 500, "UNINSTALL_DECISION_FAILED", err.Error())
		return
	}
	writeJSON(w, 200, map[string]any{
		"family_id": familyID,
		"action":    "uninstall",
		"applied":   true,
		"message":   "route state persisted as off; agent detached and backup restore attempted; gateway restart may still be required",
	})
}
