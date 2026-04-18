package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
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
