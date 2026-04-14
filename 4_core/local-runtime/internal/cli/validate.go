package cli

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/omnimemora/local-runtime/internal/attach"
)

type validateOptions struct {
	Agent   string
	Profile string
	Runs    int
	OutBase string
}

type validateReport struct {
	GeneratedAt time.Time         `json:"generated_at"`
	Agent       string            `json:"agent"`
	Profile     string            `json:"profile"`
	RuntimePort int               `json:"runtime_port"`
	Preflight   preflightResult   `json:"preflight"`
	Runs        []validationRun   `json:"runs"`
	Criteria    []criterionResult `json:"criteria"`
	Passed      bool              `json:"passed"`
}

type preflightResult struct {
	OpenClawConfigured bool `json:"openclaw_configured"`
	HandshakeOK        bool `json:"handshake_ok"`
	ToolsListOK        bool `json:"tools_list_ok"`
	MemoryWriteOK      bool `json:"memory_write_ok"`
	MemorySearchOK     bool `json:"memory_search_ok"`
	SavingsNonZero     bool `json:"savings_non_zero"`
}

type validationRun struct {
	Index    int               `json:"index"`
	Classes  []taskClassResult `json:"classes"`
	Criteria []criterionResult `json:"criteria"`
	Passed   bool              `json:"passed"`
}

type taskClassResult struct {
	Name               string        `json:"name"`
	SessionID          string        `json:"session_id"`
	Turns              []turnResult  `json:"turns"`
	MetricsStart       metricSnapshot `json:"metrics_start"`
	MetricsEnd         metricSnapshot `json:"metrics_end"`
	FirstHalfSaved     int64         `json:"first_half_saved"`
	SecondHalfSaved    int64         `json:"second_half_saved"`
	HalfRatio          float64       `json:"half_ratio"`
	SearchDiffRatio    float64       `json:"search_diff_ratio"`
	HasStartupError    bool          `json:"has_startup_error"`
	DashboardAlwaysActive bool       `json:"dashboard_always_active"`
}

type turnResult struct {
	Index           int    `json:"index"`
	Message         string `json:"message"`
	CommandError    string `json:"command_error,omitempty"`
	StartupError    bool   `json:"startup_error"`
	DashboardActive bool   `json:"dashboard_active"`
	SavingsDelta    int64  `json:"savings_delta"`
	WriteDelta      int64  `json:"write_delta"`
	SearchDelta     int64  `json:"search_delta"`
	ToolDelta       int64  `json:"tool_delta"`
}

type metricSnapshot struct {
	Handshakes int64 `json:"handshakes"`
	Tools      int64 `json:"tools"`
	WriteCalls int64 `json:"write_calls"`
	SearchCalls int64 `json:"search_calls"`
	SavedTotal int64 `json:"saved_total"`
	SavedToday int64 `json:"saved_today"`
	SavedWeek  int64 `json:"saved_week"`
	SavedMonth int64 `json:"saved_month"`
	LastStartupError string `json:"last_startup_error,omitempty"`
}

type criterionResult struct {
	Code     string `json:"code"`
	Passed   bool   `json:"passed"`
	Actual   string `json:"actual"`
	Expected string `json:"expected"`
}

type taskClassTemplate struct {
	Name     string
	Messages []string
}

// Validate runs P0-3 validation and writes report files.
// Usage: omnimemora validate openclaw --profile p0-3 --runs 3 --out ./artifacts/p0_3_report
func Validate(args []string) error {
	opts, err := parseValidateOptions(args)
	if err != nil {
		if err.Error() == "" {
			return nil
		}
		return err
	}

	port, err := detectActivePort()
	if err != nil {
		return err
	}

	report := validateReport{
		GeneratedAt: time.Now().UTC(),
		Agent:       opts.Agent,
		Profile:     opts.Profile,
		RuntimePort: port,
	}

	preflight, err := runPreflight(port)
	if err != nil {
		return err
	}
	report.Preflight = preflight

	for i := 1; i <= opts.Runs; i++ {
		runResult := validationRun{Index: i}
		for _, tmpl := range p03TaskTemplates(i) {
			classResult := runTaskClass(port, i, tmpl)
			runResult.Classes = append(runResult.Classes, classResult)
		}
		runResult.Criteria, runResult.Passed = evaluateRun(runResult)
		report.Runs = append(report.Runs, runResult)
	}

	report.Criteria, report.Passed = evaluateOverall(report)
	jsonPath, mdPath, err := writeValidationReports(opts.OutBase, report)
	if err != nil {
		return err
	}

	fmt.Printf("Validation report written:\n  %s\n  %s\n", jsonPath, mdPath)
	if report.Passed {
		fmt.Println("P0-3 validation: PASS")
		return nil
	}

	return fmt.Errorf("P0-3 validation failed: see report for failed criteria")
}

