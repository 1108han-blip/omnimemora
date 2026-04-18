// api/server.go - HTTP server setup and configuration
// Aligns with RUNTIME_ARCHITECTURE.md Section 7
package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"sync/atomic"
	"time"

	"github.com/google/uuid"
	"github.com/omnimemora/local-runtime/app"
	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/connector"
	"github.com/omnimemora/local-runtime/lifecycle"
	"github.com/omnimemora/local-runtime/metering"
	"github.com/omnimemora/local-runtime/scope"
	storepkg "github.com/omnimemora/local-runtime/store"
)

// Server is the HTTP API server
type Server struct {
	httpServer                        *http.Server
	cfg                               *config.RuntimeConfig
	service                           *app.Service
	registry                          *connector.Registry
	scopeModel                        *scope.Model
	metering                          *metering.Collector
	rtCtx                             *lifecycle.RuntimeContext
	bootstrap                         *bootstrapState // Phase 3.6: bootstrap/control state carrier
	mcpMu                             sync.RWMutex
	mcpSessions                       map[string]*mcpSession
	mcpHandshakeCount                 int64
	mcpToolCallCount                  int64
	mcpMemoryWriteCount               int64
	mcpMemorySearchContextRecallCount int64
	mcpLastStartupError               string
}

// NewServer creates a new API server
func NewServer(cfg *config.RuntimeConfig, store storepkg.Store, rtCtx *lifecycle.RuntimeContext, port int) *Server {
	var meteringCollector *metering.Collector
	if sqliteStore, ok := store.(*storepkg.SQLiteStore); ok {
		meteringCollector = metering.NewCollector(sqliteStore.DB(), cfg.Version)
	} else {
		meteringCollector = metering.NewCollector(nil, cfg.Version)
	}

	svc := app.NewService(cfg, store, meteringCollector)
	scopeModel := scope.NewModel(cfg)
	scopeResolver := scope.NewResolver(cfg)

	// Create connector registry with SQLite persistence if available
	var registry *connector.Registry
	if sqliteStore, ok := store.(*storepkg.SQLiteStore); ok {
		registry, _ = connector.NewRegistryWithDB(sqliteStore.DB())
	}
	if registry == nil {
		registry = connector.NewRegistry()
	}

	server := &Server{
		cfg:         cfg,
		service:     svc,
		registry:    registry,
		scopeModel:  scopeModel,
		metering:    meteringCollector,
		rtCtx:       rtCtx,
		bootstrap:   newBootstrapState(),
		mcpSessions: make(map[string]*mcpSession),
	}

	mux := http.NewServeMux()

	// Apply middleware
	var handler http.Handler = mux
	handler = requestIDMiddleware(handler)
	handler = loggingMiddleware(handler)
	handler = scopeMiddleware(handler, scopeResolver)

	// Register routes
	registerRootRoutes(mux, server)
	mux.HandleFunc("GET /health", server.handleHealth)
	mux.HandleFunc("GET /metrics", server.handleMetrics)
	registerOperatorDashboardRoutes(mux, server)
	registerControlCarrierRoutes(mux, server)
	registerInstallControlRoutes(mux, server)
	mux.HandleFunc("GET /sse", server.handleMCPSSE)
	mux.HandleFunc("GET /mcp", server.handleMCPSSE)
	mux.HandleFunc("GET /mcp/sse", server.handleMCPSSE)
	mux.HandleFunc("POST /mcp", server.handleMCPHTTP)
	mux.HandleFunc("POST /messages", server.handleMCPMessages)
	mux.HandleFunc("POST /mcp/messages", server.handleMCPMessages)
	mux.HandleFunc("POST /memory/write", server.handleWrite)
	mux.HandleFunc("POST /memory/query", server.handleQuery)
	mux.HandleFunc("POST /memory/search", server.handleSearch)
	mux.HandleFunc("POST /memory/delete", server.handleDelete)
	mux.HandleFunc("POST /connector/register", server.handleConnectorRegister)
	mux.HandleFunc("GET /connector/list", server.handleConnectorList)
	registerBootstrapRoutes(mux, server)

	server.httpServer = &http.Server{
		Addr:         fmt.Sprintf("%s:%d", cfg.Local.Endpoint, port),
		Handler:      handler,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	return server
}

// ListenAndServe starts the HTTP server
func (s *Server) ListenAndServe() error {
	return s.httpServer.ListenAndServe()
}

// Shutdown gracefully shuts down the server
func (s *Server) Shutdown(ctx context.Context) error {
	return s.httpServer.Shutdown(ctx)
}

// Handler returns the HTTP handler for testing
func (s *Server) Handler() http.Handler {
	return s.httpServer.Handler
}

// writeJSON writes JSON response
func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// writeError writes error response
func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, app.ErrorResponse{
		Error: message,
		Code:  code,
	})
}

// generateRequestID generates a unique request ID
func generateRequestID() string {
	return fmt.Sprintf("req_%s", uuid.New().String()[:8])
}

func (s *Server) recordMCPHandshake() {
	atomic.AddInt64(&s.mcpHandshakeCount, 1)
}

func (s *Server) recordMCPToolCall() {
	atomic.AddInt64(&s.mcpToolCallCount, 1)
}

func (s *Server) getMCPStats() (handshakes int64, toolCalls int64) {
	return atomic.LoadInt64(&s.mcpHandshakeCount), atomic.LoadInt64(&s.mcpToolCallCount)
}

func (s *Server) recordMCPToolCallByName(name string) {
	atomic.AddInt64(&s.mcpToolCallCount, 1)
	isWrite, isSearchContextRecall := classifyMCPToolCall(name)
	if isWrite {
		atomic.AddInt64(&s.mcpMemoryWriteCount, 1)
	}
	if isSearchContextRecall {
		atomic.AddInt64(&s.mcpMemorySearchContextRecallCount, 1)
	}
}

func classifyMCPToolCall(name string) (isWrite bool, isSearchContextRecall bool) {
	switch name {
	case "omnimemora_write_memory", "memory.write", "memory.store":
		return true, false
	case "omnimemora_search_memory", "memory.search", "memory.context", "memory.recall":
		return false, true
	default:
		return false, false
	}
}

func (s *Server) getMCPDetailedStats() (handshakes int64, toolCalls int64, writeCalls int64, searchContextRecallCalls int64) {
	return atomic.LoadInt64(&s.mcpHandshakeCount),
		atomic.LoadInt64(&s.mcpToolCallCount),
		atomic.LoadInt64(&s.mcpMemoryWriteCount),
		atomic.LoadInt64(&s.mcpMemorySearchContextRecallCount)
}

func (s *Server) setMCPStartupError(msg string) {
	s.mcpMu.Lock()
	s.mcpLastStartupError = msg
	s.mcpMu.Unlock()
}

func (s *Server) getMCPStartupError() string {
	s.mcpMu.RLock()
	defer s.mcpMu.RUnlock()
	return s.mcpLastStartupError
}
