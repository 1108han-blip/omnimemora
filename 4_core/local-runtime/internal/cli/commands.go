// internal/cli/commands.go - CLI Commands for OmniMemora
// Implements start, status, stop, dashboard, attach, and detach commands
package cli

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"

	"github.com/omnimemora/local-runtime/internal/attach"
	rtpkg "github.com/omnimemora/local-runtime/internal/runtime"
	"github.com/omnimemora/local-runtime/internal/verify"
)

// Start starts the OmniMemora runtime and surfaces detected agents in the UI.
func Start(args []string, version string) error {
	// Parse flags
	portFlag := ""
	skipAttach := false
	forceAttach := false
	for i, arg := range args {
		if arg == "--port" && i+1 < len(args) {
			portFlag = args[i+1]
		}
		if arg == "--skip-attach" {
			skipAttach = true
		}
		if arg == "--attach" {
			forceAttach = true
		}
	}

	// Check if already running
	existingPort, _, exists := loadRuntimeState()
	runtimeIsRunning := false
	actualPort := existingPort

	if exists {
		if err := checkRuntimeHealth(existingPort); err == nil {
			// Runtime is responding on saved port - use it
			runtimeIsRunning = true
			actualPort = existingPort
			fmt.Printf("OmniMemora is already running on port %d\n", existingPort)
			fmt.Printf("Runtime dashboard (internal/operator): http://127.0.0.1:%d/dashboard\n", existingPort)
		} else {
			// Saved port not responding - scan default ports
			foundPort := 0
			for _, p := range []int{8765, 8766, 8767, 8775} {
				if p != existingPort && checkRuntimeHealth(p) == nil {
					foundPort = p
					break
				}
			}
			if foundPort > 0 {
				// Found runtime on a different port - use it directly
				runtimeIsRunning = true
				actualPort = foundPort
				fmt.Printf("Found OmniMemora running on port %d (state was stale)\n", foundPort)
			} else {
				// No runtime found - clear stale state
				clearRuntimeState()
			}
		}
	}

	// If runtime is running (either from state or found via scan), optionally proceed with explicit attach
	if runtimeIsRunning {
		// Wait for runtime to be fully ready
		if err := waitForRuntime(actualPort, 5*time.Second); err != nil {
			fmt.Printf("Warning: Runtime may not be fully ready: %v\n", err)
		}
		// Attach is now explicit. Only run when the operator asks for it.
		if forceAttach && !skipAttach {
			runAutoAttachFlow(actualPort, forceAttach)
		} else {
			showDetectedAgentCandidates()
		}
		return nil
	}

	// Run bootstrap (first-run detection and demo seeding)
	bootstrapResult, err := bootstrap.Bootstrap()
	if err != nil {
		return fmt.Errorf("bootstrap failed: %w", err)
	}

	// Resolve port
	preferredPort := 8765
	if portFlag != "" {
		if p, err := strconv.Atoi(portFlag); err == nil {
			preferredPort = p
		}
	}

	port, portSwitched, err := rtpkg.ResolvePort(preferredPort)
	if err != nil {
		return fmt.Errorf("failed to find available port: %w", err)
	}

	if portSwitched {
		fmt.Printf("Port %d is occupied, switched to %d.\n", preferredPort, port)
	}

	// Start the runtime server in a subprocess
	pid, err := startRuntimeServer(port, version)
	if err != nil {
		clearRuntimeState()
		return fmt.Errorf("failed to start runtime: %w", err)
	}

	if err := rtpkg.SaveRuntimeState(port, pid); err != nil {
		return fmt.Errorf("failed to save runtime state: %w", err)
	}

	// Wait for server to be ready
	if err := waitForRuntime(port, 10*time.Second); err != nil {
		fmt.Printf("Warning: Runtime started but may not be fully ready: %v\n", err)
	}

	// Print startup info
	fmt.Printf("OmniMemora v%s started successfully\n", version)
	fmt.Printf("Runtime:   http://127.0.0.1:%d\n", port)
	fmt.Printf("Runtime dashboard (internal/operator): http://127.0.0.1:%d/dashboard\n", port)
	fmt.Printf("Product entry: http://127.0.0.1:18011\n")
	fmt.Printf("Data dir:  %s\n", bootstrapResult.DataDir)

	if bootstrapResult.FirstRun {
		fmt.Println("\nFirst run complete! Demo data has been seeded.")
		fmt.Println("The runtime dashboard should show initial internal token-savings data.")
	}

	// Open dashboard in browser
	openBrowser(fmt.Sprintf("http://127.0.0.1:%d/dashboard", port))

	// Agent detection remains visible, but attach is explicit and UI-controlled by default.
	if forceAttach && !skipAttach {
		runAutoAttachFlow(port, forceAttach)
	} else {
		showDetectedAgentCandidates()
	}

	return nil
}