func parseValidateOptions(args []string) (*validateOptions, error) {
	opts := &validateOptions{
		Agent:   "openclaw",
		Profile: "p0-3",
		Runs:    3,
		OutBase: filepath.FromSlash("./artifacts/p0_3_report"),
	}

	rest := args
	if len(rest) > 0 && !strings.HasPrefix(rest[0], "--") {
		opts.Agent = strings.ToLower(rest[0])
		rest = rest[1:]
	}
	if opts.Agent != "openclaw" {
		return nil, fmt.Errorf("only openclaw is supported currently")
	}

	for i := 0; i < len(rest); i++ {
		switch rest[i] {
		case "--profile":
			if i+1 < len(rest) {
				opts.Profile = rest[i+1]
				i++
			}
		case "--runs":
			if i+1 < len(rest) {
				var runs int
				fmt.Sscanf(rest[i+1], "%d", &runs)
				if runs > 0 {
					opts.Runs = runs
				}
				i++
			}
		case "--out":
			if i+1 < len(rest) {
				opts.OutBase = rest[i+1]
				i++
			}
		case "-h", "--help":
			printValidateUsage()
			return nil, fmt.Errorf("")
		}
	}

	if opts.Profile != "p0-3" {
		return nil, fmt.Errorf("unsupported profile: %s", opts.Profile)
	}
	if opts.Runs < 3 {
		return nil, fmt.Errorf("--runs must be >= 3 for stable P0-3 validation")
	}
	if strings.HasSuffix(opts.OutBase, ".json") || strings.HasSuffix(opts.OutBase, ".md") {
		opts.OutBase = strings.TrimSuffix(strings.TrimSuffix(opts.OutBase, ".json"), ".md")
	}
	return opts, nil
}

func printValidateUsage() {
	fmt.Print(`
Usage:
  omnimemora validate openclaw [--profile p0-3] [--runs 3] [--out ./artifacts/p0_3_report]
`)
}

func detectActivePort() (int, error) {
	port, _, exists := loadRuntimeState()
	if exists && checkRuntimeHealth(port) == nil {
		return port, nil
	}
	for _, p := range []int{8765, 8766, 8767, 8775} {
		if checkRuntimeHealth(p) == nil {
			return p, nil
		}
	}
	return 0, fmt.Errorf("OmniMemora runtime is not running")
}

func runPreflight(port int) (preflightResult, error) {
	p := preflightResult{
		OpenClawConfigured: attach.IsAttached(attach.AgentOpenClaw, port),
	}

	if resp, err := mcpHTTP(port, map[string]any{
		"jsonrpc": "2.0",
		"id":      1,
		"method":  "initialize",
		"params": map[string]any{
			"protocolVersion": "2024-11-05",
			"capabilities":    map[string]any{},
			"clientInfo":      map[string]any{"name": "omnimemora-validate", "version": "1.0"},
		},
	}); err == nil && strings.Contains(resp, `"protocolVersion":"2024-11-05"`) {
		p.HandshakeOK = true
	}

	if resp, err := mcpHTTP(port, map[string]any{
		"jsonrpc": "2.0",
		"id":      2,
		"method":  "tools/list",
	}); err == nil {
		if strings.Contains(resp, `"name":"memory.write"`) &&
			strings.Contains(resp, `"name":"memory.search"`) &&
			strings.Contains(resp, `"name":"memory.context"`) {
			p.ToolsListOK = true
		}
	}

	if resp, err := mcpHTTP(port, map[string]any{
		"jsonrpc": "2.0",
		"id":      3,
		"method":  "tools/call",
		"params": map[string]any{
			"name":      "memory.write",
			"arguments": map[string]any{"content": "[p0-3 preflight] write memory"},
		},
	}); err == nil && strings.Contains(resp, "memory written") {
		p.MemoryWriteOK = true
	}

	if resp, err := mcpHTTP(port, map[string]any{
		"jsonrpc": "2.0",
		"id":      4,
		"method":  "tools/call",
		"params": map[string]any{
			"name":      "memory.search",
			"arguments": map[string]any{"keyword": "p0-3 preflight", "limit": 3},
		},
	}); err == nil && strings.Contains(resp, "search done") {
		p.MemorySearchOK = true
	}

	m, err := fetchMetrics(port)
	if err != nil {
		return p, err
	}
	if m.TokenSavings != nil && (m.TokenSavings.TotalSavedTokens > 0 ||
		m.TokenSavings.TodaySavedTokens > 0 ||
		m.TokenSavings.WeekSavedTokens > 0 ||
		m.TokenSavings.MonthSavedTokens > 0) {
		p.SavingsNonZero = true
	}
	return p, nil
}

