package api

import "testing"

func TestClassifyMCPToolCall(t *testing.T) {
	tests := []struct {
		name         string
		tool         string
		wantWrite    bool
		wantSearchCR bool
	}{
		{name: "write alias", tool: "memory.write", wantWrite: true, wantSearchCR: false},
		{name: "write store alias", tool: "memory.store", wantWrite: true, wantSearchCR: false},
		{name: "legacy write", tool: "omnimemora_write_memory", wantWrite: true, wantSearchCR: false},
		{name: "search alias", tool: "memory.search", wantWrite: false, wantSearchCR: true},
		{name: "context alias", tool: "memory.context", wantWrite: false, wantSearchCR: true},
		{name: "recall alias", tool: "memory.recall", wantWrite: false, wantSearchCR: true},
		{name: "legacy search", tool: "omnimemora_search_memory", wantWrite: false, wantSearchCR: true},
		{name: "unknown", tool: "unknown.tool", wantWrite: false, wantSearchCR: false},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			gotWrite, gotSearch := classifyMCPToolCall(tc.tool)
			if gotWrite != tc.wantWrite || gotSearch != tc.wantSearchCR {
				t.Fatalf("tool=%s got(write=%v,search=%v) want(write=%v,search=%v)",
					tc.tool, gotWrite, gotSearch, tc.wantWrite, tc.wantSearchCR)
			}
		})
	}
}

