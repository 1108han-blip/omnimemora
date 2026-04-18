package api

import (
	"fmt"
	"net"
	"net/http"
	"strconv"
	"strings"

	"github.com/omnimemora/local-runtime/internal/attach"
	"github.com/omnimemora/local-runtime/pkg"
)

func registerOperatorDashboardRoutes(mux *http.ServeMux, server *Server) {
	mux.HandleFunc("GET /dashboard", server.handleDashboard)
}

// handleDashboard serves the runtime-local internal/operator dashboard.
// It is an internal verification and recovery surface, not the product-facing
// control truth.
func (s *Server) handleDashboard(w http.ResponseWriter, r *http.Request) {
	metrics, err := s.service.GetMetrics(r.Context())
	if err != nil {
		html := `<!DOCTYPE html>
<html>
<head>
		<title>OmniMemora Runtime Dashboard</title>
	<meta charset="utf-8">
	<style>
		body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 40px; background: #f5f5f5; }
		.container { max-width: 800px; margin: 0 auto; text-align: center; }
		.error { background: #fee; border: 1px solid #fcc; padding: 20px; border-radius: 8px; color: #633; }
	</style>
</head>
<body>
	<div class="container">
		<div class="error">
			<h2>Dashboard temporarily unavailable</h2>
			<p>Please try refreshing. If the problem persists, restart OmniMemora.</p>
		</div>
	</div>
</body>
</html>`
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(200)
		w.Write([]byte(html))
		return
	}

	hasData := metrics.TokenSavings != nil && (metrics.TokenSavings.TotalSavedTokens > 0 ||
		metrics.TokenSavings.TodaySavedTokens > 0 ||
		metrics.TokenSavings.WeekSavedTokens > 0 ||
		metrics.TokenSavings.MonthSavedTokens > 0)
	runtimePort := resolveDashboardRuntimePort(s.httpServer.Addr, r.Host)
	connectedAgents := detectConnectedAgents(runtimePort)
	hasConnectedAgents := len(connectedAgents) > 0
	mcpHandshakes, mcpToolCalls := s.getMCPStats()
	hasMCPConnected := mcpHandshakes > 0
	hasMCPActive := mcpToolCalls > 0
	gatewayStatus := loadGatewayStatus()

	html := `<!DOCTYPE html>
<html>
<head>
	<title>OmniMemora Runtime - Token Savings Dashboard</title>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<style>
		* { box-sizing: border-box; margin: 0; padding: 0; }
		body {
			font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
			background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
			min-height: 100vh;
			padding: 20px;
		}
		.container { max-width: 900px; margin: 0 auto; }
		.status-card {
			background: white;
			border-radius: 16px;
			padding: 20px 30px;
			margin-bottom: 20px;
			box-shadow: 0 4px 20px rgba(0,0,0,0.08);
		}
		.status-row {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 8px 0;
			border-bottom: 1px solid #edf2f7;
		}
		.status-row:last-child { border-bottom: none; }
		.status-item {
			display: flex;
			align-items: center;
			gap: 10px;
			font-size: 14px;
			color: #4a5568;
		}
		.status-icon {
			width: 24px;
			height: 24px;
			border-radius: 50%;
			display: flex;
			align-items: center;
			justify-content: center;
			font-size: 12px;
			font-weight: bold;
		}
		.status-icon.success { background: #d4edda; color: #155724; }
		.status-icon.warning { background: #fff3cd; color: #856404; }
		.status-icon.inactive { background: #e2e8f0; color: #718096; }
		.gateway-alert {
			background: #fff4e5;
			border: 1px solid #f6ad55;
			color: #7b341e;
			border-radius: 14px;
			padding: 16px 20px;
			margin-bottom: 20px;
			box-shadow: 0 4px 20px rgba(0,0,0,0.05);
		}
		.gateway-alert strong { display: block; margin-bottom: 6px; }
		.hero {
			background: white;
			border-radius: 16px;
			padding: 40px;
			margin-bottom: 20px;
			box-shadow: 0 10px 40px rgba(0,0,0,0.15);
			text-align: center;
		}
		.hero .brand {
			color: #667eea;
			font-size: 14px;
			font-weight: 600;
			letter-spacing: 1px;
			margin-bottom: 20px;
			opacity: 0.8;
		}
		.hero .status {
			display: inline-block;
			background: #d4edda;
			color: #155724;
			padding: 6px 16px;
			border-radius: 20px;
			font-size: 12px;
			font-weight: 600;
			margin-bottom: 20px;
		}
		.total-savings {
			font-size: 64px;
			font-weight: 800;
			color: #2d3748;
			line-height: 1;
			margin-bottom: 8px;
		}
		.total-label {
			font-size: 20px;
			color: #4a5568;
			margin-bottom: 5px;
		}
		.demo-badge {
			display: inline-block;
			background: #fef3c7;
			color: #92400e;
			padding: 4px 12px;
			border-radius: 12px;
			font-size: 11px;
			font-weight: 600;
			margin-left: 10px;
			vertical-align: middle;
		}
		.savings-note {
			font-size: 14px;
			color: #718096;
			margin-top: 10px;
		}
		.metrics-row {
			display: grid;
			grid-template-columns: repeat(3, 1fr);
			gap: 15px;
			margin-top: 30px;
		}
		.metric-box {
			background: #f7fafc;
			border-radius: 12px;
			padding: 20px;
			text-align: center;
		}
		.metric-value {
			font-size: 28px;
			font-weight: 700;
			color: #667eea;
		}
		.metric-label {
			font-size: 12px;
			color: #a0aec0;
			text-transform: uppercase;
			margin-top: 5px;
		}
		.card {
			background: white;
			border-radius: 16px;
			padding: 30px;
			margin-bottom: 20px;
			box-shadow: 0 4px 20px rgba(0,0,0,0.08);
		}
		.card h2 {
			font-size: 18px;
			color: #2d3748;
			margin-bottom: 20px;
			padding-bottom: 10px;
			border-bottom: 2px solid #edf2f7;
		}
		.trend-chart {
			display: flex;
			align-items: flex-end;
			justify-content: space-between;
			height: 120px;
			padding: 0 10px;
			gap: 8px;
		}
		.trend-bar {
			flex: 1;
			background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
			border-radius: 6px 6px 0 0;
			min-height: 4px;
			position: relative;
			transition: transform 0.2s;
		}
		.trend-bar:hover { transform: scaleY(1.05); }
		.trend-labels {
			display: flex;
			justify-content: space-between;
			margin-top: 8px;
			padding: 0 5px;
		}
		.trend-label {
			font-size: 10px;
			color: #a0aec0;
		}
		.no-data {
			text-align: center;
			padding: 40px;
			color: #718096;
		}
		.no-data h3 { color: #4a5568; margin-bottom: 10px; }
		.connect-section {
			background: linear-gradient(135deg, #667eea22 0%, #764ba222 100%);
			border-radius: 12px;
			padding: 20px;
			text-align: center;
		}
		.connect-section code {
			background: #e2e8f0;
			padding: 4px 10px;
			border-radius: 4px;
			font-size: 14px;
		}
		.footer {
			text-align: center;
			padding: 20px;
			color: rgba(255,255,255,0.7);
			font-size: 12px;
		}
		@media (max-width: 600px) {
			.metrics-row { grid-template-columns: 1fr; }
			.total-savings { font-size: 48px; }
		}
	</style>
</head>
<body>
	<div class="container">
`

	html += buildGatewayAlertHTML(gatewayStatus)
	html += buildRuntimeStatusCardHTML(hasConnectedAgents, hasMCPConnected, hasMCPActive, mcpHandshakes, mcpToolCalls)
	html += buildRuntimeHeroHTML(metrics, hasData, hasMCPActive, hasMCPConnected, mcpToolCalls, connectedAgents)
	html += buildTrendSectionHTML(metrics, hasData)
	html += buildEfficiencySectionHTML(metrics, hasData, r.URL.Query().Get("debug") == "1")
	html += `		<div class="footer">
			OmniMemora v` + escapeHTML(metrics.Runtime.Version) + `
		</div>
	</div>
`
	html += gatewayActionScriptHTML()
	html += `</body>
</html>`

	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(200)
	w.Write([]byte(html))
}

