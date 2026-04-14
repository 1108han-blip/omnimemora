// internal/attach/strategy.go - Attach Strategy Resolution
// Determines whether to auto-attach or show selection UI
package attach

import (
	"fmt"
)

// AttachStrategy determines how agents are selected for attachment
type AttachStrategy int

const (
	// AutoAttach auto-attaches without prompting
	AutoAttach AttachStrategy = iota
	// ShowSelection shows a quick-select UI
	ShowSelection
	// SkipAttach skips attachment entirely
	SkipAttach
)

// ResolveAttachStrategy determines the appropriate attach strategy
// based on the number and type of detected agents
func ResolveAttachStrategy(agents []AgentInfo) (AttachStrategy, []AgentInfo) {
	if len(agents) == 0 {
		return SkipAttach, nil
	}

	if len(agents) == 1 {
		// Single agent - auto attach
		return AutoAttach, agents
	}

	// Multiple agents - show selection UI
	return ShowSelection, agents
}

// ShouldAutoAttach returns true if we should auto-attach without prompting
func ShouldAutoAttach(agents []AgentInfo) bool {
	if len(agents) == 0 {
		return false
	}
	// Auto-attach only when exactly one agent is detected
	return len(agents) == 1
}

// GetAutoAttachAgent returns the single agent to auto-attach, or nil
func GetAutoAttachAgent(agents []AgentInfo) *AgentInfo {
	if len(agents) != 1 {
		return nil
	}
	return &agents[0]
}

// AttachResult represents the result of an attach operation
type AttachResult struct {
	Agent     AgentType
	Success   bool
	Message   string
	ConfigWriten bool
}

// AttachResults contains results for multiple attach operations
type AttachResults struct {
	Results     []AttachResult
	TotalAttempted int
	TotalSucceeded int
}

// String returns a summary of attach results
func (r *AttachResults) String() string {
	if len(r.Results) == 0 {
		return "No agents to attach"
	}

	var success, failed []string
	for _, res := range r.Results {
		agentName := GetAgentDisplayName(res.Agent)
		if res.Success {
			success = append(success, agentName)
		} else {
			failed = append(failed, agentName+": "+res.Message)
		}
	}

	msg := ""
	if len(success) > 0 {
		msg += fmt.Sprintf("Attached: %v", success)
	}
	if len(failed) > 0 {
		if msg != "" {
			msg += "\n"
		}
		msg += fmt.Sprintf("Failed: %v", failed)
	}
	return msg
}