func showDetectedAgentCandidates() {
	agents := attach.DetectAgents()
	if len(agents) == 0 {
		return
	}

	fmt.Println()
	fmt.Println("Detected agents (shown in UI, not auto-attached):")
	for _, agent := range agents {
		fmt.Printf("  - %s\n", agent.Name)
	}
}

// runAutoAttachFlow performs the full auto-detect/attach/verify flow
func runAutoAttachFlow(port int, forceAttach bool) {
	// Step 1: Detect agents
	agents := attach.DetectAgents()
	if len(agents) == 0 {
		attach.ShowNoAgentWarning()
		return
	}

	// Step 2: Resolve attach strategy
	strategy, _ := attach.ResolveAttachStrategy(agents)

	switch strategy {
	case attach.AutoAttach:
		// Single agent - auto attach
		fmt.Println()
		fmt.Println("  Detected:", agents[0].Name)
		result := attachAgent(agents[0].Type, port)
		showAttachResult(result)

	case attach.ShowSelection:
		if forceAttach {
			// Force attach = attach all without prompting
			attachAllAgents(agents, port)
		} else {
			// Show quick select UI
			quickResult := attach.ShowQuickSelectUI(agents)
			if quickResult.Skipped {
				fmt.Println("  Skipped agent attachment.")
			} else {
				attachSelectedAgents(quickResult.Selected, port)
			}
		}

	case attach.SkipAttach:
		// No agents detected
		attach.ShowNoAgentWarning()
	}

	// Step 3: Run auto-verify
	fmt.Println()
	fmt.Println("  Running memory verification...")
	verifyReq := verify.DefaultVerifyRequest(port)
	verifyResult := verify.RunAutoVerify(verifyReq)
	if verifyResult.Success {
		fmt.Printf("  ✓ Memory verification passed (write: %dms, recall: %dms)\n",
			verifyResult.WriteDurationMs, verifyResult.RecallDurationMs)
	} else {
		fmt.Printf("  ⚠ Verification: %s\n", verifyResult.Message)
	}
}

// attachAgent attaches a single agent and returns the result
func attachAgent(agentType attach.AgentType, port int) *attach.AttachResult {
	switch agentType {
	case attach.AgentCodex:
		return attach.AttachCodex()
	case attach.AgentClaude:
		return attach.AttachClaude()
	case attach.AgentCursor:
		return attach.AttachCursor()
	case attach.AgentOpenClaw:
		return attach.AttachOpenClaw()
	default:
		return &attach.AttachResult{Agent: agentType, Success: false, Message: "Unknown agent type"}
	}
}

// attachAllAgents attaches all detected agents
func attachAllAgents(agents []attach.AgentInfo, port int) {
	fmt.Println()
	fmt.Println("  Attaching all detected agents...")
	results := &attach.AttachResults{}
	for _, agent := range agents {
		result := attachAgent(agent.Type, port)
		results.Results = append(results.Results, *result)
		results.TotalAttempted++
		if result.Success {
			results.TotalSucceeded++
		}
	}
	attach.ShowAttachSuccess(results)
}

