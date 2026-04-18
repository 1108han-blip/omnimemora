package api

import (
	"context"
	"fmt"
	"strings"

	"github.com/google/uuid"
	"github.com/omnimemora/local-runtime/pkg"
)

func (s *Server) handleMCPWriteTool(ctx context.Context, id any, args map[string]interface{}, scopeRef *pkg.ScopeRef) *mcpResponse {
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
}

func (s *Server) handleMCPSearchTool(ctx context.Context, id any, args map[string]interface{}, scopeRef *pkg.ScopeRef) *mcpResponse {
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
}

func (s *Server) handleMCPContextTool(ctx context.Context, id any, args map[string]interface{}, scopeRef *pkg.ScopeRef) *mcpResponse {
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
}
