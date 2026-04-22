// api/routes.go - Memory-plane and runtime connector route handlers
// Aligns with RUNTIME_ARCHITECTURE.md Section 7
package api

import (
	"encoding/json"
	"net/http"

	"github.com/omnimemora/local-runtime/app"
	"github.com/omnimemora/local-runtime/connector"
	"github.com/omnimemora/local-runtime/pkg"
)

// handleHealth handles GET /health
func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	health, err := s.service.GetHealth(r.Context())
	if err != nil {
		writeError(w, 503, "HEALTH_ERROR", err.Error())
		return
	}
	writeJSON(w, 200, health)
}

// handleMetrics handles GET /metrics
func (s *Server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	metrics, err := s.service.GetMetrics(r.Context())
	if err != nil {
		writeError(w, 500, "METRICS_ERROR", err.Error())
		return
	}

	handshakes, toolCalls, writeCalls, searchContextRecallCalls := s.getMCPDetailedStats()
	metrics.MCP = &pkg.MCPMetrics{
		Handshakes:                     handshakes,
		ToolInvocations:                toolCalls,
		MemoryWriteCalls:               writeCalls,
		MemorySearchContextRecallCalls: searchContextRecallCalls,
		LastStartupError:               s.getMCPStartupError(),
	}
	writeJSON(w, 200, metrics)
}

// handleWrite handles POST /memory/write
func (s *Server) handleWrite(w http.ResponseWriter, r *http.Request) {
	var req pkg.WriteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}

	scopeRef := getScopeRefFromContext(r)
	if scopeRef == nil {
		scopeRef = s.scopeModel.GetDefaultScopeRef()
	}

	if req.RequestID == "" {
		req.RequestID = getRequestID(r.Context())
		if req.RequestID == "" {
			req.RequestID = generateRequestID()
		}
	}

	if scopeRef.Scope == pkg.ScopeCustom {
		writeError(w, 501, "NOT_IMPLEMENTED", "custom scope not implemented")
		return
	}

	resp, err := s.service.WriteMemory(r.Context(), &req, scopeRef)
	if err != nil {
		if appErr, ok := err.(*app.AppError); ok {
			writeError(w, appErr.HTTPCode, appErr.Code, appErr.Message)
			return
		}
		writeError(w, 500, "WRITE_ERROR", err.Error())
		return
	}

	writeJSON(w, 201, resp)
}

// handleQuery handles POST /memory/query
func (s *Server) handleQuery(w http.ResponseWriter, r *http.Request) {
	var req pkg.QueryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}

	scopeRef := getScopeRefFromContext(r)
	if scopeRef == nil {
		scopeRef = s.scopeModel.GetDefaultScopeRef()
	}

	if req.RequestID == "" {
		req.RequestID = getRequestID(r.Context())
		if req.RequestID == "" {
			req.RequestID = generateRequestID()
		}
	}

	if scopeRef.Scope == pkg.ScopeCustom {
		writeError(w, 501, "NOT_IMPLEMENTED", "custom scope not implemented")
		return
	}

	resp, err := s.service.QueryMemory(r.Context(), &req, scopeRef)
	if err != nil {
		if appErr, ok := err.(*app.AppError); ok {
			writeError(w, appErr.HTTPCode, appErr.Code, appErr.Message)
			return
		}
		writeError(w, 500, "QUERY_ERROR", err.Error())
		return
	}

	writeJSON(w, 200, resp)
}

// handleSearch handles POST /memory/search
func (s *Server) handleSearch(w http.ResponseWriter, r *http.Request) {
	var req pkg.SearchRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}

	scopeRef := getScopeRefFromContext(r)
	if scopeRef == nil {
		scopeRef = s.scopeModel.GetDefaultScopeRef()
	}

	if req.RequestID == "" {
		req.RequestID = getRequestID(r.Context())
		if req.RequestID == "" {
			req.RequestID = generateRequestID()
		}
	}

	if scopeRef.Scope == pkg.ScopeCustom {
		writeError(w, 501, "NOT_IMPLEMENTED", "custom scope not implemented")
		return
	}

	resp, err := s.service.SearchMemory(r.Context(), &req, scopeRef)
	if err != nil {
		if appErr, ok := err.(*app.AppError); ok {
			writeError(w, appErr.HTTPCode, appErr.Code, appErr.Message)
			return
		}
		writeError(w, 500, "SEARCH_ERROR", err.Error())
		return
	}

	writeJSON(w, 200, resp)
}

// handleDelete handles POST /memory/delete
func (s *Server) handleDelete(w http.ResponseWriter, r *http.Request) {
	var req pkg.DeleteRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}

	scopeRef := getScopeRefFromContext(r)
	if scopeRef == nil {
		scopeRef = s.scopeModel.GetDefaultScopeRef()
	}

	if req.RequestID == "" {
		req.RequestID = getRequestID(r.Context())
		if req.RequestID == "" {
			req.RequestID = generateRequestID()
		}
	}

	if scopeRef.Scope == pkg.ScopeCustom {
		writeError(w, 501, "NOT_IMPLEMENTED", "custom scope not implemented")
		return
	}

	resp, err := s.service.DeleteMemory(r.Context(), &req, scopeRef)
	if err != nil {
		if appErr, ok := err.(*app.AppError); ok {
			writeError(w, appErr.HTTPCode, appErr.Code, appErr.Message)
			return
		}
		writeError(w, 500, "DELETE_ERROR", err.Error())
		return
	}

	writeJSON(w, 200, resp)
}

// handleConnectorRegister handles POST /connector/register
func (s *Server) handleConnectorRegister(w http.ResponseWriter, r *http.Request) {
	var req connector.RegisterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "INVALID_REQUEST", "invalid JSON body")
		return
	}

	resp, err := s.registry.Register(&req)
	if err != nil {
		writeError(w, 400, "REGISTER_ERROR", err.Error())
		return
	}

	writeJSON(w, 201, resp)
}

// handleConnectorList handles GET /connector/list
func (s *Server) handleConnectorList(w http.ResponseWriter, r *http.Request) {
	connectors := s.registry.List()
	writeJSON(w, 200, connectors)
}

func getScopeRefFromContext(r *http.Request) *pkg.ScopeRef {
	if scopeRef, ok := r.Context().Value(scopeContextKey).(*pkg.ScopeRef); ok {
		return scopeRef
	}
	return nil
}
