// tests/search_phase3_deterministic_test.go - Phase 3 deterministic context tests
// Verifies that same input always produces same context output
package tests

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/omnimemora/local-runtime/api"
	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/lifecycle"
	"github.com/omnimemora/local-runtime/pkg"
	"github.com/omnimemora/local-runtime/store"
)

// TestDeterministicContext tests that identical inputs produce identical outputs
func TestDeterministicContext(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write 5 memories with known content
	memories := []string{
		"This is a detailed memory about Go programming language and its concurrency model with goroutines",
		"Python is a programming language known for its simplicity and extensive standard library",
		"SQLite is a lightweight embedded database that stores data in a single file",
		"JavaScript runs in browsers and can also be used server-side with Node.js runtime",
		"Memory efficiency is important for performance in large-scale systems",
	}

	for _, content := range memories {
		writeReq := pkg.WriteRequest{Content: content}
		writeBody, _ := json.Marshal(writeReq)
		req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "deterministic_test_agent")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)
		if rec.Code != http.StatusCreated {
			t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
		}
	}

	// Run same search 10 times and verify identical results
	keyword := "programming"
	var firstResult *pkg.SearchResponse

	for i := 0; i < 10; i++ {
		searchReq := map[string]interface{}{
			"keyword": keyword,
			"limit":   5,
			"options": map[string]interface{}{
				"assemble_context": true,
				"context_strategy": "topk_excerpt",
				"context_mode":     "balanced",
			},
		}
		searchBody, _ := json.Marshal(searchReq)
		req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "deterministic_test_agent")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Fatalf("search %d failed: %d - %s", i, rec.Code, rec.Body.String())
		}

		var searchResp pkg.SearchResponse
		if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
			t.Fatalf("search %d failed to parse: %v", i, err)
		}

		if firstResult == nil {
			firstResult = &searchResp
			t.Logf("First run: strategy=%s, resolved=%s, mode=%s, items=%d, raw=%d, compressed=%d, saved=%d, ratio=%.2f",
				searchResp.Context.Strategy,
				searchResp.Context.StrategyResolved,
				searchResp.Context.Mode,
				searchResp.Context.ItemsSelected,
				searchResp.Context.RawTokens,
				searchResp.Context.CompressedTokens,
				searchResp.Context.SavedTokens,
				searchResp.Context.CompressionRatio,
			)
		} else {
			// Verify identical results
			if searchResp.Context.Strategy != firstResult.Context.Strategy {
				t.Errorf("run %d: Strategy mismatch: got %s, want %s", i, searchResp.Context.Strategy, firstResult.Context.Strategy)
			}
			if searchResp.Context.StrategyResolved != firstResult.Context.StrategyResolved {
				t.Errorf("run %d: StrategyResolved mismatch: got %s, want %s", i, searchResp.Context.StrategyResolved, firstResult.Context.StrategyResolved)
			}
			if searchResp.Context.Mode != firstResult.Context.Mode {
				t.Errorf("run %d: Mode mismatch: got %s, want %s", i, searchResp.Context.Mode, firstResult.Context.Mode)
			}
			if searchResp.Context.ItemsSelected != firstResult.Context.ItemsSelected {
				t.Errorf("run %d: ItemsSelected mismatch: got %d, want %d", i, searchResp.Context.ItemsSelected, firstResult.Context.ItemsSelected)
			}
			if searchResp.Context.RawTokens != firstResult.Context.RawTokens {
				t.Errorf("run %d: RawTokens mismatch: got %d, want %d", i, searchResp.Context.RawTokens, firstResult.Context.RawTokens)
			}
			if searchResp.Context.CompressedTokens != firstResult.Context.CompressedTokens {
				t.Errorf("run %d: CompressedTokens mismatch: got %d, want %d", i, searchResp.Context.CompressedTokens, firstResult.Context.CompressedTokens)
			}
			if searchResp.Context.SavedTokens != firstResult.Context.SavedTokens {
				t.Errorf("run %d: SavedTokens mismatch: got %d, want %d", i, searchResp.Context.SavedTokens, firstResult.Context.SavedTokens)
			}
			if searchResp.Context.CompressionRatio != firstResult.Context.CompressionRatio {
				t.Errorf("run %d: CompressionRatio mismatch: got %.4f, want %.4f", i, searchResp.Context.CompressionRatio, firstResult.Context.CompressionRatio)
			}
			if searchResp.Context.CombinedText != firstResult.Context.CombinedText {
				t.Errorf("run %d: CombinedText mismatch", i)
			}
		}
	}
}