// attachSelectedAgents attaches user-selected agents
func attachSelectedAgents(selected []attach.AgentType, port int) {
	if len(selected) == 0 {
		return
	}
	results := &attach.AttachResults{}
	for _, agentType := range selected {
		result := attachAgent(agentType, port)
		results.Results = append(results.Results, *result)
		results.TotalAttempted++
		if result.Success {
			results.TotalSucceeded++
		}
	}
	attach.ShowAttachSuccess(results)
}

// showAttachResult shows the result of a single attach
func showAttachResult(result *attach.AttachResult) {
	agentName := attach.GetAgentDisplayName(result.Agent)
	if result.Success {
		fmt.Printf("  ✓ %s configured successfully\n", agentName)
	} else {
		fmt.Printf("  ✗ %s: %s\n", agentName, result.Message)
	}
}

// Attach connects an agent to OmniMemora
func Attach(args []string) error {
	// Check for help flag first
	for _, arg := range args {
		if arg == "--help" || arg == "-h" {
			printAttachUsage()
			return nil
		}
	}

	port, _, exists := loadRuntimeState()
	if !exists {
		// State file missing - scan default ports to find running runtime
		fmt.Println("Runtime state not found, scanning for running OmniMemora...")
		foundPort := 0
		for _, p := range []int{8765, 8766, 8767, 8775} {
			if checkRuntimeHealth(p) == nil {
				foundPort = p
				break
			}
		}
		if foundPort == 0 {
			fmt.Println("OmniMemora is not running")
			fmt.Println("\nRun 'omnimemora start' first.")
			return nil
		}
		port = foundPort
		fmt.Printf("Found OmniMemora running on port %d\n", port)
	}

	if err := checkRuntimeHealth(port); err != nil {
		// Try other default ports
		foundPort := 0
		for _, p := range []int{8765, 8766, 8767, 8775} {
			if p != port && checkRuntimeHealth(p) == nil {
				foundPort = p
				break
			}
		}
		if foundPort == 0 {
			fmt.Printf("OmniMemora is not responding on port %d\n", port)
			fmt.Println("Run 'omnimemora start' first.")
			return nil
		}
		port = foundPort
	}

	if len(args) == 0 {
		// No agent specified - show detected agents
		agents := attach.DetectAgents()
		if len(agents) == 0 {
			attach.ShowNoAgentWarning()
			return nil
		}

		fmt.Println()
		fmt.Println("  Detected agents:")
		for _, a := range agents {
			status := ""
			if attach.IsAttached(a.Type, port) {
				status = " (configured)"
			}
			fmt.Printf("    • %s%s\n", a.Name, status)
		}
		fmt.Println()
		fmt.Println("  Usage: omnimemora attach <agent>")
		fmt.Println("  Agents: codex, claude, cursor, openclaw")
		return nil
	}

	agentArg := args[0]
	var agentType attach.AgentType
	switch agentArg {
	case "codex":
		agentType = attach.AgentCodex
	case "claude":
		agentType = attach.AgentClaude
	case "cursor":
		agentType = attach.AgentCursor
	case "openclaw":
		agentType = attach.AgentOpenClaw
	case "all":
		// Attach all detected agents
		agents := attach.DetectAgents()
		if len(agents) == 0 {
			attach.ShowNoAgentWarning()
			return nil
		}
		attachAllAgents(agents, port)
		return nil
	default:
		fmt.Printf("\nUnknown agent: %s\n\n", agentArg)
		fmt.Println("Available agents:")
		fmt.Println("  codex       - OpenAI Codex")
		fmt.Println("  claude      - Claude Code (Anthropic)")
		fmt.Println("  cursor      - Cursor AI")
		fmt.Println("  openclaw    - OpenClaw")
		fmt.Println("  all         - Attach all detected agents")
		fmt.Println()
		fmt.Println("Examples:")
		fmt.Println("  omnimemora attach codex")
		fmt.Println("  omnimemora attach claude")
		fmt.Println("  omnimemora attach all")
		return nil
	}

	// Check if already attached
	if attach.IsAttached(agentType, port) {
		agentName := attach.GetAgentDisplayName(agentType)
		fmt.Printf("%s is already configured.\n", agentName)
		return nil
	}

	// Attach the agent
	fmt.Println()
	result := attachAgent(agentType, port)
	showAttachResult(result)

	return nil
}

