// internal/attach/ui.go - Terminal Quick-Select UI for Agent Attachment
package attach

import (
	"bufio"
	"fmt"
	"os"
	"strings"
)

// QuickSelectResult contains the user's selection
type QuickSelectResult struct {
	Selected []AgentType
	Skipped  bool
}

// ShowQuickSelectUI displays a terminal UI for multi-agent selection
// Returns selected agents or empty slice if user skipped
func ShowQuickSelectUI(agents []AgentInfo) QuickSelectResult {
	clearScreen()

	// Build header
	fmt.Println()
	fmt.Println("  ╔════════════════════════════════════════════════════════════╗")
	fmt.Println("  ║         OmniMemora - Connect your AI tools                ║")
	fmt.Println("  ╚════════════════════════════════════════════════════════════╝")
	fmt.Println()
	fmt.Println("  OmniMemora detected the following tools on your system:")
	fmt.Println()

	// Show agent list with checkboxes
	selections := make([]bool, len(agents))
	for i, agent := range agents {
		selections[i] = true // Default to checked
		checkbox := "[✓]"
		status := ""
		if agent.Running {
			status = " (running)"
		}
		fmt.Printf("  %s %d. %s%s\n", checkbox, i+1, agent.Name, status)
	}

	fmt.Println()
	fmt.Println("  ──────────────────────────────────────────────────────────────")
	fmt.Println()
	fmt.Println("  Commands:")
	fmt.Println("    [Enter]     - Connect selected agents")
	fmt.Println("    [A]         - Select/deselect all")
	fmt.Println("    [Number]    - Toggle selection (e.g., 1, 2, 3)")
	fmt.Println("    [S]         - Skip (connect later)")
	fmt.Println("    [Q]         - Quit")
	fmt.Println()

	// Simple interactive selection
	reader := bufio.NewReader(os.Stdin)

	for {
		fmt.Print("  > ")
		input, _ := reader.ReadString('\n')
		input = strings.TrimSpace(strings.ToUpper(input))

		if input == "" {
			// Enter pressed - proceed with selected
			break
		}

		if input == "S" || input == "SKIP" {
			return QuickSelectResult{Skipped: true}
		}

		if input == "Q" || input == "QUIT" {
			fmt.Println("  Cancelled.")
			os.Exit(0)
		}

		if input == "A" || input == "ALL" {
			// Toggle all
			allSelected := allSelected(selections)
			for i := range selections {
				selections[i] = !allSelected
			}
		} else {
			// Try to parse as number
			var num int
			if _, err := fmt.Sscanf(input, "%d", &num); err == nil && num >= 1 && num <= len(agents) {
				selections[num-1] = !selections[num-1]
			}
		}

		// Redisplay
		clearScreen()
		fmt.Println()
		fmt.Println("  ╔════════════════════════════════════════════════════════════╗")
		fmt.Println("  ║         OmniMemora - Connect your AI tools                ║")
		fmt.Println("  ╚════════════════════════════════════════════════════════════╝")
		fmt.Println()
		fmt.Println("  OmniMemora detected the following tools on your system:")
		fmt.Println()

		for i, agent := range agents {
			checkbox := "[ ]"
			if selections[i] {
				checkbox = "[✓]"
			}
			status := ""
			if agent.Running {
				status = " (running)"
			}
			fmt.Printf("  %s %d. %s%s\n", checkbox, i+1, agent.Name, status)
		}

		fmt.Println()
		fmt.Println("  ──────────────────────────────────────────────────────────────")
		fmt.Println()
		fmt.Println("  Commands:")
		fmt.Println("    [Enter]     - Connect selected agents")
		fmt.Println("    [A]         - Select/deselect all")
		fmt.Println("    [Number]    - Toggle selection (e.g., 1, 2, 3)")
		fmt.Println("    [S]         - Skip (connect later)")
		fmt.Println("    [Q]         - Quit")
		fmt.Println()
	}

	// Build selected list
	var selected []AgentType
	for i, s := range selections {
		if s {
			selected = append(selected, agents[i].Type)
		}
	}

	return QuickSelectResult{Selected: selected, Skipped: false}
}

func allSelected(selections []bool) bool {
	for _, s := range selections {
		if !s {
			return false
		}
	}
	return true
}

func clearScreen() {
	// Cross-platform clear
	fmt.Print("\033[2J\033[H")
}

// ShowAttachSummary prints a summary of what will be attached
func ShowAttachSummary(agents []AgentInfo) {
	fmt.Println()
	fmt.Println("  The following agents will be connected:")
	for _, a := range agents {
		fmt.Printf("    • %s\n", a.Name)
	}
	fmt.Println()
}

// ShowAttachSuccess prints success message after attachment
func ShowAttachSuccess(results *AttachResults) {
	fmt.Println()
	fmt.Println("  ╔════════════════════════════════════════════════════════════╗")
	fmt.Println("  ║                    Connection Results                      ║")
	fmt.Println("  ╚════════════════════════════════════════════════════════════╝")
	fmt.Println()

	for _, res := range results.Results {
		agentName := GetAgentDisplayName(res.Agent)
		if res.Success {
			fmt.Printf("    ✓ %s configured\n", agentName)
		} else {
			fmt.Printf("    ✗ %s: %s\n", agentName, res.Message)
		}
	}

	fmt.Println()
	if results.TotalSucceeded == results.TotalAttempted {
		fmt.Println("  All selected agents configured successfully!")
	} else {
		fmt.Printf("  %d/%d agents configured.\n", results.TotalSucceeded, results.TotalAttempted)
	}
	fmt.Println()
}

// ShowNoAgentWarning prints a message when no agents are detected
func ShowNoAgentWarning() {
	fmt.Println()
	fmt.Println("  ⚠ No AI agents detected on this system.")
	fmt.Println()
	fmt.Println("  OmniMemora supports:")
	fmt.Println("    • Codex (OpenAI)")
	fmt.Println("    • Claude Code (Anthropic)")
	fmt.Println("    • Cursor")
	fmt.Println("    • OpenClaw")
	fmt.Println()
	fmt.Println("  You can connect later using:")
	fmt.Printf("    omnimemora attach <agent>\n")
	fmt.Println()
}
