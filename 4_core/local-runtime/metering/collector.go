// metering/collector.go - Metering event collection and aggregation
// Aligns with RUNTIME_ARCHITECTURE.md Section 10
// NOTE: This package does NOT import "app" to avoid circular dependency
package metering

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// Collector collects and aggregates metering events
type Collector struct {
	db             *sql.DB
	mu             sync.Mutex
	runtimeVersion string
}

// NewCollector creates a new metering collector
func NewCollector(db *sql.DB, runtimeVersion string) *Collector {
	return &Collector{
		db:             db,
		runtimeVersion: runtimeVersion,
	}
}

// Record records a metering event
func (c *Collector) Record(event *Event) error {
	c.mu.Lock()
	defer c.mu.Unlock()

	query := `
	INSERT INTO metering_events (
		event_id, request_id, event_type, tenant_id, user_id, workspace_id, agent_id,
		scope, sharing_mode, input_tokens, compressed_tokens, saved_tokens,
		query_count, recall_hits, recall_hit_rate, timestamp, runtime_version, store_type,
		raw_tokens, assembled_hits, context_strategy, context_mode,
		compile_strategy_policy_version, compile_strategy_policy_source,
		context_strategy_requested, context_strategy_resolved, context_mode_resolved
	) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err := c.db.Exec(query,
		event.EventID,
		event.RequestID,
		event.EventType,
		event.TenantID,
		event.UserID,
		event.WorkspaceID,
		event.AgentID,
		event.Scope,
		event.SharingMode,
		event.InputTokens,
		event.CompressedTokens,
		event.SavedTokens,
		event.QueryCount,
		event.RecallHits,
		event.RecallHitRate,
		event.Timestamp,
		event.RuntimeVersion,
		event.StoreType,
		event.RawTokens,
		event.AssembledHits,
		event.ContextStrategy,
		event.ContextMode,
		event.CompileStrategyPolicyVersion,
		event.CompileStrategyPolicySource,
		event.ContextStrategyRequested,
		event.ContextStrategyResolved,
		event.ContextModeResolved,
	)

	return err
}

// MetricsData holds raw aggregated metrics from DB
type MetricsData struct {
	Totals      TotalsData
	ByScope     []ScopeData
	ByDay       []DayData
	ByWorkspace []WorkspaceData
	ByAgent     []AgentData
	// Time-range savings (Phase 3)
	TodaySavedTokens int64
	WeekSavedTokens  int64
	MonthSavedTokens int64
	// Efficiency (Phase 3)
	AvgCompressionRatio float64
	AvgSavedPerQuery    float64
	// Demo detection (Phase 3.5)
	DemoEventsOccurred bool
}

// TotalsData holds raw totals
type TotalsData struct {
	MemoryCount           int64
	TotalWrites           int64
	TotalQueries          int64
	TotalInputTokens      int64
	TotalCompressedTokens int64
	TotalSavedTokens      int64
	TotalQueryCount       int64
	TotalRecallHits       int64
}

// ScopeData holds raw per-scope metrics
type ScopeData struct {
	Scope       string
	AgentID     string
	WorkspaceID string
	SavedTokens int64
	WriteCount  int64
}

// DayData holds raw daily metrics
type DayData struct {
	Date        string
	SavedTokens int64
	QueryCount  int64
}

// WorkspaceData holds raw per-workspace metrics (Phase 3)
type WorkspaceData struct {
	WorkspaceID string
	SavedTokens int64
	QueryCount  int64
}

// AgentData holds raw per-agent metrics (Phase 3)
type AgentData struct {
	AgentID     string
	SavedTokens int64
}

// GetMetricsData returns raw aggregated metrics
func (c *Collector) GetMetricsData(ctx context.Context) (*MetricsData, error) {
	data := &MetricsData{}

	// Get totals
	totalsQuery := `
	SELECT
		(SELECT COUNT(*) FROM memories) as memory_count,
		COALESCE(SUM(CASE WHEN event_type = 'memory_write' THEN 1 ELSE 0 END), 0) as total_writes,
		COALESCE(SUM(CASE WHEN event_type = 'memory_query' THEN 1 ELSE 0 END), 0) as total_queries,
		COALESCE(SUM(input_tokens), 0) as total_input,
		COALESCE(SUM(compressed_tokens), 0) as total_compressed,
		COALESCE(SUM(saved_tokens), 0) as total_saved,
		COALESCE(SUM(query_count), 0) as total_query_count,
		COALESCE(SUM(recall_hits), 0) as total_recall_hits
	FROM metering_events
	`

	err := c.db.QueryRowContext(ctx, totalsQuery).Scan(
		&data.Totals.MemoryCount,
		&data.Totals.TotalWrites,
		&data.Totals.TotalQueries,
		&data.Totals.TotalInputTokens,
		&data.Totals.TotalCompressedTokens,
		&data.Totals.TotalSavedTokens,
		&data.Totals.TotalQueryCount,
		&data.Totals.TotalRecallHits,
	)
	if err != nil && err != sql.ErrNoRows {
		return nil, fmt.Errorf("failed to get totals: %w", err)
	}

	// Get by-scope metrics
	byScopeQuery := `
	SELECT scope, agent_id, workspace_id,
		COALESCE(SUM(saved_tokens), 0) as saved,
		COALESCE(SUM(CASE WHEN event_type = 'memory_write' THEN 1 ELSE 0 END), 0) as write_count
	FROM metering_events
	GROUP BY scope, agent_id, workspace_id
	`

	rows, err := c.db.QueryContext(ctx, byScopeQuery)
	if err != nil {
		return nil, fmt.Errorf("failed to get by-scope metrics: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		var sd ScopeData
		if err := rows.Scan(&sd.Scope, &sd.AgentID, &sd.WorkspaceID, &sd.SavedTokens, &sd.WriteCount); err != nil {
			continue
		}
		data.ByScope = append(data.ByScope, sd)
	}

	// Get daily metrics
	byDayQuery := `
	SELECT
		date(replace(substr(timestamp, 1, 19), 'T', ' '), 'utc', 'localtime') as date,
		COALESCE(SUM(saved_tokens), 0) as saved,
		COALESCE(SUM(query_count), 0) as queries
	FROM metering_events
	GROUP BY date(replace(substr(timestamp, 1, 19), 'T', ' '), 'utc', 'localtime')
	ORDER BY date DESC
	LIMIT 30
	`

	rows2, err := c.db.QueryContext(ctx, byDayQuery)
	if err != nil {
		return nil, fmt.Errorf("failed to get daily metrics: %w", err)
	}
	defer rows2.Close()

	for rows2.Next() {
		var dd DayData
		if err := rows2.Scan(&dd.Date, &dd.SavedTokens, &dd.QueryCount); err != nil {
			continue
		}
		data.ByDay = append(data.ByDay, dd)
	}

	// Phase 3: Time-range savings (today, week, month)
	// Get "today" saved tokens as a rolling 24h window.
	// This avoids local timezone parsing edge cases across platforms.
	todayQuery := `
	SELECT COALESCE(SUM(saved_tokens), 0)
	FROM metering_events
	WHERE datetime(replace(substr(timestamp, 1, 19), 'T', ' '), 'utc') >= datetime('now', '-24 hours')
	`
	c.db.QueryRowContext(ctx, todayQuery).Scan(&data.TodaySavedTokens)

	// Get this week's saved tokens (last 7 days including today, local timezone)
	weekQuery := `
	SELECT COALESCE(SUM(saved_tokens), 0)
	FROM metering_events
	WHERE date(replace(substr(timestamp, 1, 19), 'T', ' '), 'utc', 'localtime') >= date('now', 'localtime', '-6 days')
	`
	c.db.QueryRowContext(ctx, weekQuery).Scan(&data.WeekSavedTokens)

	// Get this month's saved tokens (last 30 days including today, local timezone)
	monthQuery := `
	SELECT COALESCE(SUM(saved_tokens), 0)
	FROM metering_events
	WHERE date(replace(substr(timestamp, 1, 19), 'T', ' '), 'utc', 'localtime') >= date('now', 'localtime', '-29 days')
	`
	c.db.QueryRowContext(ctx, monthQuery).Scan(&data.MonthSavedTokens)

	// Phase 3: By-workspace breakdown
	byWorkspaceQuery := `
	SELECT workspace_id,
		COALESCE(SUM(saved_tokens), 0) as saved,
		COALESCE(SUM(query_count), 0) as queries
	FROM metering_events
	WHERE workspace_id IS NOT NULL AND workspace_id != ''
	GROUP BY workspace_id
	`
	rowsW, err := c.db.QueryContext(ctx, byWorkspaceQuery)
	if err == nil {
		defer rowsW.Close()
		for rowsW.Next() {
			var wd WorkspaceData
			if err := rowsW.Scan(&wd.WorkspaceID, &wd.SavedTokens, &wd.QueryCount); err != nil {
				continue
			}
			data.ByWorkspace = append(data.ByWorkspace, wd)
		}
	}

	// Phase 3: By-agent breakdown
	byAgentQuery := `
	SELECT agent_id,
		COALESCE(SUM(saved_tokens), 0) as saved
	FROM metering_events
	WHERE agent_id IS NOT NULL AND agent_id != ''
	GROUP BY agent_id
	`
	rowsA, err := c.db.QueryContext(ctx, byAgentQuery)
	if err == nil {
		defer rowsA.Close()
		for rowsA.Next() {
			var ad AgentData
			if err := rowsA.Scan(&ad.AgentID, &ad.SavedTokens); err != nil {
				continue
			}
			data.ByAgent = append(data.ByAgent, ad)
		}
	}

	// Phase 3: Efficiency metrics
	// Avg compression ratio = total_compressed / total_input (for events with input_tokens > 0)
	efficiencyQuery := `
	SELECT
		COALESCE(AVG(CASE WHEN input_tokens > 0 THEN CAST(compressed_tokens AS FLOAT) / input_tokens ELSE 0 END), 0) as avg_compression,
		COALESCE(AVG(CASE WHEN query_count > 0 THEN CAST(saved_tokens AS FLOAT) / query_count ELSE 0 END), 0) as avg_saved_per_query
	FROM metering_events
	WHERE event_type = 'memory_search'
	`
	c.db.QueryRowContext(ctx, efficiencyQuery).Scan(&data.AvgCompressionRatio, &data.AvgSavedPerQuery)

	// Phase 3.5: Demo data detection
	// Check if demo query has been run (demo marker exists in data dir)
	data.DemoEventsOccurred = checkDemoMarker()

	return data, nil
}

// GetSavedTokensSince returns saved token sum since a timestamp (inclusive).
// This is used for runtime-session counters that reset after process restart.
func (c *Collector) GetSavedTokensSince(ctx context.Context, since time.Time) (int64, error) {
	var total int64
	query := `
	SELECT COALESCE(SUM(saved_tokens), 0)
	FROM metering_events
	WHERE datetime(replace(substr(timestamp, 1, 19), 'T', ' '), 'utc') >= datetime(?)
	`
	if err := c.db.QueryRowContext(ctx, query, since.UTC().Format("2006-01-02 15:04:05")).Scan(&total); err != nil {
		return 0, err
	}
	return total, nil
}

// checkDemoMarker checks if demo data has been seeded
func checkDemoMarker() bool {
	markerFile, ok := resolveBootstrapMarkerPath()
	if !ok {
		return false
	}
	_, err := os.Stat(markerFile)
	return err == nil
}

func resolveBootstrapMarkerPath() (string, bool) {
	// Keep this package independent from internal/runtime to avoid extra coupling.
	dataDir := strings.TrimSpace(os.Getenv("OMNIMEMORA_RUNTIME_DATA_DIR"))
	if dataDir == "" {
		dataDir = strings.TrimSpace(os.Getenv("OMNIMEMORA_DATA_DIR"))
	}
	if dataDir == "" {
		homeDir, err := os.UserHomeDir()
		if err != nil {
			return "", false
		}
		dataDir = filepath.Join(homeDir, ".omnimemora")
	}
	dataDir = filepath.Clean(os.ExpandEnv(dataDir))
	return filepath.Join(dataDir, "bootstrap", "first_run_done"), true
}

// GetTotals returns basic totals for health check
func (c *Collector) GetTotals(ctx context.Context) (*TotalsData, error) {
	query := `
	SELECT
		COALESCE(SUM(input_tokens), 0),
		COALESCE(SUM(compressed_tokens), 0),
		COALESCE(SUM(saved_tokens), 0),
		COALESCE(SUM(query_count), 0),
		COALESCE(SUM(recall_hits), 0)
	FROM metering_events
	`

	var totals TotalsData
	err := c.db.QueryRowContext(ctx, query).Scan(
		&totals.TotalInputTokens,
		&totals.TotalCompressedTokens,
		&totals.TotalSavedTokens,
		&totals.TotalQueryCount,
		&totals.TotalRecallHits,
	)
	if err != nil && err != sql.ErrNoRows {
		return nil, err
	}

	return &totals, nil
}
