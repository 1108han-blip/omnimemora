package api

import "github.com/omnimemora/local-runtime/pkg"

func mcpToolCatalog() []map[string]any {
	return []map[string]any{
		{
			"name":        "omnimemora_write_memory",
			"description": "Write a memory item into OmniMemora.",
			"inputSchema": map[string]any{
				"type": "object",
				"properties": map[string]any{
					"content": map[string]any{"type": "string"},
					"scope":   map[string]any{"type": "string"},
				},
				"required": []string{"content"},
			},
		},
		{
			"name":        "omnimemora_search_memory",
			"description": "Search memories and assemble context.",
			"inputSchema": map[string]any{
				"type": "object",
				"properties": map[string]any{
					"keyword": map[string]any{"type": "string"},
					"limit":   map[string]any{"type": "integer"},
				},
				"required": []string{"keyword"},
			},
		},
		{
			"name":        "memory.write",
			"description": "Write memory content.",
			"inputSchema": map[string]any{
				"type": "object",
				"properties": map[string]any{
					"content": map[string]any{"type": "string"},
					"scope":   map[string]any{"type": "string"},
				},
				"required": []string{"content"},
			},
		},
		{
			"name":        "memory.search",
			"description": "Search memory by keyword.",
			"inputSchema": map[string]any{
				"type": "object",
				"properties": map[string]any{
					"keyword": map[string]any{"type": "string"},
					"limit":   map[string]any{"type": "integer"},
				},
				"required": []string{"keyword"},
			},
		},
		{
			"name":        "memory.context",
			"description": "Recall memory context for current query.",
			"inputSchema": map[string]any{
				"type": "object",
				"properties": map[string]any{
					"query": map[string]any{"type": "string"},
					"limit": map[string]any{"type": "integer"},
				},
				"required": []string{"query"},
			},
		},
	}
}

func defaultMCPScopeRef() *pkg.ScopeRef {
	return &pkg.ScopeRef{
		TenantID:    "openclaw",
		UserID:      "openclaw-user",
		WorkspaceID: "openclaw-workspace",
		AgentID:     "openclaw-agent",
		Scope:       pkg.ScopeAgent,
		SharingMode: pkg.SharingModeIsolated,
	}
}
