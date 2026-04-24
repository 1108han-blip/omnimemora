// store/sqlite_store.go - SQLite implementation of Store interface
// Uses SQLite with FTS5 for full-text search
// This is the MVP default implementation per RUNTIME_ARCHITECTURE.md Section 8.3
package store

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/omnimemora/local-runtime/pkg"
	_ "modernc.org/sqlite"
)

// SQLiteStore implements Store using SQLite + FTS5
type SQLiteStore struct {
	dbPath      string
	db          *sql.DB
	capabilities SearchCapabilities
}

// NewSQLiteStore creates a new SQLite store
func NewSQLiteStore(dataPath string) (*SQLiteStore, error) {
	// Expand path
	if strings.HasPrefix(dataPath, "~/") {
		home, err := os.UserHomeDir()
		if err == nil {
			dataPath = filepath.Join(home, dataPath[2:])
		}
	}
	dataPath = os.ExpandEnv(dataPath)

	// Ensure directory exists
	if err := os.MkdirAll(dataPath, 0755); err != nil {
		return nil, fmt.Errorf("failed to create data directory: %w", err)
	}

	dbPath := filepath.Join(dataPath, "memory.db")
	db, err := sql.Open("sqlite", dbPath+"?_journal_mode=WAL&_busy_timeout=5000")
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	store := &SQLiteStore{
		dbPath: dbPath,
		db:     db,
		capabilities: SearchCapabilities{
			FTS5Enabled:   false,
			BM25Available: false,
		},
	}

	if err := store.migrate(); err != nil {
		db.Close()
		return nil, fmt.Errorf("migration failed: %w", err)
	}

	// Detect capabilities after migration
	store.detectCapabilities()

	return store, nil
}

// migrate creates the required tables
func (s *SQLiteStore) migrate() error {
	// Create main memory table
	memoryTable := `
	CREATE TABLE IF NOT EXISTS memories (
		memory_id TEXT PRIMARY KEY,
		content TEXT NOT NULL,
		content_hash TEXT NOT NULL,
		metadata TEXT,
		tenant_id TEXT NOT NULL DEFAULT '',
		user_id TEXT NOT NULL DEFAULT '',
		workspace_id TEXT NOT NULL DEFAULT '',
		agent_id TEXT NOT NULL DEFAULT '',
		scope TEXT NOT NULL DEFAULT 'agent',
		sharing_mode TEXT NOT NULL DEFAULT 'isolated',
		created_at DATETIME NOT NULL,
		updated_at DATETIME NOT NULL,
		last_accessed_at DATETIME,
		expires_at DATETIME,
		access_count INTEGER NOT NULL DEFAULT 0
	);
	CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope);
	CREATE INDEX IF NOT EXISTS idx_memories_agent ON memories(agent_id);
	CREATE INDEX IF NOT EXISTS idx_memories_workspace ON memories(workspace_id);
	CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);
	CREATE INDEX IF NOT EXISTS idx_memories_hash ON memories(content_hash);
	`

	if _, err := s.db.Exec(memoryTable); err != nil {
		return fmt.Errorf("failed to create memory table: %w", err)
	}

	// Create FTS5 virtual table for full-text search
	ftsTable := `
	CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
		memory_id,
		content,
		content='memories',
		content_rowid='rowid'
	);
	`

	if _, err := s.db.Exec(ftsTable); err != nil {
		// FTS5 might not be available on all SQLite builds
		// Continue without FTS - search will fall back to LIKE
		fmt.Printf("FTS5 warning (non-critical): %v\n", err)
	}

	// Create trigger to keep FTS in sync (if FTS available)
	trigger := `
	CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
		INSERT INTO memories_fts(rowid, memory_id, content) VALUES (new.rowid, new.memory_id, new.content);
	END;
	`
	if _, err := s.db.Exec(trigger); err != nil {
		// Trigger might fail if FTS not available, continue
	}

	// Create metering events table
	meteringTable := `
	CREATE TABLE IF NOT EXISTS metering_events (
		event_id TEXT PRIMARY KEY,
		request_id TEXT NOT NULL,
		event_type TEXT NOT NULL,
		tenant_id TEXT NOT NULL DEFAULT '',
		user_id TEXT NOT NULL DEFAULT '',
		workspace_id TEXT NOT NULL DEFAULT '',
		agent_id TEXT NOT NULL DEFAULT '',
		scope TEXT NOT NULL DEFAULT 'agent',
		sharing_mode TEXT NOT NULL DEFAULT 'isolated',
		input_tokens INTEGER NOT NULL DEFAULT 0,
		compressed_tokens INTEGER NOT NULL DEFAULT 0,
		saved_tokens INTEGER NOT NULL DEFAULT 0,
		query_count INTEGER NOT NULL DEFAULT 0,
		recall_hits INTEGER NOT NULL DEFAULT 0,
		recall_hit_rate REAL NOT NULL DEFAULT 0,
		timestamp DATETIME NOT NULL,
		runtime_version TEXT NOT NULL DEFAULT '',
		store_type TEXT NOT NULL DEFAULT ''
	);
	CREATE INDEX IF NOT EXISTS idx_metering_timestamp ON metering_events(timestamp);
	CREATE INDEX IF NOT EXISTS idx_metering_agent ON metering_events(agent_id);
	CREATE INDEX IF NOT EXISTS idx_metering_tenant ON metering_events(tenant_id);
	`

	if _, err := s.db.Exec(meteringTable); err != nil {
		return fmt.Errorf("failed to create metering table: %w", err)
	}

	// Phase 2b: Add missing columns to metering_events if they don't exist
	if err := s.migrateMeteringPhase2b(); err != nil {
		return fmt.Errorf("metering phase 2b migration failed: %w", err)
	}

	return nil
}

