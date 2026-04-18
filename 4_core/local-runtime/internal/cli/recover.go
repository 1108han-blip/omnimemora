package cli

import (
	"fmt"
	"strings"

	"github.com/omnimemora/local-runtime/api"
	"github.com/omnimemora/local-runtime/internal/attach"
)

// Recover provides an offline decision carrier fallback for extreme failure paths.
// It is intended for runtime-dead scenarios and does not depend on runtime HTTP health.
func Recover(args []string) error {
	if len(args) == 0 {
		printRecoverUsage()
		return nil
	}
	if args[0] == "-h" || args[0] == "--help" {
		printRecoverUsage()
		return nil
	}
	if len(args) < 2 {
		printRecoverUsage()
		return fmt.Errorf("recover requires <disable-route|uninstall> <family>")
	}

	action := strings.TrimSpace(args[0])
	familyID, agentType, err := resolveRecoverFamily(args[1])
	if err != nil {
		return err
	}

	switch action {
	case "disable-route":
		result, err := api.ApplyDisableRouteDecision(familyID)
		if err != nil {
			return err
		}
		fmt.Printf("Recover action applied: %s for %s\n", result.Action, result.FamilyID)
		fmt.Println(result.Message)
		return nil
	case "uninstall":
		result, err := api.ApplyUninstallDecision(agentType, familyID)
		if err != nil {
			return err
		}
		fmt.Printf("Recover action applied: %s for %s\n", result.Action, result.FamilyID)
		fmt.Println(result.Message)
		return nil
	default:
		printRecoverUsage()
		return fmt.Errorf("unknown recover action: %s", action)
	}
}

func resolveRecoverFamily(raw string) (string, attach.AgentType, error) {
	switch strings.TrimSpace(strings.ToLower(raw)) {
	case "codex", "codex_cli":
		return "codex_cli", attach.AgentCodex, nil
	case "claude", "claude_code":
		return "claude_code", attach.AgentClaude, nil
	case "cursor":
		return "cursor", attach.AgentCursor, nil
	case "openclaw":
		return "openclaw", attach.AgentOpenClaw, nil
	default:
		return "", "", fmt.Errorf("unknown family: %s", raw)
	}
}

func printRecoverUsage() {
	fmt.Print(`
Usage:
  omnimemora recover disable-route <family>
  omnimemora recover uninstall <family>

Families:
  codex | codex_cli
  claude | claude_code
  cursor
  openclaw
`)
}
