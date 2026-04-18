package api

import "sync"

type bootstrapState struct {
	mu      sync.RWMutex
	success bool
}

func newBootstrapState() *bootstrapState {
	return &bootstrapState{}
}

func (s *bootstrapState) setSuccess(ok bool) {
	s.mu.Lock()
	s.success = ok
	s.mu.Unlock()
}

func (s *bootstrapState) isSuccess() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.success
}
