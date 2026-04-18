package api

import "sync"

type mcpTransportState struct {
	mu       sync.RWMutex
	sessions map[string]*mcpSession
}

func newMCPTransportState() *mcpTransportState {
	return &mcpTransportState{
		sessions: make(map[string]*mcpSession),
	}
}

func (s *mcpTransportState) putSession(sessionID string, session *mcpSession) {
	s.mu.Lock()
	s.sessions[sessionID] = session
	s.mu.Unlock()
}

func (s *mcpTransportState) getSession(sessionID string) *mcpSession {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.sessions[sessionID]
}

func (s *mcpTransportState) deleteSession(sessionID string) {
	s.mu.Lock()
	delete(s.sessions, sessionID)
	s.mu.Unlock()
}
