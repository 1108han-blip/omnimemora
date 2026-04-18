package api

import "sync"

type mcpState struct {
	mu               sync.RWMutex
	lastStartupError string
}

func newMCPState() *mcpState {
	return &mcpState{}
}

func (s *mcpState) setStartupError(msg string) {
	s.mu.Lock()
	s.lastStartupError = msg
	s.mu.Unlock()
}

func (s *mcpState) startupError() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.lastStartupError
}
