package api

import "sync/atomic"

type mcpMetricsState struct {
	handshakeCount                 int64
	toolCallCount                  int64
	memoryWriteCount               int64
	memorySearchContextRecallCount int64
}

func newMCPMetricsState() *mcpMetricsState {
	return &mcpMetricsState{}
}

func (s *mcpMetricsState) recordHandshake() {
	atomic.AddInt64(&s.handshakeCount, 1)
}

func (s *mcpMetricsState) recordToolCallByName(name string) {
	atomic.AddInt64(&s.toolCallCount, 1)
	isWrite, isSearchContextRecall := classifyMCPToolCall(name)
	if isWrite {
		atomic.AddInt64(&s.memoryWriteCount, 1)
	}
	if isSearchContextRecall {
		atomic.AddInt64(&s.memorySearchContextRecallCount, 1)
	}
}

func (s *mcpMetricsState) stats() (handshakes int64, toolCalls int64) {
	return atomic.LoadInt64(&s.handshakeCount), atomic.LoadInt64(&s.toolCallCount)
}

func (s *mcpMetricsState) detailedStats() (handshakes int64, toolCalls int64, writeCalls int64, searchContextRecallCalls int64) {
	return atomic.LoadInt64(&s.handshakeCount),
		atomic.LoadInt64(&s.toolCallCount),
		atomic.LoadInt64(&s.memoryWriteCount),
		atomic.LoadInt64(&s.memorySearchContextRecallCount)
}