func buildRuntimeStatusCardHTML(hasConnectedAgents, hasMCPConnected, hasMCPActive bool, mcpHandshakes, mcpToolCalls int64) string {
	statusCard := `
		<div class="status-card">
			<div class="status-row">
				<div class="status-item">
					<div class="status-icon success">&#10003;</div>
					<span>Runtime Running</span>
				</div>
				<div class="status-item">
					<div class="status-icon `
	if hasConnectedAgents {
		statusCard += `success">&#10003;</div>
					<span>Agent Configured</span>
				</div>
			</div>
			<div class="status-row">
				<div class="status-item">
					<div class="status-icon `
		if hasMCPConnected {
			statusCard += `success">&#10003;</div>
					<span>MCP Connected</span>
				</div>
			</div>`
		} else {
			statusCard += `warning">!</div>
					<span>MCP Handshake Pending</span>
				</div>
			</div>`
		}
	} else {
		statusCard += `warning">!</div>
					<span>Agent Config Pending</span>
				</div>
			</div>
			<div class="status-row">
				<div class="status-item">
					<div class="status-icon warning">!</div>
					<span>MCP Handshake Pending</span>
				</div>
			</div>`
	}
	statusCard += `
			<div class="status-row">
				<div class="status-item">
					<div class="status-icon `
	if hasMCPActive {
		statusCard += `success">&#10003;</div>
					<span>Memory Tools Active</span>
				</div>
			</div>`
	} else {
		statusCard += `warning">!</div>
					<span>Tool Calls Pending</span>
				</div>
			</div>`
	}
	statusCard += `
			<div class="status-row">
				<div class="status-item">
					<div class="status-icon success">&#35;</div>
					<span>MCP Handshakes: ` + fmt.Sprintf("%d", mcpHandshakes) + `</span>
				</div>
				<div class="status-item">
					<div class="status-icon success">&#35;</div>
					<span>Tool Invocations: ` + fmt.Sprintf("%d", mcpToolCalls) + `</span>
				</div>
			</div>
	</div>
`
	return statusCard
}