// TestDeterministicContextAutoStrategy tests determinism with auto strategy
func TestDeterministicContextAutoStrategy(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write memories with different age characteristics
	memories := []struct {
		content  string
		daysAgo  int
	}{
		{"Recent memory about distributed systems and microservices architecture", 1},
		{"Old memory about monolithic applications and traditional deployment", 30},
		{"Very old memory about early computing history", 90},
	}

	for _, m := range memories {
		writeReq := pkg.WriteRequest{Content: m.content}
		writeBody, _ := json.Marshal(writeReq)
		req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "auto_strategy_test_agent")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)
		if rec.Code != http.StatusCreated {
			t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
		}
	}

	// Run search with auto strategy multiple times
	var firstResolvedStrategy string
	var firstContextText string

	for i := 0; i < 5; i++ {
		searchReq := map[string]interface{}{
			"keyword": "memory systems",
			"limit":   5,
			"options": map[string]interface{}{
				"assemble_context": true,
				"context_strategy": "auto",
			},
		}
		searchBody, _ := json.Marshal(searchReq)
		req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "auto_strategy_test_agent")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Fatalf("search %d failed: %d - %s", i, rec.Code, rec.Body.String())
		}

		var searchResp pkg.SearchResponse
		if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
			t.Fatalf("search %d failed to parse: %v", i, err)
		}

		if firstResolvedStrategy == "" {
			firstResolvedStrategy = searchResp.Context.StrategyResolved
			firstContextText = searchResp.Context.CombinedText
			t.Logf("Run %d: resolved strategy=%s", i, firstResolvedStrategy)
		} else {
			if searchResp.Context.StrategyResolved != firstResolvedStrategy {
				t.Errorf("run %d: StrategyResolved mismatch: got %s, want %s", i, searchResp.Context.StrategyResolved, firstResolvedStrategy)
			}
			if searchResp.Context.CombinedText != firstContextText {
				t.Errorf("run %d: CombinedText mismatch with auto strategy", i)
			}
		}
	}
}

// TestDeterministicContextModes tests determinism across different modes
func TestDeterministicContextModes(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write multiple memories
	for i := 0; i < 10; i++ {
		writeReq := pkg.WriteRequest{Content: "Memory content number " + string(rune('0'+i)) + " with some additional text for testing"}
		writeBody, _ := json.Marshal(writeReq)
		req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "modes_test_agent")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)
		if rec.Code != http.StatusCreated {
			t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
		}
	}

	modes := []string{"precise", "balanced", "aggressive"}

	for _, mode := range modes {
		var firstResult *pkg.SearchResponse

		// Run same search 3 times for each mode
		for j := 0; j < 3; j++ {
			searchReq := map[string]interface{}{
				"keyword": "memory content",
				"limit":   10,
				"options": map[string]interface{}{
					"assemble_context": true,
					"context_strategy": "topk_excerpt",
					"context_mode":     mode,
				},
			}
			searchBody, _ := json.Marshal(searchReq)
			req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
			req.Header.Set("Content-Type", "application/json")
			req.Header.Set("X-OmniMemora-Agent", "modes_test_agent")

			rec := httptest.NewRecorder()
			server.Handler().ServeHTTP(rec, req)

			if rec.Code != http.StatusOK {
				t.Fatalf("mode %s run %d failed: %d - %s", mode, j, rec.Code, rec.Body.String())
			}

			var searchResp pkg.SearchResponse
			if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
				t.Fatalf("mode %s run %d failed to parse: %v", mode, j, err)
			}

			if firstResult == nil {
				firstResult = &searchResp
				t.Logf("Mode %s: items=%d, raw=%d, compressed=%d, ratio=%.2f",
					mode, searchResp.Context.ItemsSelected, searchResp.Context.RawTokens,
					searchResp.Context.CompressedTokens, searchResp.Context.CompressionRatio)
			} else {
				if searchResp.Context.ItemsSelected != firstResult.Context.ItemsSelected {
					t.Errorf("mode %s run %d: ItemsSelected mismatch: got %d, want %d",
						mode, j, searchResp.Context.ItemsSelected, firstResult.Context.ItemsSelected)
				}
				if searchResp.Context.RawTokens != firstResult.Context.RawTokens {
					t.Errorf("mode %s run %d: RawTokens mismatch: got %d, want %d",
						mode, j, searchResp.Context.RawTokens, firstResult.Context.RawTokens)
				}
				if searchResp.Context.CompressedTokens != firstResult.Context.CompressedTokens {
					t.Errorf("mode %s run %d: CompressedTokens mismatch: got %d, want %d",
						mode, j, searchResp.Context.CompressedTokens, firstResult.Context.CompressedTokens)
				}
			}
		}
	}
}

