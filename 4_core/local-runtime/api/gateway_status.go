package api

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"

	rtpkg "github.com/omnimemora/local-runtime/internal/runtime"
)

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
