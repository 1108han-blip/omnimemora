// store/store.go - Store interface abstraction layer
// Aligns with RUNTIME_ARCHITECTURE.md Section 8.2
// CRITICAL: Business logic must only use this interface, never direct SQL
package store

import (
	"context"
	"time"

	"github.com/omnimemora/local-runtime/pkg"
)

// Store is the storage abstraction interface
// All backend implementations must satisfy this interface
type Store interface {
	// Write stores a memory record
	Write(ctx context.Context, record *pkg.MemoryRecord) error

	// Query performs search within scope (uses FTS5 if available)
	Query(ctx context.Context, req *QueryRequest) (*QueryResult, error)

	// Search performs keyword search within scope (FTS5)
	Search(ctx context.Context, req *SearchRequest) (*SearchResult, error)

	// QueryByHash finds a record by content hash within scope (for dedup)
	QueryByHash(ctx context.Context, contentHash string, scopeRef *pkg.ScopeRef) (string, error)

	// Delete removes a memory record
	Delete(ctx context.Context, memoryID string, scopeRef *pkg.ScopeRef) error

	// Count returns the total number of memory records
	Count(ctx context.Context) (int64, error)

	// Close releases store resources
	Close() error
}

// QueryRequest represents a query request to the store
type QueryRequest struct {
	Query     string
	ScopeRef  *pkg.ScopeRef
	Limit     int
	RequestID string
}

// QueryResult represents query results from the store
type QueryResult struct {
	Results []QueryMatch
	Total   int
}

// SearchRequest represents a search request to the store
type SearchRequest struct {
	Keyword           string
	ScopeRef          *pkg.ScopeRef
	Limit             int
	RequestID         string
	IncludeBreakdown  bool
}

// SearchResult represents search results from the store
type SearchResult struct {
	Results []SearchCandidate
	Total   int
}

// SearchCandidate represents a candidate from the store before ranking
type SearchCandidate struct {
	MemoryID       string
	Content        string
	Metadata       map[string]any
	CreatedAt      time.Time
	UpdatedAt      time.Time
	LastAccessedAt *time.Time
	AccessCount    int
	RawTextScore   float64 // BM25 score if available, otherwise 0
}

// QueryMatch represents a single query match
type QueryMatch struct {
	MemoryID  string
	Content   string
	Score     float64
	Scope     pkg.ScopeType
	CreatedAt time.Time
	Metadata  map[string]any
}

// SearchCapabilities represents search engine capabilities
type SearchCapabilities struct {
	FTS5Enabled   bool
	BM25Available bool
}
