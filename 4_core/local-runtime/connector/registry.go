// connector/registry.go - Connector registry with SQLite persistence
// Aligns with RUNTIME_ARCHITECTURE.md Section 11.3
package connector

import (
	"database/sql"
	"fmt"
	"sync"
	"time"
)

// Registry manages connector registrations with SQLite persistence
type Registry struct {
	mu         sync.RWMutex
	connectors map[string]*Info
	db         *sql.DB
}

// NewRegistry creates a new connector registry
func NewRegistry() *Registry {
	return &Registry{
		connectors: make(map[string]*Info),
	}
}

// NewRegistryWithDB creates a new connector registry with SQLite persistence
func NewRegistryWithDB(db *sql.DB) (*Registry, error) {
	registry := &Registry{
		connectors: make(map[string]*Info),
		db:         db,
	}

	// Initialize schema
	if err := registry.initSchema(); err != nil {
		return nil, err
	}

	// Load existing connectors from DB
	if err := registry.loadFromDB(); err != nil {
		return nil, err
	}

	return registry, nil
}

// initSchema creates the connectors table if not exists
func (r *Registry) initSchema() error {
	if r.db == nil {
		return nil
	}

	query := `
	CREATE TABLE IF NOT EXISTS connectors (
		connector_id TEXT PRIMARY KEY,
		agent_id TEXT NOT NULL,
		connector_type TEXT NOT NULL DEFAULT 'http',
		workspace_id TEXT NOT NULL DEFAULT 'default',
		status TEXT NOT NULL DEFAULT 'active',
		registered_at DATETIME NOT NULL
	);
	CREATE INDEX IF NOT EXISTS idx_connectors_agent ON connectors(agent_id);
	CREATE INDEX IF NOT EXISTS idx_connectors_workspace ON connectors(workspace_id);
	`

	_, err := r.db.Exec(query)
	return err
}

// loadFromDB loads existing connectors from database
func (r *Registry) loadFromDB() error {
	if r.db == nil {
		return nil
	}

	rows, err := r.db.Query("SELECT connector_id, agent_id, connector_type, workspace_id, status, registered_at FROM connectors")
	if err != nil {
		return err
	}
	defer rows.Close()

	for rows.Next() {
		var info Info
		if err := rows.Scan(&info.ConnectorID, &info.AgentID, &info.ConnectorType, &info.WorkspaceID, &info.Status, &info.RegisteredAt); err != nil {
			continue
		}
		r.connectors[info.ConnectorID] = &info
	}

	return nil
}

// Register registers a new connector
func (r *Registry) Register(req *RegisterRequest) (*RegisterResponse, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if req.ConnectorID == "" {
		return nil, fmt.Errorf("connector_id is required")
	}
	if req.AgentID == "" {
		return nil, fmt.Errorf("agent_id is required")
	}
	if req.ConnectorType == "" {
		req.ConnectorType = "http" // Default type
	}
	if req.WorkspaceID == "" {
		req.WorkspaceID = "default"
	}

	info := &Info{
		ConnectorID:   req.ConnectorID,
		AgentID:       req.AgentID,
		ConnectorType: req.ConnectorType,
		WorkspaceID:   req.WorkspaceID,
		Status:        "active",
		RegisteredAt:  time.Now().UTC(),
	}

	r.connectors[req.ConnectorID] = info

	// Persist to DB if available
	if r.db != nil {
		query := `INSERT OR REPLACE INTO connectors (connector_id, agent_id, connector_type, workspace_id, status, registered_at) VALUES (?, ?, ?, ?, ?, ?)`
		_, err := r.db.Exec(query, info.ConnectorID, info.AgentID, info.ConnectorType, info.WorkspaceID, info.Status, info.RegisteredAt)
		if err != nil {
			// Log but don't fail - registry still works in-memory
			fmt.Printf("connector persist error: %v\n", err)
		}
	}

	return &RegisterResponse{
		ConnectorID:  info.ConnectorID,
		Status:       info.Status,
		RegisteredAt: info.RegisteredAt,
	}, nil
}

// Deregister removes a connector from the registry
func (r *Registry) Deregister(connectorID string) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, ok := r.connectors[connectorID]; !ok {
		return fmt.Errorf("connector not found: %s", connectorID)
	}

	delete(r.connectors, connectorID)

	// Remove from DB if available
	if r.db != nil {
		_, err := r.db.Exec("DELETE FROM connectors WHERE connector_id = ?", connectorID)
		if err != nil {
			fmt.Printf("connector delete error: %v\n", err)
		}
	}

	return nil
}

// List returns all registered connectors
func (r *Registry) List() []*Info {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]*Info, 0, len(r.connectors))
	for _, info := range r.connectors {
		result = append(result, info)
	}
	return result
}

// Get returns a specific connector
func (r *Registry) Get(connectorID string) (*Info, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	info, ok := r.connectors[connectorID]
	return info, ok
}

// Count returns the number of registered connectors
func (r *Registry) Count() int {
	r.mu.RLock()
	defer r.mu.RUnlock()
	return len(r.connectors)
}