func buildRuntimeHeroHTML(metrics *pkg.MetricsResponse, hasData, hasMCPActive, hasMCPConnected bool, mcpToolCalls int64, connectedAgents []string) string {
	if hasData {
		isDemoData := metrics.DemoEventsOccurred && !hasMCPActive
		html := `		<div class="hero">
			<div class="brand">OMNIMEMORA</div>
			<div class="total-savings">` + formatInt64(metrics.TokenSavings.TotalSavedTokens) + `</div>
			<div class="total-label">tokens saved</div>
`
		if isDemoData {
			html += `			<div class="demo-badge">Demo data – connect your agent to see real savings</div>
`
		}
		html += `			<div class="metrics-row">
				<div class="metric-box">
					<div class="metric-value">` + formatInt64(metrics.TokenSavings.TodaySavedTokens) + `</div>
					<div class="metric-label">Today</div>
				</div>
				<div class="metric-box">
					<div class="metric-value">` + formatInt64(metrics.TokenSavings.WeekSavedTokens) + `</div>
					<div class="metric-label">This Week</div>
				</div>
				<div class="metric-box">
					<div class="metric-value">` + formatInt64(metrics.TokenSavings.MonthSavedTokens) + `</div>
					<div class="metric-label">This Month</div>
				</div>
			</div>
`
		if !isDemoData {
			html += `			<div class="savings-note">Keep your agent running to accumulate savings</div>
`
		}
		html += `		</div>
`
		return html
	}

	subtitle := "connect your agent to start saving"
	connectBody := `<p style="color: #4a5568; margin-bottom: 15px;">Run one of these commands to connect your agent:</p>
				<p style="margin-bottom: 10px;"><code>omnimemora attach codex</code></p>
				<p style="margin-bottom: 10px;"><code>omnimemora attach claude</code></p>
				<p><code>omnimemora attach openclaw</code></p>`
	if len(connectedAgents) > 0 {
		subtitle = "agent configured, waiting for MCP handshake"
		connectBody = `<p style="color: #4a5568; margin-bottom: 10px;">Configured: <strong>` + strings.Join(connectedAgents, ", ") + `</strong></p>
				<p style="color: #718096;">Configuration is written. Waiting for protocol-level MCP handshake.</p>`
		if hasMCPConnected {
			subtitle = "mcp connected, waiting for first tool call"
			connectBody = `<p style="color: #4a5568; margin-bottom: 10px;">MCP handshake established.</p>
					<p style="color: #718096;">Waiting for first successful memory tool invocation.</p>`
		}
		if hasMCPActive {
			subtitle = "memory tools active, waiting for measurable savings"
			connectBody = `<p style="color: #4a5568; margin-bottom: 10px;">MCP tool calls observed: <strong>` + fmt.Sprintf("%d", mcpToolCalls) + `</strong></p>
					<p style="color: #718096;">Savings will appear after effective context compression in real tasks.</p>`
		}
	}

	return `		<div class="hero">
			<div class="brand">OMNIMEMORA</div>
			<div class="total-savings" style="font-size: 48px; color: #718096;">No savings yet</div>
			<div class="total-label" style="margin-bottom: 20px;">` + subtitle + `</div>
			<span class="status">&#10003; Active</span>
			<div class="connect-section" style="margin-top: 30px;">
				` + connectBody + `
			</div>
		</div>
`
}

