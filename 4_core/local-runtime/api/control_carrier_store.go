package api

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	rtpkg "github.com/omnimemora/local-runtime/internal/runtime"
)

// gatewayStatusPayload is the runtime-local control carrier status surface.
// It belongs to the decision/control carrier, not the runtime capability plane.
type gatewayStatusPayload struct {
	Status             string `json:"status"`
	StatusSource       string `json:"status_source,omitempty"`
	TransitionReason   string `json:"transition_reason,omitempty"`
	GatewayHealth      string `json:"gateway_health"`
	CapabilityHealth   string `json:"capability_health"`
	RoutingRequested   bool   `json:"routing_requested"`
	RoutingEffective   bool   `json:"routing_effective"`
	UserActionRequired bool   `json:"user_action_required"`
	RecommendedAction  string `json:"recommended_action"`
	ErrorCode          string `json:"error_code,omitempty"`
}

// gatewayDecisionPayload is the runtime-local control carrier decision intake.
// It records a user decision for the supervisor to consume.
type gatewayDecisionPayload struct {
	Action           string `json:"action"`
	FamilyID         string `json:"family_id"`
	DecisionSource   string `json:"decision_source,omitempty"`
	TransitionReason string `json:"transition_reason,omitempty"`
}

func defaultGatewayStatus() gatewayStatusPayload {
	return gatewayStatusPayload{
		Status:             "healthy",
		StatusSource:       "observed-health",
		TransitionReason:   "gateway_process_healthy",
		GatewayHealth:      "healthy",
		CapabilityHealth:   "healthy",
		RoutingRequested:   false,
		RoutingEffective:   false,
		UserActionRequired: false,
		RecommendedAction:  "none",
	}
}

func gatewayStatusPath() (string, error) {
	if explicit := strings.TrimSpace(os.Getenv("OMNIMEMORA_TRACK_B_STATUS_PATH")); explicit != "" {
		return filepath.Clean(explicit), nil
	}
	dataDir, err := rtpkg.GetDataDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dataDir, "track_b_status.json"), nil
}

func gatewayDecisionPath() (string, error) {
	if explicit := strings.TrimSpace(os.Getenv("OMNIMEMORA_GATEWAY_DECISION_PATH")); explicit != "" {
		return filepath.Clean(explicit), nil
	}
	dataDir, err := rtpkg.GetDataDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dataDir, "gateway_decision.json"), nil
}

func writeGatewayDecision(decision gatewayDecisionPayload) error {
	path, err := gatewayDecisionPath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(decision, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0644)
}

func loadGatewayStatus() gatewayStatusPayload {
	status := defaultGatewayStatus()
	path, err := gatewayStatusPath()
	if err != nil {
		return status
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return status
	}
	if err := json.Unmarshal(raw, &status); err != nil {
		return defaultGatewayStatus()
	}
	if status.Status == "" {
		return defaultGatewayStatus()
	}
	if status.RecommendedAction == "" {
		status.RecommendedAction = "none"
	}
	return status
}
