package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

// registerControlCarrierRoutes exposes runtime-local recovery decision routes.
// These are control-carrier surfaces, not memory-plane routes and not product entry.
func registerControlCarrierRoutes(mux *http.ServeMux, server *Server) {
	mux.HandleFunc("GET /gateway/status", server.handleGatewayStatus)
	mux.HandleFunc("POST /gateway/decision/disable-route", server.handleGatewayDecisionDisableRoute)
	mux.HandleFunc("POST /gateway/decision/uninstall", server.handleGatewayDecisionUninstall)
}

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

// handleGatewayStatus serves the runtime-local control carrier state.
// It is separate from runtime capability health and survives as the canonical
// recovery decision surface for runtime-local operators.
func (s *Server) handleGatewayStatus(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, 200, loadGatewayStatus())
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
	result, err := ApplyDisableRouteDecision(familyID)
	if err != nil {
		writeError(w, 500, "DISABLE_ROUTE_DECISION_FAILED", err.Error())
		return
	}
	writeJSON(w, 200, map[string]any{
		"family_id": result.FamilyID,
		"action":    result.Action,
		"applied":   true,
		"message":   result.Message,
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
	result, err := ApplyUninstallDecision(agentType, familyID)
	if err != nil {
		writeError(w, 500, "UNINSTALL_DECISION_FAILED", err.Error())
		return
	}
	writeJSON(w, 200, map[string]any{
		"family_id": result.FamilyID,
		"action":    result.Action,
		"applied":   true,
		"message":   result.Message,
	})
}