// Write stores a memory record
func (s *SQLiteStore) Write(ctx context.Context, record *pkg.MemoryRecord) error {
	metadataJSON := ""
	if record.Metadata != nil {
		// Simple JSON serialization - in production use proper JSON library
		metadataJSON = fmt.Sprintf("%v", record.Metadata)
	}

	query := `
	INSERT INTO memories (memory_id, content, content_hash, metadata, tenant_id, user_id, workspace_id, agent_id, scope, sharing_mode, created_at, updated_at, expires_at, access_count)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`

	_, err := s.db.ExecContext(ctx, query,
		record.MemoryID,
		record.Content,
		record.ContentHash,
		metadataJSON,
		record.ScopeRef.TenantID,
		record.ScopeRef.UserID,
		record.ScopeRef.WorkspaceID,
		record.ScopeRef.AgentID,
		string(record.ScopeRef.Scope),
		string(record.ScopeRef.SharingMode),
		record.CreatedAt,
		record.UpdatedAt,
		record.ExpiresAt,
		record.AccessCount,
	)

	if err != nil {
		return fmt.Errorf("failed to write memory: %w", err)
	}

	return nil
}

// Query performs search within scope
func (s *SQLiteStore) Query(ctx context.Context, req *QueryRequest) (*QueryResult, error) {
	limit := req.Limit
	if limit <= 0 {
		limit = 10
	}

	// Build scope filter
	scopeFilter, args := buildScopeFilter(req.ScopeRef, req.Query)

	query := fmt.Sprintf(`
	SELECT memory_id, content, scope, created_at, metadata
	FROM memories
	WHERE %s
	ORDER BY created_at DESC
	LIMIT ?
	`, scopeFilter)

	args = append(args, limit)

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("query failed: %w", err)
	}
	defer rows.Close()

	results := &QueryResult{
		Results: []QueryMatch{},
	}

	for rows.Next() {
		var match QueryMatch
		var metadata string
		if err := rows.Scan(&match.MemoryID, &match.Content, &match.Scope, &match.CreatedAt, &metadata); err != nil {
			continue
		}
		match.Score = 1.0 // MVP: all matches score 1.0
		results.Results = append(results.Results, match)
	}

	results.Total = len(results.Results)
	return results, nil
}