// TestDeterministicContextTokenBudgetBoundary tests token budget boundary behavior
func TestDeterministicContextTokenBudgetBoundary(t *testing.T) {
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	defer s.Close()

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}

	server := api.NewServer(cfg, s, rtCtx, 18765)

	// Write memories of varying sizes
	memories := []string{
		"Short", // tiny
		strings.Repeat("medium content with some text ", 20),  // ~440 chars
		strings.Repeat("larger content block with more information ", 50),  // ~1100 chars
	}

	for _, content := range memories {
		writeReq := pkg.WriteRequest{Content: content}
		writeBody, _ := json.Marshal(writeReq)
		req := httptest.NewRequest("POST", "/memory/write", bytes.NewReader(writeBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "budget_test_agent")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)
		if rec.Code != http.StatusCreated {
			t.Fatalf("write failed: %d - %s", rec.Code, rec.Body.String())
		}
	}

	// Run same search 5 times with aggressive mode (higher budget)
	var firstResult *pkg.SearchResponse

	for i := 0; i < 5; i++ {
		searchReq := map[string]interface{}{
			"keyword": "content",
			"limit":   5,
			"options": map[string]interface{}{
				"assemble_context": true,
				"context_strategy": "topk_excerpt",
				"context_mode":     "aggressive",
			},
		}
		searchBody, _ := json.Marshal(searchReq)
		req := httptest.NewRequest("POST", "/memory/search", bytes.NewReader(searchBody))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-OmniMemora-Agent", "budget_test_agent")

		rec := httptest.NewRecorder()
		server.Handler().ServeHTTP(rec, req)

		if rec.Code != http.StatusOK {
			t.Fatalf("search %d failed: %d - %s", i, rec.Code, rec.Body.String())
		}

		var searchResp pkg.SearchResponse
		if err := json.Unmarshal(rec.Body.Bytes(), &searchResp); err != nil {
			t.Fatalf("search %d failed to parse: %v", i, err)
		}

		if firstResult == nil {
			firstResult = &searchResp
			t.Logf("First run: items=%d, raw=%d, compressed=%d, saved=%d",
				searchResp.Context.ItemsSelected, searchResp.Context.RawTokens,
				searchResp.Context.CompressedTokens, searchResp.Context.SavedTokens)
		} else {
			if searchResp.Context.ItemsSelected != firstResult.Context.ItemsSelected {
				t.Errorf("run %d: ItemsSelected mismatch: got %d, want %d",
					i, searchResp.Context.ItemsSelected, firstResult.Context.ItemsSelected)
			}
			if searchResp.Context.RawTokens != firstResult.Context.RawTokens {
				t.Errorf("run %d: RawTokens mismatch: got %d, want %d",
					i, searchResp.Context.RawTokens, firstResult.Context.RawTokens)
			}
			if searchResp.Context.CompressedTokens != firstResult.Context.CompressedTokens {
				t.Errorf("run %d: CompressedTokens mismatch: got %d, want %d",
					i, searchResp.Context.CompressedTokens, firstResult.Context.CompressedTokens)
			}
		}
	}
}