func p03TaskTemplates(runIndex int) []taskClassTemplate {
	return []taskClassTemplate{
		{
			Name: "连续问答型",
			Messages: []string{
				fmt.Sprintf("P0-3 run %d 连续问答第1轮：先调用 memory.write 记录主题“Atlas发布风险”，再调用 memory.search 检索相同主题。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 连续问答第2轮：继续追问Atlas成本，必须调用 memory.context 或 memory.recall。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 连续问答第3轮：补充依赖项，先 write 再 search。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 连续问答第4轮：复述前文结论，调用 memory.context。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 连续问答第5轮：新增约束，先 write 后 search。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 连续问答第6轮：收敛行动项，调用 memory.search。只输出工具结果。", runIndex),
			},
		},
		{
			Name: "编辑迭代型",
			Messages: []string{
				fmt.Sprintf("P0-3 run %d 编辑迭代第1轮：写入文稿版本v1要点（memory.write），再检索v1。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 编辑迭代第2轮：在v1基础上做v2修改，调用 memory.write + memory.context。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 编辑迭代第3轮：继续到v3并检索差异，调用 memory.write + memory.search。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 编辑迭代第4轮：定稿v4，调用 memory.context 汇总。只输出工具结果。", runIndex),
			},
		},
		{
			Name: "项目执行型",
			Messages: []string{
				fmt.Sprintf("P0-3 run %d 项目执行第1步：写入项目里程碑（memory.write）并检索。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 项目执行第2步：记录风险清单，调用 memory.write + memory.search。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 项目执行第3步：记录负责人分工，调用 memory.write + memory.context。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 项目执行第4步：基于前文给出执行顺序，调用 memory.recall 或 memory.context。只输出工具结果。", runIndex),
				fmt.Sprintf("P0-3 run %d 项目执行第5步：收尾检查，调用 memory.search。只输出工具结果。", runIndex),
			},
		},
	}
}

func runTaskClass(port int, runIndex int, tmpl taskClassTemplate) taskClassResult {
	sessionID := fmt.Sprintf("p03-%d-%s", runIndex, sanitizeName(tmpl.Name))
	start, _ := currentSnapshot(port)
	prev := start

	result := taskClassResult{
		Name:           tmpl.Name,
		SessionID:      sessionID,
		MetricsStart:   start,
		DashboardAlwaysActive: true,
	}

	half := len(tmpl.Messages) / 2
	if half == 0 {
		half = 1
	}
	var firstHalfSearch, secondHalfSearch int64

	for i, message := range tmpl.Messages {
		output, cmdErr := runOpenClawTurn(sessionID, message)
		now, _ := currentSnapshot(port)
		dashboardActive, _ := isDashboardActive(port)

		turn := turnResult{
			Index:           i + 1,
			Message:         message,
			DashboardActive: dashboardActive,
			SavingsDelta:    maxInt64(now.SavedTotal-prev.SavedTotal, 0),
			WriteDelta:      maxInt64(now.WriteCalls-prev.WriteCalls, 0),
			SearchDelta:     maxInt64(now.SearchCalls-prev.SearchCalls, 0),
			ToolDelta:       maxInt64(now.Tools-prev.Tools, 0),
		}
		if cmdErr != nil {
			turn.CommandError = cmdErr.Error()
		}
		if detectStartupError(output) || strings.TrimSpace(now.LastStartupError) != "" {
			turn.StartupError = true
			result.HasStartupError = true
		}
		if !dashboardActive {
			result.DashboardAlwaysActive = false
		}

		if i < half {
			result.FirstHalfSaved += turn.SavingsDelta
			firstHalfSearch += turn.SearchDelta
		} else {
			result.SecondHalfSaved += turn.SavingsDelta
			secondHalfSearch += turn.SearchDelta
		}

		result.Turns = append(result.Turns, turn)
		prev = now
	}

	result.MetricsEnd = prev
	result.HalfRatio = computeHalfRatio(result.FirstHalfSaved, result.SecondHalfSaved)
	result.SearchDiffRatio = computeSearchDiffRatio(firstHalfSearch, secondHalfSearch)
	return result
}