// Search performs keyword search within scope using FTS5
// Returns candidates for app-layer ranking
func (s *SQLiteStore) Search(ctx context.Context, req *SearchRequest) (*SearchResult, error) {
	limit := req.Limit
	if limit <= 0 {
		limit = 10
	}

	// Candidate limit is larger than final limit to give ranking room
	candidateLimit := limit * 3
	if candidateLimit < 20 {
		candidateLimit = 20
	}

	// Build scope filter
	scopeFilter, args := buildScopeFilter(req.ScopeRef, "")

	// Try FTS5 search first, fall back to LIKE
	var rows *sql.Rows
	var err error

	if s.capabilities.FTS5Enabled {
		// FTS5 MATCH query
		ftsQuery := fmt.Sprintf(`
		SELECT m.memory_id, m.content, m.metadata, m.created_at, m.updated_at, m.last_accessed_at, m.access_count
		FROM memories m
		WHERE %s AND m.memory_id IN (SELECT memory_id FROM memories_fts WHERE memories_fts MATCH ?)
		ORDER BY m.created_at DESC
		LIMIT ?
		`, scopeFilter)

		ftsArgs := append(args, req.Keyword, candidateLimit)
		rows, err = s.db.QueryContext(ctx, ftsQuery, ftsArgs...)
	}

	// LIKE fallback (disabled FTS5 or FTS5 query syntax/runtime error)
	if err != nil || !s.capabilities.FTS5Enabled {
		likeQuery := fmt.Sprintf(`
		SELECT memory_id, content, metadata, created_at, updated_at, last_accessed_at, access_count
		FROM memories
		WHERE %s AND content LIKE ?
		ORDER BY created_at DESC
		LIMIT ?
		`, scopeFilter)

		likeArgs := append(args, "%"+req.Keyword+"%", candidateLimit)
		rows, err = s.db.QueryContext(ctx, likeQuery, likeArgs...)
	}

	if err != nil {
		return nil, fmt.Errorf("search failed: %w", err)
	}
	defer rows.Close()

	results := &SearchResult{
		Results: []SearchCandidate{},
	}

	for rows.Next() {
		var candidate SearchCandidate
		var metadata string
		var lastAccessedAt sql.NullTime
		if err := rows.Scan(&candidate.MemoryID, &candidate.Content, &metadata, &candidate.CreatedAt, &candidate.UpdatedAt, &lastAccessedAt, &candidate.AccessCount); err != nil {
			continue
		}
		if lastAccessedAt.Valid {
			candidate.LastAccessedAt = &lastAccessedAt.Time
		}
		candidate.RawTextScore = 0 // Will be set by app layer if BM25 available
		results.Results = append(results.Results, candidate)
	}

	results.Total = len(results.Results)
	return results, nil
}

// QueryByHash finds a record by content hash within scope (for dedup)
// Includes tenant_id filtering for proper tenant isolation
func (s *SQLiteStore) QueryByHash(ctx context.Context, contentHash string, scopeRef *pkg.ScopeRef) (string, error) {
	query := `
	SELECT memory_id FROM memories
	WHERE content_hash = ?
	AND scope = ?
	AND agent_id = ?
	AND workspace_id = ?
	AND tenant_id = ?
	LIMIT 1
	`

	var memoryID string
	err := s.db.QueryRowContext(ctx, query,
		contentHash,
		string(scopeRef.Scope),
		scopeRef.AgentID,
		scopeRef.WorkspaceID,
		scopeRef.TenantID,
	).Scan(&memoryID)

	if err == sql.ErrNoRows {
		return "", nil
	}
	if err != nil {
		return "", fmt.Errorf("dedup query failed: %w", err)
	}

	return memoryID, nil
}

// Delete removes a memory record
// Enforces scope boundary: only creator can delete within their scope
func (s *SQLiteStore) Delete(ctx context.Context, memoryID string, scopeRef *pkg.ScopeRef) error {
	// Build scope-aware delete query
	// Must match the same scope filtering as Query
	switch scopeRef.Scope {
	case pkg.ScopeAgent:
		query := `DELETE FROM memories WHERE memory_id = ? AND scope = 'agent' AND tenant_id = ? AND agent_id = ?`
		_, err := s.db.ExecContext(ctx, query, memoryID, scopeRef.TenantID, scopeRef.AgentID)
		if err != nil {
			return fmt.Errorf("delete failed: %w", err)
		}
	case pkg.ScopeWorkspace:
		query := `DELETE FROM memories WHERE memory_id = ? AND scope = 'workspace' AND tenant_id = ? AND workspace_id = ?`
		_, err := s.db.ExecContext(ctx, query, memoryID, scopeRef.TenantID, scopeRef.WorkspaceID)
		if err != nil {
			return fmt.Errorf("delete failed: %w", err)
		}
	case pkg.ScopeUser:
		query := `DELETE FROM memories WHERE memory_id = ? AND scope = 'user' AND tenant_id = ? AND user_id = ?`
		_, err := s.db.ExecContext(ctx, query, memoryID, scopeRef.TenantID, scopeRef.UserID)
		if err != nil {
			return fmt.Errorf("delete failed: %w", err)
		}
	default:
		return fmt.Errorf("delete not supported for scope: %s", scopeRef.Scope)
	}
	return nil
}