// Detach disconnects an agent from OmniMemora
func Detach(args []string) error {
	// Check for help flag first
	for _, arg := range args {
		if arg == "--help" || arg == "-h" {
			printDetachUsage()
			return nil
		}
	}

	port, _, exists := loadRuntimeState()
	if !exists {
		fmt.Println("OmniMemora is not running")
		return nil
	}

	if len(args) == 0 {
		fmt.Println("Usage: omnimemora detach <agent>")
		fmt.Println("  Valid agents: codex, claude, cursor, openclaw, all")
		return nil
	}

	agentArg := args[0]
	var agentType attach.AgentType
	switch agentArg {
	case "codex":
		agentType = attach.AgentCodex
	case "claude":
		agentType = attach.AgentClaude
	case "cursor":
		agentType = attach.AgentCursor
	case "openclaw":
		agentType = attach.AgentOpenClaw
	case "all":
		// Detach all agents
		attach.DetachCodex()
		attach.DetachClaude()
		attach.DetachCursor()
		attach.DetachOpenClaw()
		fmt.Println("All agents detached.")
		return nil
	default:
		fmt.Printf("\nUnknown agent: %s\n\n", agentArg)
		fmt.Println("Available agents:")
		fmt.Println("  codex       - OpenAI Codex")
		fmt.Println("  claude      - Claude Code (Anthropic)")
		fmt.Println("  cursor      - Cursor AI")
		fmt.Println("  openclaw    - OpenClaw")
		fmt.Println("  all         - Detach all agents")
		fmt.Println()
		fmt.Println("Examples:")
		fmt.Println("  omnimemora detach codex")
		fmt.Println("  omnimemora detach claude")
		fmt.Println("  omnimemora detach all")
		return nil
	}

	// Detach the agent
	err := attach.DetachAgent(agentType, port)
	agentName := attach.GetAgentDisplayName(agentType)
	if err != nil {
		fmt.Printf("Failed to detach %s: %v\n", agentName, err)
	} else {
		fmt.Printf("%s detached successfully.\n", agentName)
	}

	return nil
}

// Status shows the current runtime status
// Uses /health as source of truth for runtime state
func Status() error {
	// First, try to load state file
	port, pid, stateExists := loadRuntimeState()

	// Always verify via /health as source of truth
	// Try saved port first, then scan default ports
	portsToCheck := []int{port}
	if port != 8765 {
		portsToCheck = append(portsToCheck, 8765)
	}
	if port != 8766 {
		portsToCheck = append(portsToCheck, 8766)
	}
	if port != 8767 {
		portsToCheck = append(portsToCheck, 8767)
	}

	var activePort int
	for _, p := range portsToCheck {
		if p <= 0 {
			continue
		}
		if checkRuntimeHealth(p) == nil {
			activePort = p
			break
		}
	}

	if activePort == 0 {
		// No responding runtime found
		if stateExists {
			fmt.Println("Runtime state file exists but runtime is not responding.")
			fmt.Printf("PID: %d\n", pid)
		} else {
			fmt.Println("OmniMemora is not running")
		}
		fmt.Println("\nRun 'omnimemora start' to start the runtime.")
		return nil
	}

	// Runtime is responding - /health is source of truth
	fmt.Printf("Running on :%d\n", activePort)
	if pid > 0 {
		fmt.Printf("PID: %d\n", pid)
	}
	fmt.Println("Status: healthy")

	// Get metrics
	metrics, err := fetchMetrics(activePort)
	if err != nil {
		fmt.Printf("Runtime dashboard (internal/operator): http://127.0.0.1:%d/dashboard\n", activePort)
		fmt.Println("\nToken savings data unavailable.")
	} else {
		if metrics.TokenSavings.TodaySavedTokens > 0 {
			estimatedCost := float64(metrics.TokenSavings.TodaySavedTokens) / 1000 * 0.01 // rough estimate
			fmt.Printf("Today saved: %s tokens (~$%.2f)\n", formatInt64(metrics.TokenSavings.TodaySavedTokens), estimatedCost)
		} else {
			fmt.Println("Today saved: 0 tokens")
		}

		if metrics.TokenSavings.TotalSavedTokens > 0 {
			fmt.Printf("Total saved: %s tokens\n", formatInt64(metrics.TokenSavings.TotalSavedTokens))
		}

		fmt.Printf("\nRuntime dashboard (internal/operator): http://127.0.0.1:%d/dashboard\n", activePort)
	}

	return nil
}