func runOpenClawTurn(sessionID, message string) (string, error) {
	cmd := exec.Command("openclaw", "agent", "--local", "--agent", "main", "--session-id", sessionID, "--message", message, "--timeout", "180", "--json")
	out, err := cmd.CombinedOutput()
	return string(out), err
}

func currentSnapshot(port int) (metricSnapshot, error) {
	metrics, err := fetchMetrics(port)
	if err != nil {
		return metricSnapshot{}, err
	}
	s := metricSnapshot{}
	if metrics.MCP != nil {
		s.Handshakes = metrics.MCP.Handshakes
		s.Tools = metrics.MCP.ToolInvocations
		s.WriteCalls = metrics.MCP.MemoryWriteCalls
		s.SearchCalls = metrics.MCP.MemorySearchContextRecallCalls
		s.LastStartupError = metrics.MCP.LastStartupError
	}
	if metrics.TokenSavings != nil {
		s.SavedTotal = metrics.TokenSavings.TotalSavedTokens
		s.SavedToday = metrics.TokenSavings.TodaySavedTokens
		s.SavedWeek = metrics.TokenSavings.WeekSavedTokens
		s.SavedMonth = metrics.TokenSavings.MonthSavedTokens
	}
	return s, nil
}

func isDashboardActive(port int) (bool, error) {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get(fmt.Sprintf("http://127.0.0.1:%d/dashboard", port))
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()
	var buf bytes.Buffer
	_, _ = buf.ReadFrom(resp.Body)
	body := buf.String()
	return strings.Contains(body, "Memory Tools Active"), nil
}

func detectStartupError(output string) bool {
	lower := strings.ToLower(output)
	if strings.Contains(lower, "failed to start server") ||
		strings.Contains(lower, "sse error") ||
		strings.Contains(lower, "non-200 status code") ||
		strings.Contains(lower, "404") {
		return true
	}
	return false
}

func evaluateRun(run validationRun) ([]criterionResult, bool) {
	var criteria []criterionResult
	all := true

	noStartup := true
	toolNonZero := true
	savingsGrowth := true
	halfRatioOK := true
	firstHalfMinOK := true
	searchDiffOK := true
	dashboardActive := true

	for _, c := range run.Classes {
		if c.HasStartupError {
			noStartup = false
		}
		deltaTools := c.MetricsEnd.Tools - c.MetricsStart.Tools
		if deltaTools <= 0 {
			toolNonZero = false
		}
		if c.SecondHalfSaved <= c.FirstHalfSaved {
			savingsGrowth = false
		}
		if c.HalfRatio < 1.3 {
			halfRatioOK = false
		}
		if c.FirstHalfSaved < 300 {
			firstHalfMinOK = false
		}
		if c.SearchDiffRatio > 0.30 {
			searchDiffOK = false
		}
		if !c.DashboardAlwaysActive {
			dashboardActive = false
		}
	}

	criteria = append(criteria, criterionResult{
		Code:     "no_mcp_startup_error",
		Passed:   noStartup,
		Actual:   fmt.Sprintf("classes=%d startup_error=%v", len(run.Classes), !noStartup),
		Expected: "no startup error across all classes",
	})
	criteria = append(criteria, criterionResult{
		Code:     "tool_invocations_non_zero",
		Passed:   toolNonZero,
		Actual:   "all classes have non-zero tool deltas",
		Expected: "tool invocations stay non-zero",
	})
	criteria = append(criteria, criterionResult{
		Code:     "savings_continuous_growth",
		Passed:   savingsGrowth,
		Actual:   "second_half_saved > first_half_saved for each class",
		Expected: "savings sustained growth",
	})
	criteria = append(criteria, criterionResult{
		Code:     "half_ratio_ge_1_3",
		Passed:   halfRatioOK,
		Actual:   "ratio(second/first) per class",
		Expected: ">= 1.3",
	})
	criteria = append(criteria, criterionResult{
		Code:     "first_half_saved_ge_300",
		Passed:   firstHalfMinOK,
		Actual:   "first half saved tokens per class",
		Expected: ">= 300",
	})
	criteria = append(criteria, criterionResult{
		Code:     "search_call_diff_le_30pct",
		Passed:   searchDiffOK,
		Actual:   "abs(second-first)/max(first,1)",
		Expected: "<= 0.30",
	})
	criteria = append(criteria, criterionResult{
		Code:     "dashboard_memory_tools_active",
		Passed:   dashboardActive,
		Actual:   "dashboard active status in all turns",
		Expected: "always Memory Tools Active",
	})

	for _, c := range criteria {
		if !c.Passed {
			all = false
		}
	}
	return criteria, all
}