// Count returns the total number of memory records
func (s *SQLiteStore) Count(ctx context.Context) (int64, error) {
	var count int64
	err := s.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM memories").Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("count failed: %w", err)
	}
	return count, nil
}

// Close releases store resources
func (s *SQLiteStore) Close() error {
	return s.db.Close()
}

// DB returns the underlying database connection for metering
func (s *SQLiteStore) DB() *sql.DB {
	return s.db
}

// GetCapabilities returns the search capabilities
func (s *SQLiteStore) GetCapabilities() SearchCapabilities {
	return s.capabilities
}

// migrateMeteringPhase2b adds Phase 2b metering columns if they don't exist
func (s *SQLiteStore) migrateMeteringPhase2b() error {
	// Check if raw_tokens column exists
	var colExists int
	err := s.db.QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='raw_tokens'").Scan(&colExists)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to check raw_tokens column: %w", err)
	}

	if colExists == 0 {
		// Add raw_tokens column
		if _, err := s.db.Exec("ALTER TABLE metering_events ADD COLUMN raw_tokens INTEGER NOT NULL DEFAULT 0"); err != nil {
			return fmt.Errorf("failed to add raw_tokens column: %w", err)
		}
	}

	// Check if assembled_hits column exists
	err = s.db.QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='assembled_hits'").Scan(&colExists)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to check assembled_hits column: %w", err)
	}

	if colExists == 0 {
		// Add assembled_hits column
		if _, err := s.db.Exec("ALTER TABLE metering_events ADD COLUMN assembled_hits INTEGER NOT NULL DEFAULT 0"); err != nil {
			return fmt.Errorf("failed to add assembled_hits column: %w", err)
		}
	}

	// Phase 3.6: Add context_strategy and context_mode columns
	err = s.db.QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='context_strategy'").Scan(&colExists)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to check context_strategy column: %w", err)
	}
	if colExists == 0 {
		if _, err := s.db.Exec("ALTER TABLE metering_events ADD COLUMN context_strategy TEXT NOT NULL DEFAULT ''"); err != nil {
			return fmt.Errorf("failed to add context_strategy column: %w", err)
		}
	}

	err = s.db.QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='context_mode'").Scan(&colExists)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to check context_mode column: %w", err)
	}
	if colExists == 0 {
		if _, err := s.db.Exec("ALTER TABLE metering_events ADD COLUMN context_mode TEXT NOT NULL DEFAULT ''"); err != nil {
			return fmt.Errorf("failed to add context_mode column: %w", err)
		}
	}

	// Phase CSP-001: Add compile strategy policy evidence columns
	err = s.db.QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='compile_strategy_policy_version'").Scan(&colExists)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to check compile_strategy_policy_version column: %w", err)
	}
	if colExists == 0 {
		if _, err := s.db.Exec("ALTER TABLE metering_events ADD COLUMN compile_strategy_policy_version TEXT NOT NULL DEFAULT ''"); err != nil {
			return fmt.Errorf("failed to add compile_strategy_policy_version column: %w", err)
		}
	}

	err = s.db.QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='compile_strategy_policy_source'").Scan(&colExists)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to check compile_strategy_policy_source column: %w", err)
	}
	if colExists == 0 {
		if _, err := s.db.Exec("ALTER TABLE metering_events ADD COLUMN compile_strategy_policy_source TEXT NOT NULL DEFAULT ''"); err != nil {
			return fmt.Errorf("failed to add compile_strategy_policy_source column: %w", err)
		}
	}

	err = s.db.QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='context_strategy_requested'").Scan(&colExists)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to check context_strategy_requested column: %w", err)
	}
	if colExists == 0 {
		if _, err := s.db.Exec("ALTER TABLE metering_events ADD COLUMN context_strategy_requested TEXT NOT NULL DEFAULT ''"); err != nil {
			return fmt.Errorf("failed to add context_strategy_requested column: %w", err)
		}
	}

	err = s.db.QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='context_strategy_resolved'").Scan(&colExists)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to check context_strategy_resolved column: %w", err)
	}
	if colExists == 0 {
		if _, err := s.db.Exec("ALTER TABLE metering_events ADD COLUMN context_strategy_resolved TEXT NOT NULL DEFAULT ''"); err != nil {
			return fmt.Errorf("failed to add context_strategy_resolved column: %w", err)
		}
	}

	err = s.db.QueryRow("SELECT COUNT(*) FROM pragma_table_info('metering_events') WHERE name='context_mode_resolved'").Scan(&colExists)
	if err != nil && err != sql.ErrNoRows {
		return fmt.Errorf("failed to check context_mode_resolved column: %w", err)
	}
	if colExists == 0 {
		if _, err := s.db.Exec("ALTER TABLE metering_events ADD COLUMN context_mode_resolved TEXT NOT NULL DEFAULT ''"); err != nil {
			return fmt.Errorf("failed to add context_mode_resolved column: %w", err)
		}
	}

	return nil
}