// Stop stops the runtime
func Stop() error {
	port, pid, exists := loadRuntimeState()

	if !exists {
		fmt.Println("OmniMemora is not running")
		clearRuntimeState()
		return nil
	}

	// Try graceful shutdown via HTTP
	client := &http.Client{Timeout: 5 * time.Second}
	req, _ := http.NewRequest("POST", fmt.Sprintf("http://localhost:%d/shutdown", port), nil)
	resp, err := client.Do(req)
	if err == nil {
		resp.Body.Close()
		// Give it a moment to shut down
		time.Sleep(500 * time.Millisecond)
	}

	// If process is still running, kill it
	if pid > 0 {
		proc, _ := os.FindProcess(pid)
		if proc != nil {
			_ = proc.Kill()
			time.Sleep(100 * time.Millisecond)
		}
	}

	clearRuntimeState()
	fmt.Println("OmniMemora stopped")
	return nil
}

// OpenDashboard opens the dashboard in browser
func OpenDashboard(args []string) error {
	port, _, exists := loadRuntimeState()

	if !exists {
		fmt.Println("OmniMemora is not running")
		fmt.Println("\nRun 'omnimemora start' first.")
		return nil
	}

	url := fmt.Sprintf("http://127.0.0.1:%d/dashboard", port)

	if err := checkRuntimeHealth(port); err != nil {
		fmt.Printf("OmniMemora is not responding on port %d\n", port)
		return nil
	}

	fmt.Printf("Opening runtime dashboard (internal/operator): %s\n", url)
	return openBrowser(url)
}

// ConnectCodex shows Codex integration guide
func ConnectCodex(args []string) error {
	adapterPort := 18011 // Python Adapter MCP port (not Go Runtime 8765)
	adapterURL := fmt.Sprintf("http://127.0.0.1:%d", adapterPort)

	fmt.Printf(`
=== OmniMemora Codex Integration ===

The recommended way to integrate OmniMemora with Codex is via the MCP shim
(tools/mcp_omnimemora.py), which proxies stdio JSON-RPC to the adapter at %s.

Add to your Codex config (~/.codex/config.toml):

  [mcp_servers.omnimemora]
  command = "python"
  args = ["path/to/tools/mcp_omnimemora.py"]
  env = { OMNIMEMORA_ADAPTER_URL = "%s" }

Or use the automatic attach command:
  omnimemora attach codex

For manual setup, run 'omnimemora attach codex' from the project root.

`, adapterURL, adapterURL)

	return nil
}

// ConnectClaude shows Claude Code integration guide
func ConnectClaude(args []string) error {
	adapterPort := 18011 // Python Adapter port (not Go Runtime 8765)
	adapterURL := fmt.Sprintf("http://127.0.0.1:%d", adapterPort)

	fmt.Printf(`
=== OmniMemora Claude Code Integration ===

Adapter URL:
  %s

Add to your CLAUDE.md or project configuration.

Or via environment variable:
  export OMNIMEMORA_URL=%s

`, adapterURL, adapterURL)

	return nil
}

// Helper functions