func buildTrendSectionHTML(metrics *pkg.MetricsResponse, hasData bool) string {
	if len(metrics.ByDay) == 0 || !hasData {
		return ""
	}
	html := `		<div class="card">
			<h2>Daily Trend</h2>
			<div class="trend-chart">
`
	maxSaved := int64(1)
	daysToShow := metrics.ByDay
	if len(daysToShow) > 7 {
		daysToShow = daysToShow[len(daysToShow)-7:]
	}
	for _, d := range daysToShow {
		if d.SavedTokens > maxSaved {
			maxSaved = d.SavedTokens
		}
	}
	for _, d := range daysToShow {
		height := "4"
		if maxSaved > 0 {
			height = fmt.Sprintf("%d", int(float64(d.SavedTokens)/float64(maxSaved)*100)+4)
		}
		html += `				<div class="trend-bar" style="height:` + height + `px;" title="` + d.Date + `: ` + formatInt64(d.SavedTokens) + ` tokens"></div>
`
	}
	html += `			</div>
			<div class="trend-labels">
				<span class="trend-label">` + daysToShow[0].Date + `</span>
				<span class="trend-label">` + daysToShow[len(daysToShow)-1].Date + `</span>
			</div>
		</div>
`
	return html
}

func buildEfficiencySectionHTML(metrics *pkg.MetricsResponse, hasData, debug bool) string {
	if !hasData || !debug {
		return ""
	}
	return `		<div class="card">
			<h2>Efficiency</h2>
			<div class="metrics-row">
				<div class="metric-box">
					<div class="metric-value">` + formatFloat(metrics.Efficiency.AvgCompressionRatio) + `</div>
					<div class="metric-label">Compression Ratio</div>
				</div>
				<div class="metric-box">
					<div class="metric-value">` + formatFloat(metrics.Efficiency.AvgSavedPerQuery) + `</div>
					<div class="metric-label">Avg Saved/Query</div>
				</div>
			</div>
		</div>
`
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

func formatFloat(f float64) string {
	return fmt.Sprintf("%.2f", f)
}

func escapeHTML(s string) string {
	s = strings.ReplaceAll(s, "&", "&amp;")
	s = strings.ReplaceAll(s, "<", "&lt;")
	s = strings.ReplaceAll(s, ">", "&gt;")
	s = strings.ReplaceAll(s, "\"", "&quot;")
	return s
}

func resolveDashboardRuntimePort(serverAddr, requestHost string) int {
	parse := func(v string) int {
		if v == "" {
			return 0
		}
		if strings.Contains(v, ":") {
			_, portStr, err := net.SplitHostPort(v)
			if err == nil {
				if p, err := strconv.Atoi(portStr); err == nil {
					return p
				}
			}
		}
		if p, err := strconv.Atoi(v); err == nil {
			return p
		}
		return 0
	}

	if p := parse(requestHost); p > 0 {
		return p
	}
	if p := parse(serverAddr); p > 0 {
		return p
	}
	return 8765
}

func detectConnectedAgents(runtimePort int) []string {
	agents := attach.DetectAgents()
	connected := make([]string, 0, len(agents))
	for _, a := range agents {
		if attach.IsAttached(a.Type, runtimePort) {
			connected = append(connected, a.Name)
		}
	}
	return connected
}
