package api

import "encoding/json"

type mcpSession struct {
	id   string
	send chan []byte
}

type mcpRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      any             `json:"id,omitempty"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

type mcpResponse struct {
	JSONRPC string    `json:"jsonrpc"`
	ID      any       `json:"id,omitempty"`
	Result  any       `json:"result,omitempty"`
	Error   *mcpError `json:"error,omitempty"`
}

type mcpError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

func mcpToolText(id any, text string) *mcpResponse {
	return &mcpResponse{
		JSONRPC: "2.0",
		ID:      id,
		Result: map[string]any{
			"content": []map[string]any{
				{"type": "text", "text": text},
			},
		},
	}
}

func mcpToolError(id any, msg string) *mcpResponse {
	return &mcpResponse{
		JSONRPC: "2.0",
		ID:      id,
		Result: map[string]any{
			"isError": true,
			"content": []map[string]any{
				{"type": "text", "text": msg},
			},
		},
	}
}