func startRuntimeServer(port int, version string) (int, error) {
	// Get the current executable path
	execPath, err := os.Executable()
	if err != nil {
		return 0, fmt.Errorf("failed to get executable path: %w", err)
	}

	// Build command - pass serve subcommand
	cmd := exec.Command(execPath, "serve", fmt.Sprintf("--port=%d", port))

	stdoutFile, stderrFile, closeLogs, err := openRuntimeLogFiles()
	if err != nil {
		return 0, fmt.Errorf("failed to setup runtime logs: %w", err)
	}
	defer func() {
		if closeLogs != nil {
			closeLogs()
		}
	}()
	cmd.Stdout = stdoutFile
	cmd.Stderr = stderrFile

	if err := cmd.Start(); err != nil {
		return 0, fmt.Errorf("failed to start server process: %w", err)
	}

	return cmd.Process.Pid, nil
}

func openRuntimeLogFiles() (*os.File, *os.File, func(), error) {
	logDir, err := resolveRuntimeLogDir()
	if err != nil {
		return nil, nil, nil, err
	}
	if err := os.MkdirAll(logDir, 0755); err != nil {
		return nil, nil, nil, fmt.Errorf("failed to create log dir: %w", err)
	}

	stdoutPath := filepath.Join(logDir, "runtime.out.log")
	stderrPath := filepath.Join(logDir, "runtime.err.log")

	stdoutFile, err := os.OpenFile(stdoutPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("failed to open stdout log: %w", err)
	}
	stderrFile, err := os.OpenFile(stderrPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		_ = stdoutFile.Close()
		return nil, nil, nil, fmt.Errorf("failed to open stderr log: %w", err)
	}

	closeLogs := func() {
		_ = stdoutFile.Close()
		_ = stderrFile.Close()
	}
	return stdoutFile, stderrFile, closeLogs, nil
}

func resolveRuntimeLogDir() (string, error) {
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_RUNTIME_LOG_DIR")); v != "" {
		return filepath.Clean(os.ExpandEnv(v)), nil
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_LOG_DIR")); v != "" {
		return filepath.Clean(os.ExpandEnv(v)), nil
	}
	dataDir, err := rtpkg.GetDataDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dataDir, "logs"), nil
}

func waitForRuntime(port int, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)

	for time.Now().Before(deadline) {
		if err := checkRuntimeHealth(port); err == nil {
			return nil
		}
		time.Sleep(200 * time.Millisecond)
	}

	return fmt.Errorf("timeout waiting for runtime")
}

func checkRuntimeHealth(port int) error {
	client := &http.Client{Timeout: 2 * time.Second}
	resp, err := client.Get(fmt.Sprintf("http://127.0.0.1:%d/health", port))
	if err != nil {
		return err
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("health check returned %d", resp.StatusCode)
	}
	return nil
}

func fetchMetrics(port int) (*MetricsResponse, error) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(fmt.Sprintf("http://127.0.0.1:%d/metrics", port))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("metrics returned %d", resp.StatusCode)
	}

	var metrics MetricsResponse
	if err := json.NewDecoder(resp.Body).Decode(&metrics); err != nil {
		return nil, err
	}

	return &metrics, nil
}

// MetricsResponse represents the metrics endpoint response
type MetricsResponse struct {
	TokenSavings *TokenSavings `json:"token_savings,omitempty"`
	MCP          *MCPMetrics   `json:"mcp,omitempty"`
}

type TokenSavings struct {
	TotalSavedTokens int64 `json:"total_saved_tokens"`
	TodaySavedTokens int64 `json:"today_saved_tokens"`
	WeekSavedTokens  int64 `json:"week_saved_tokens"`
	MonthSavedTokens int64 `json:"month_saved_tokens"`
}

type MCPMetrics struct {
	Handshakes                     int64  `json:"handshakes"`
	ToolInvocations                int64  `json:"tool_invocations"`
	MemoryWriteCalls               int64  `json:"memory_write_calls"`
	MemorySearchContextRecallCalls int64  `json:"memory_search_context_recall_calls"`
	LastStartupError               string `json:"last_startup_error,omitempty"`
}

