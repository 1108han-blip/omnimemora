package api

import (
	"fmt"

	"github.com/omnimemora/local-runtime/internal/attach"
)

// ApplyDisableRouteDecision and ApplyUninstallDecision are runtime-local
// control carrier actions. They do not redefine memory-plane behavior and are
// not product-entry semantics.
type controlCarrierActionResult struct {
	FamilyID string
	Action   string
	Message  string
}

type ControlCarrierActionResult struct {
	FamilyID string
	Action   string
	Message  string
}

func ApplyDisableRouteDecision(familyID string) (*ControlCarrierActionResult, error) {
	if err := disableRouteForFamily(familyID); err != nil {
		return nil, fmt.Errorf("persist route off: %w", err)
	}
	if err := writeGatewayDecision(gatewayDecisionPayload{
		Action:           "disable-route",
		FamilyID:         familyID,
		DecisionSource:   "user-runtime-action",
		TransitionReason: "user_disabled_route_after_gateway_failure",
	}); err != nil {
		return nil, fmt.Errorf("persist gateway decision: %w", err)
	}
	return &ControlCarrierActionResult{
		FamilyID: familyID,
		Action:   "disable_route",
		Message:  "route state persisted as off; successful gateway recovery will converge to healthy passthrough (routing_effective=false)",
	}, nil
}

func ApplyUninstallDecision(agentType attach.AgentType, familyID string) (*ControlCarrierActionResult, error) {
	if err := disableRouteForFamily(familyID); err != nil {
		return nil, fmt.Errorf("persist route off before uninstall: %w", err)
	}
	if err := attach.DetachAgent(agentType, 8765); err != nil {
		return nil, fmt.Errorf("detach agent: %w", err)
	}
	if err := writeGatewayDecision(gatewayDecisionPayload{
		Action:           "uninstall",
		FamilyID:         familyID,
		DecisionSource:   "user-runtime-action",
		TransitionReason: "user_uninstalled_after_gateway_failure",
	}); err != nil {
		return nil, fmt.Errorf("persist gateway decision: %w", err)
	}
	return &ControlCarrierActionResult{
		FamilyID: familyID,
		Action:   "uninstall",
		Message:  "route state persisted as off; agent detached and backup restore attempted; successful gateway recovery will remain outside product-enhanced routing",
	}, nil
}