// detectCapabilities probes for FTS5 and BM25 availability
func (s *SQLiteStore) detectCapabilities() {
	// Probe for FTS5
	var ftsExists int
	err := s.db.QueryRow("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='memories_fts'").Scan(&ftsExists)
	if err == nil && ftsExists > 0 {
		s.capabilities.FTS5Enabled = true
	}

	// Probe for BM25 availability
	if s.capabilities.FTS5Enabled {
		var bm25Test float64
		err := s.db.QueryRow("SELECT bm25(memories_fts) FROM memories_fts LIMIT 1").Scan(&bm25Test)
		if err == nil {
			s.capabilities.BM25Available = true
		}
	}
}

// buildScopeFilter builds SQL filter from scope reference
// tenant_id is ALWAYS filtered - no cross-tenant visibility
func buildScopeFilter(scopeRef *pkg.ScopeRef, query string) (string, []any) {
	var conditions []string
	var args []any

	// CRITICAL: tenant_id filtering - no cross-tenant access
	if scopeRef.TenantID != "" {
		conditions = append(conditions, "tenant_id = ?")
		args = append(args, scopeRef.TenantID)
	} else {
		// If no tenant_id specified, filter by empty tenant (local mode)
		// This ensures tenant isolation in multi-tenant scenarios
		conditions = append(conditions, "(tenant_id = '' OR tenant_id IS NULL)")
	}

	// Always filter by scope boundaries
	switch scopeRef.Scope {
	case pkg.ScopeAgent:
		conditions = append(conditions, "agent_id = ?")
		args = append(args, scopeRef.AgentID)
		// Agent scope only sees agent memories (not workspace)
		conditions = append(conditions, "scope = 'agent'")
	case pkg.ScopeWorkspace:
		// Workspace scope sees workspace memories AND other agents' workspace memories
		// within the same workspace (that's the point of workspace scope)
		conditions = append(conditions, "workspace_id = ?")
		args = append(args, scopeRef.WorkspaceID)
		conditions = append(conditions, "scope = 'workspace'")
	case pkg.ScopeUser:
		conditions = append(conditions, "user_id = ?")
		args = append(args, scopeRef.UserID)
		conditions = append(conditions, "scope = 'user'")
	case pkg.ScopeCustom:
		// Custom scope not supported in MVP
		return "1=0", nil
	}

	// Add text search if query provided
	if query != "" {
		// Try FTS5 first, fall back to LIKE
		conditions = append(conditions, "memory_id IN (SELECT memory_id FROM memories_fts WHERE memories_fts MATCH ?)")
		args = append(args, query)
	}

	if len(conditions) == 0 {
		return "1=1", nil
	}

	return strings.Join(conditions, " AND "), args
}
