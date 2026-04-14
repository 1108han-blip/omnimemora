// internal/demo/seed.go - Demo Data and Query for OmniMemora
// Provides initial demo data and executes demo search to show immediate value
package demo

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/omnimemora/local-runtime/pkg"
)

// Demo memories for initial seed
var demoMemories = []struct {
	Content  string
	Metadata map[string]any
}{
	{
		Content:  "Context optimization is crucial for AI agents working with long conversations. By compressing context, we reduce token usage while maintaining relevance.",
		Metadata: map[string]any{"source": "demo", "tags": []string{"context", "optimization"}},
	},
	{
		Content:  "Token savings accumulate when using selective context assembly. Each query that uses assemble_context=true can save hundreds to thousands of tokens per session.",
		Metadata: map[string]any{"source": "demo", "tags": []string{"token", "savings"}},
	},
	{
		Content:  "Memory retrieval in OmniMemora uses scope-based isolation. Agents can access their own memory workspace without interference from other agents.",
		Metadata: map[string]any{"source": "demo", "tags": []string{"memory", "retrieval"}},
	},
	{
		Content:  "Long-context compression techniques extract the most relevant excerpts from conversation history, preserving key information while discarding filler.",
		Metadata: map[string]any{"source": "demo", "tags": []string{"compression", "long-context"}},
	},
	{
		Content:  "Agent workflow continuity is maintained by storing conversation context between sessions. This allows AI agents to resume work without re-explaining background.",
		Metadata: map[string]any{"source": "demo", "tags": []string{"workflow", "continuity"}},
	},
	{
		Content:  "The topk_excerpt strategy selects the highest-scoring memory fragments within a token budget, optimizing for relevance per token spent.",
		Metadata: map[string]any{"source": "demo", "tags": []string{"strategy", "topk"}},
	},
	{
		Content:  "Recency boosting in context selection ensures recent memories are weighted higher, reflecting the temporal nature of most tasks.",
		Metadata: map[string]any{"source": "demo", "tags": []string{"recency", "boost"}},
	},
	{
		Content:  "Diversity selection prevents repetitive content from dominating context, ensuring a broader coverage of relevant information.",
		Metadata: map[string]any{"source": "demo", "tags": []string{"diversity"}},
	},
}

// SeedData writes demo memories to the store via HTTP API
func SeedData() error {
	baseURL := getRuntimeBaseURL()

	// Write each demo memory
	for i, mem := range demoMemories {
		writeReq := pkg.WriteRequest{
			Content:  mem.Content,
			Metadata: mem.Metadata,
			Scope:    pkg.ScopeAgent,
		}
		writeReq.Metadata["demo_index"] = i
		writeReq.Metadata["demo_写入时间"] = time.Now().UTC().Format(time.RFC3339)

		body, err := json.Marshal(writeReq)
		if err != nil {
			return fmt.Errorf("failed to marshal write request: %w", err)
		}

		resp, err := http.Post(baseURL+"/memory/write", "application/json", bytes.NewReader(body))
		if err != nil {
			return fmt.Errorf("failed to write demo memory %d: %w", i, err)
		}
		resp.Body.Close()

		if resp.StatusCode != http.StatusCreated {
			return fmt.Errorf("demo memory %d write failed with status %d", i, resp.StatusCode)
		}
	}

	return nil
}

// ExecuteDemoQuery runs a demo search to populate metrics
func ExecuteDemoQuery() error {
	baseURL := getRuntimeBaseURL()

	// Execute demo search with context assembly
	searchReq := map[string]interface{}{
		"keyword": "context optimization",
		"limit":   5,
		"options": map[string]interface{}{
			"assemble_context": true,
			"context_strategy": "auto",
			"context_mode":     "balanced",
		},
	}

	body, err := json.Marshal(searchReq)
	if err != nil {
		return fmt.Errorf("failed to marshal search request: %w", err)
	}

	resp, err := http.Post(baseURL+"/memory/search", "application/json", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("failed to execute demo search: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("demo search failed with status %d", resp.StatusCode)
	}

	return nil
}

// ExecuteDemo runs both seed and query
func ExecuteDemo() error {
	if err := SeedData(); err != nil {
		return fmt.Errorf("demo seed failed: %w", err)
	}
	if err := ExecuteDemoQuery(); err != nil {
		return fmt.Errorf("demo query failed: %w", err)
	}
	return nil
}

// getRuntimeBaseURL returns the base URL for runtime API
func getRuntimeBaseURL() string {
	port, _ := getRuntimePortFromState()
	if port == 0 {
		port = 8765 // Default fallback
	}
	return fmt.Sprintf("http://localhost:%d", port)
}

// getRuntimePortFromState reads port from runtime state file
func getRuntimePortFromState() (int, error) {
	// This is duplicated from runtime/port_resolver to avoid import cycle
	dataDir, err := getDataDir()
	if err != nil {
		return 0, err
	}

	stateFile := dataDir + "/runtime.state"
	content, err := osReadFile(stateFile)
	if err != nil {
		return 0, err
	}

	// Simple parsing
	for _, line := range splitLines(string(content)) {
		if len(line) > 5 && line[0:4] == "port" {
			var port int
			fmt.Sscanf(line[5:], "%d", &port)
			return port, nil
		}
	}

	return 0, fmt.Errorf("port not found in state file")
}

func getDataDir() (string, error) {
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_RUNTIME_DATA_DIR")); v != "" {
		return filepath.Clean(os.ExpandEnv(v)), nil
	}
	if v := strings.TrimSpace(os.Getenv("OMNIMEMORA_DATA_DIR")); v != "" {
		return filepath.Clean(os.ExpandEnv(v)), nil
	}
	homeDir, err := osUserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(homeDir, ".omnimemora"), nil
}

func osUserHomeDir() (string, error) {
	return os.UserHomeDir()
}

func osReadFile(name string) ([]byte, error) {
	return os.ReadFile(name)
}

func splitLines(s string) []string {
	var lines []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			lines = append(lines, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		lines = append(lines, s[start:])
	}
	return lines
}