func evaluateOverall(report validateReport) ([]criterionResult, bool) {
	var criteria []criterionResult
	passRuns := 0
	for _, run := range report.Runs {
		if run.Passed {
			passRuns++
		}
	}

	preflightOK := report.Preflight.OpenClawConfigured &&
		report.Preflight.HandshakeOK &&
		report.Preflight.ToolsListOK &&
		report.Preflight.MemoryWriteOK &&
		report.Preflight.MemorySearchOK &&
		report.Preflight.SavingsNonZero

	criteria = append(criteria, criterionResult{
		Code:     "preflight_gate",
		Passed:   preflightOK,
		Actual:   fmt.Sprintf("configured=%v handshake=%v tools=%v write=%v search=%v savings_non_zero=%v",
			report.Preflight.OpenClawConfigured,
			report.Preflight.HandshakeOK,
			report.Preflight.ToolsListOK,
			report.Preflight.MemoryWriteOK,
			report.Preflight.MemorySearchOK,
			report.Preflight.SavingsNonZero),
		Expected: "all preflight checks true",
	})

	criteria = append(criteria, criterionResult{
		Code:     "stable_reproduce_3_runs",
		Passed:   passRuns >= 3,
		Actual:   fmt.Sprintf("pass_runs=%d", passRuns),
		Expected: ">= 3 PASS runs",
	})

	all := true
	for _, c := range criteria {
		if !c.Passed {
			all = false
		}
	}
	return criteria, all
}

