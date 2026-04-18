package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/omnimemora/local-runtime/pkg"
)

func (s *Server) handleMCPSSE(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)

	sessionID := "mcp_" + uuid.New().String()
	session := &mcpSession{
		id:   sessionID,
		send: make(chan []byte, 32),
	}

	s.mcpTransport.putSession(sessionID, session)
	defer func() {
		s.mcpTransport.deleteSession(sessionID)
	}()

	_, _ = fmt.Fprintf(w, "event: endpoint\ndata: /messages?sessionId=%s\n\n", sessionID)
	flusher.Flush()

	keepAlive := time.NewTicker(20 * time.Second)
	defer keepAlive.Stop()

	for {
		select {
		case msg := <-session.send:
			_, _ = fmt.Fprintf(w, "event: message\ndata: %s\n\n", string(msg))
			flusher.Flush()
		case <-keepAlive.C:
			_, _ = fmt.Fprint(w, ": keepalive\n\n")
			flusher.Flush()
		case <-r.Context().Done():
			return
		}
	}
}

func (s *Server) handleMCPMessages(w http.ResponseWriter, r *http.Request) {
	sessionID := r.URL.Query().Get("sessionId")
	if sessionID == "" {
		s.setMCPStartupError("missing sessionId")
		writeError(w, 400, "MCP_BAD_REQUEST", "missing sessionId")
		return
	}

	session := s.mcpTransport.getSession(sessionID)
	if session == nil {
		s.setMCPStartupError("session not found")
		writeError(w, 404, "MCP_SESSION_NOT_FOUND", "session not found")
		return
	}

	var req mcpRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		s.setMCPStartupError("invalid jsonrpc request")
		writeError(w, 400, "MCP_BAD_REQUEST", "invalid jsonrpc request")
		return
	}

	resp := s.handleMCPRequest(r.Context(), &req)
	if resp != nil {
		data, err := json.Marshal(resp)
		if err == nil {
			select {
			case session.send <- data:
			default:
				// Drop the response if client is not consuming fast enough.
			}
		}
	}

	w.WriteHeader(http.StatusAccepted)
}

func (s *Server) handleMCPHTTP(w http.ResponseWriter, r *http.Request) {
	var req mcpRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		s.setMCPStartupError("invalid jsonrpc request")
		writeError(w, 400, "MCP_BAD_REQUEST", "invalid jsonrpc request")
		return
	}

	resp := s.handleMCPRequest(r.Context(), &req)
	if resp == nil {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

func (s *Server) handleMCPRequest(ctx context.Context, req *mcpRequest) *mcpResponse {
	switch req.Method {
	case "initialize":
		s.recordMCPHandshake()
		s.setMCPStartupError("")
		return &mcpResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"protocolVersion": "2024-11-05",
				"serverInfo": map[string]any{
					"name":    "omnimemora",
					"version": s.rtCtx.Version,
				},
				"capabilities": map[string]any{
					"tools": map[string]any{},
				},
			},
		}
	case "notifications/initialized":
		return nil
	case "tools/list":
		return &mcpResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Result: map[string]any{
				"tools": mcpToolCatalog(),
			},
		}
	case "tools/call":
		var params struct {
			Name      string                 `json:"name"`
			Arguments map[string]interface{} `json:"arguments"`
		}
		if err := json.Unmarshal(req.Params, &params); err != nil {
			s.setMCPStartupError("invalid tools/call params")
			return &mcpResponse{
				JSONRPC: "2.0",
				ID:      req.ID,
				Error:   &mcpError{Code: -32602, Message: "invalid params"},
			}
		}
		s.recordMCPToolCallByName(params.Name)
		return s.callMCPTool(ctx, req.ID, params.Name, params.Arguments)
	default:
		s.setMCPStartupError("method not found: " + req.Method)
		return &mcpResponse{
			JSONRPC: "2.0",
			ID:      req.ID,
			Error:   &mcpError{Code: -32601, Message: "method not found"},
		}
	}
}

func (s *Server) callMCPTool(ctx context.Context, id any, name string, args map[string]interface{}) *mcpResponse {
	scopeRef := defaultMCPScopeRef()

	switch name {
	case "omnimemora_write_memory", "memory.write", "memory.store":
		content, _ := args["content"].(string)
		if strings.TrimSpace(content) == "" {
			return mcpToolError(id, "content is required")
		}
		req := &pkg.WriteRequest{
			Content:   content,
			RequestID: "mcp_write_" + uuid.New().String()[:8],
			Metadata: map[string]any{
				"source": "openclaw-mcp",
			},
		}
		if scope, ok := args["scope"].(string); ok {
			req.Scope = pkg.ScopeType(scope)
		}
		resp, err := s.service.WriteMemory(ctx, req, scopeRef)
		if err != nil {
			return mcpToolError(id, err.Error())
		}
		return mcpToolText(id, fmt.Sprintf("memory written: %s", resp.MemoryID))

	case "omnimemora_search_memory", "memory.search":
		keyword, _ := args["keyword"].(string)
		if strings.TrimSpace(keyword) == "" {
			return mcpToolError(id, "keyword is required")
		}
		limit := 8
		if f, ok := args["limit"].(float64); ok && int(f) > 0 {
			limit = int(f)
		}
		req := &pkg.SearchRequest{
			Keyword:   keyword,
			Limit:     limit,
			RequestID: "mcp_search_" + uuid.New().String()[:8],
			Options: pkg.SearchOptions{
				AssembleContext: true,
				ContextStrategy: "auto",
				ContextMode:     "balanced",
			},
		}
		resp, err := s.service.SearchMemory(ctx, req, scopeRef)
		if err != nil {
			return mcpToolError(id, err.Error())
		}
		return mcpToolText(id, fmt.Sprintf("search done: results=%d saved_tokens=%d", len(resp.Results), func() int {
			if resp.Context != nil {
				return resp.Context.SavedTokens
			}
			return 0
		}()))
	case "memory.context", "memory.recall":
		query, _ := args["query"].(string)
		if strings.TrimSpace(query) == "" {
			query, _ = args["keyword"].(string)
		}
		if strings.TrimSpace(query) == "" {
			return mcpToolError(id, "query is required")
		}
		limit := 8
		if f, ok := args["limit"].(float64); ok && int(f) > 0 {
			limit = int(f)
		}
		req := &pkg.SearchRequest{
			Keyword:   query,
			Limit:     limit,
			RequestID: "mcp_context_" + uuid.New().String()[:8],
			Options: pkg.SearchOptions{
				AssembleContext: true,
				ContextStrategy: "auto",
				ContextMode:     "balanced",
			},
		}
		resp, err := s.service.SearchMemory(ctx, req, scopeRef)
		if err != nil {
			return mcpToolError(id, err.Error())
		}
		contextText := ""
		saved := 0
		if resp.Context != nil {
			contextText = resp.Context.CombinedText
			saved = resp.Context.SavedTokens
		}
		return mcpToolText(id, fmt.Sprintf("context ready: results=%d saved_tokens=%d\n%s", len(resp.Results), saved, contextText))
	default:
		s.setMCPStartupError("unknown tool: " + name)
		return mcpToolError(id, "unknown tool: "+name)
	}
}