func openBrowser(url string) error {
	goos := runtime.GOOS
	var cmd *exec.Cmd
	switch goos {
	case "windows":
		cmd = exec.Command("cmd", "/c", "start", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	return cmd.Start()
}

func loadRuntimeState() (port int, pid int, exists bool) {
	port, pid, exists, _ = rtpkg.LoadRuntimeState()
	return
}

func clearRuntimeState() {
	rtpkg.ClearRuntimeState()
}

func isProcessRunning(pid int) bool {
	return rtpkg.IsProcessRunning(pid)
}

func formatInt64(n int64) string {
	if n >= 1000000 {
		return fmt.Sprintf("%.1fM", float64(n)/1000000)
	}
	if n >= 1000 {
		return fmt.Sprintf("%.1fK", float64(n)/1000)
	}
	return fmt.Sprintf("%d", n)
}

// Need to import bootstrap
var bootstrap = struct {
	Bootstrap func() (*BootstrapResult, error)
}{
	Bootstrap: bootstrapImpl,
}

// BootstrapResult contains the results of bootstrap operation
type BootstrapResult struct {
	Initialized  bool
	DemoExecuted bool
	Port         int
	DataDir      string
	FirstRun     bool
}

func bootstrapImpl() (*BootstrapResult, error) {
	result := &BootstrapResult{}

	// Get data directory
	dataDir, err := rtpkg.GetDataDir()
	if err != nil {
		return nil, fmt.Errorf("failed to get data directory: %w", err)
	}
	result.DataDir = dataDir

	// Create directory structure
	if err := createDirs(dataDir); err != nil {
		return nil, fmt.Errorf("failed to create directories: %w", err)
	}

	// Check if first run
	isFirstRun, err := isFirstRun(dataDir)
	if err != nil {
		return nil, fmt.Errorf("failed to check first run status: %w", err)
	}
	result.FirstRun = isFirstRun

	if isFirstRun {
		// Mark as initialized BEFORE demo seeding
		if err := markInitialized(dataDir); err != nil {
			return nil, fmt.Errorf("failed to mark initialized: %w", err)
		}
		result.Initialized = true
	}

	return result, nil
}

func createDirs(dataDir string) error {
	// Simple implementation - ensure directory exists
	return os.MkdirAll(dataDir, 0755)
}

func isFirstRun(dataDir string) (bool, error) {
	markerFile := dataDir + "/bootstrap/first_run_done"
	_, err := os.Stat(markerFile)
	if err == nil {
		return false, nil
	}
	if os.IsNotExist(err) {
		return true, nil
	}
	return false, err
}

func markInitialized(dataDir string) error {
	bootstrapDir := dataDir + "/bootstrap"
	if err := os.MkdirAll(bootstrapDir, 0755); err != nil {
		return err
	}
	markerFile := bootstrapDir + "/first_run_done"
	content := fmt.Sprintf("initialized=true\ncreated=%s\n", time.Now().UTC().Format(time.RFC3339))
	return os.WriteFile(markerFile, []byte(content), 0644)
}

// runtime package reference
var _ = rtpkg.IsProcessRunning

// printAttachUsage displays help for the attach command
func printAttachUsage() {
	fmt.Print(`
Usage:
  omnimemora attach <agent> [options]

Connect an AI agent to OmniMemora.

Agents:
  codex       OpenAI Codex
  claude      Claude Code (Anthropic)
  cursor      Cursor AI
  openclaw    OpenClaw
  all         Attach all detected agents

Options:
  --help, -h  Show this help

Examples:
  omnimemora attach codex       Connect to Codex
  omnimemora attach claude      Connect to Claude Code
  omnimemora attach all         Connect all detected agents
  omnimemora attach             Show detected agents
`)
}

// printDetachUsage displays help for the detach command
func printDetachUsage() {
	fmt.Print(`
Usage:
  omnimemora detach <agent> [options]

Disconnect an AI agent from OmniMemora.

Agents:
  codex       OpenAI Codex
  claude      Claude Code (Anthropic)
  cursor      Cursor AI
  openclaw    OpenClaw
  all         Detach all agents

Options:
  --help, -h  Show this help

Examples:
  omnimemora detach codex       Disconnect from Codex
  omnimemora detach claude      Disconnect from Claude Code
  omnimemora detach all         Disconnect all agents
`)
}