func writeValidationReports(outBase string, report validateReport) (string, string, error) {
	if outBase == "" {
		outBase = filepath.FromSlash("./artifacts/p0_3_report")
	}
	jsonPath := outBase + ".json"
	mdPath := outBase + ".md"
	if err := os.MkdirAll(filepath.Dir(jsonPath), 0755); err != nil {
		return "", "", err
	}

	jsonBytes, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return "", "", err
	}
	if err := os.WriteFile(jsonPath, jsonBytes, 0644); err != nil {
		return "", "", err
	}

	var md strings.Builder
	md.WriteString("# OmniMemora P0-3 Validation Report\n\n")
	md.WriteString(fmt.Sprintf("- Generated: %s\n", report.GeneratedAt.Format(time.RFC3339)))
	md.WriteString(fmt.Sprintf("- Agent: %s\n", report.Agent))
	md.WriteString(fmt.Sprintf("- Profile: %s\n", report.Profile))
	md.WriteString(fmt.Sprintf("- Runtime Port: %d\n", report.RuntimePort))
	md.WriteString(fmt.Sprintf("- Overall: **%s**\n\n", passLabel(report.Passed)))

	md.WriteString("## Preflight\n\n")
	md.WriteString(fmt.Sprintf("- OpenClaw configured: %v\n", report.Preflight.OpenClawConfigured))
	md.WriteString(fmt.Sprintf("- MCP handshake: %v\n", report.Preflight.HandshakeOK))
	md.WriteString(fmt.Sprintf("- tools/list memory visible: %v\n", report.Preflight.ToolsListOK))
	md.WriteString(fmt.Sprintf("- memory.write success: %v\n", report.Preflight.MemoryWriteOK))
	md.WriteString(fmt.Sprintf("- memory.search success: %v\n", report.Preflight.MemorySearchOK))
	md.WriteString(fmt.Sprintf("- metrics savings non-zero: %v\n\n", report.Preflight.SavingsNonZero))

	for _, run := range report.Runs {
		md.WriteString(fmt.Sprintf("## Run %d: %s\n\n", run.Index, passLabel(run.Passed)))
		for _, c := range run.Classes {
			deltaTools := c.MetricsEnd.Tools - c.MetricsStart.Tools
			deltaWrites := c.MetricsEnd.WriteCalls - c.MetricsStart.WriteCalls
			deltaSearch := c.MetricsEnd.SearchCalls - c.MetricsStart.SearchCalls
			deltaSaved := c.MetricsEnd.SavedTotal - c.MetricsStart.SavedTotal
			md.WriteString(fmt.Sprintf("### %s\n", c.Name))
			md.WriteString(fmt.Sprintf("- MCP Handshakes Δ: %d\n", c.MetricsEnd.Handshakes-c.MetricsStart.Handshakes))
			md.WriteString(fmt.Sprintf("- Tool Invocations Δ: %d\n", deltaTools))
			md.WriteString(fmt.Sprintf("- memory.write Δ: %d\n", deltaWrites))
			md.WriteString(fmt.Sprintf("- memory.search/context/recall Δ: %d\n", deltaSearch))
			md.WriteString(fmt.Sprintf("- token_savings.total_saved_tokens Δ: %d\n", deltaSaved))
			md.WriteString(fmt.Sprintf("- first_half_saved: %d\n", c.FirstHalfSaved))
			md.WriteString(fmt.Sprintf("- second_half_saved: %d\n", c.SecondHalfSaved))
			md.WriteString(fmt.Sprintf("- half_ratio: %.2f\n", c.HalfRatio))
			md.WriteString(fmt.Sprintf("- search_diff_ratio: %.2f\n", c.SearchDiffRatio))
			md.WriteString(fmt.Sprintf("- startup_error: %v\n", c.HasStartupError))
			md.WriteString(fmt.Sprintf("- dashboard_always_active: %v\n\n", c.DashboardAlwaysActive))
		}
	}

	md.WriteString("## Overall Criteria\n\n")
	for _, c := range report.Criteria {
		md.WriteString(fmt.Sprintf("- [%s] `%s` actual=%s expected=%s\n", passMarker(c.Passed), c.Code, c.Actual, c.Expected))
	}

	if err := os.WriteFile(mdPath, []byte(md.String()), 0644); err != nil {
		return "", "", err
	}
	return jsonPath, mdPath, nil
}

func mcpHTTP(port int, payload map[string]any) (string, error) {
	body, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	req, err := http.NewRequest("POST", fmt.Sprintf("http://127.0.0.1:%d/mcp", port), bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 8 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	var out bytes.Buffer
	_, _ = out.ReadFrom(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return out.String(), fmt.Errorf("mcp status %d", resp.StatusCode)
	}
	return out.String(), nil
}

func sanitizeName(v string) string {
	v = strings.TrimSpace(strings.ToLower(v))
	v = strings.ReplaceAll(v, " ", "-")
	v = strings.ReplaceAll(v, "型", "")
	return v
}

func maxInt64(a, b int64) int64 {
	if a > b {
		return a
	}
	return b
}

func computeHalfRatio(firstHalf, secondHalf int64) float64 {
	if firstHalf <= 0 {
		if secondHalf > 0 {
			return 999
		}
		return 0
	}
	return float64(secondHalf) / float64(firstHalf)
}

func computeSearchDiffRatio(firstHalfSearch, secondHalfSearch int64) float64 {
	base := maxInt64(firstHalfSearch, 1)
	diff := firstHalfSearch - secondHalfSearch
	if diff < 0 {
		diff = -diff
	}
	return float64(diff) / float64(base)
}

func passLabel(ok bool) string {
	if ok {
		return "PASS"
	}
	return "FAIL"
}

func passMarker(ok bool) string {
	if ok {
		return "x"
	}
	return " "
}
