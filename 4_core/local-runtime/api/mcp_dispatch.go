package api

import (
	"context"
	"encoding/json"
)

type mcpToolCallParams struct {
	Name      string                 `json:"name"`
	Arguments map[string]interface{} `json:"arguments"`
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
		var params mcpToolCallParams
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
		return s.handleMCPWriteTool(ctx, id, args, scopeRef)
	case "omnimemora_search_memory", "memory.search":
		return s.handleMCPSearchTool(ctx, id, args, scopeRef)
	case "memory.context", "memory.recall":
		return s.handleMCPContextTool(ctx, id, args, scopeRef)
	default:
		s.setMCPStartupError("unknown tool: " + name)
		return mcpToolError(id, "unknown tool: "+name)
	}
}
