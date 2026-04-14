// app/context/assembler.go - Context Assembler
// Orchestrates context construction using strategies with caching
package context

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"

	"github.com/omnimemora/local-runtime/pkg"
)

// CacheKeyComponents contains all components needed for cache key generation
type CacheKeyComponents struct {
	TenantID    string
	WorkspaceID string
	AgentID     string
	Scope       string
	Query       string
	Strategy    string
	Mode        ContextMode
	TokenBudget int
	MaxItems    int
}

// AssemblyResult contains the assembled context along with metadata (Phase 2c.5)
type AssemblyResult struct {
	Context          *pkg.StrategyAssembledContext // nil if no assembly happened
	Items            []pkg.StrategyContextItem
	Effectiveness    *pkg.StrategyEffectiveness
	ResolvedStrategy string // the actual strategy used (may differ from requested if auto)
	RawTokens        int    // honest sum of item.Tokens (not estimated)
	AssembledHits    int    // count of items selected
}

// Assembler orchestrates context construction using strategies
// NOTE: Cache is intentionally disabled pending dedicated scope-isolation audit
type Assembler struct {
	cache *Cache // cache disabled - reserved for future scope-aware implementation
}

// NewAssembler creates a new context assembler
func NewAssembler() *Assembler {
	return &Assembler{
		cache: NewCache(100), // allocated but not used
	}
}

// ClearCache clears the context cache (no-op, cache disabled)
func (a *Assembler) ClearCache() {
	// cache intentionally disabled pending dedicated scope-isolation audit
}

// BuildCacheKey generates a cache key from components
func (a *Assembler) BuildCacheKey(comp CacheKeyComponents) string {
	data := fmt.Sprintf("%s+%s+%s+%s+%s+%s+%s+%d+%d",
		comp.TenantID, comp.WorkspaceID, comp.AgentID, comp.Scope,
		comp.Query, comp.Strategy, comp.Mode, comp.TokenBudget, comp.MaxItems)
	h := sha256.New()
	h.Write([]byte(data))
	return hex.EncodeToString(h.Sum(nil))[:32]
}

// AssembleContext builds context using the specified strategy
// Cache is disabled - this method always executes the strategy
func (a *Assembler) AssembleContext(
	results []pkg.StrategySearchResult,
	query string,
	strategyName string,
	opts StrategyOptions,
	cacheComp CacheKeyComponents,
) AssemblyResult {
	// Resolve strategy (default to topk_excerpt)
	strategy := GetStrategy(strategyName)
	if strategy == nil {
		strategy = GetStrategy(DefaultStrategy)
		strategyName = DefaultStrategy
	}

	// Apply mode defaults
	opts = opts.GetDefaults()

	// Execute strategy
	items := strategy.Select(results, query, opts)

	// Handle empty items case
	if len(items) == 0 {
		return AssemblyResult{
			Context:          nil,
			Items:            nil,
			Effectiveness:    nil,
			ResolvedStrategy: strategyName,
			RawTokens:        0,
			AssembledHits:    0,
		}
	}

	result := strategy.Assemble(items, opts)

	// Honest token accounting: RawTokens = sum of all selected item.Tokens
	rawTokens := 0
	for _, item := range items {
		rawTokens += item.Tokens
	}

	effectiveness := ComputeEffectiveness(items, result, rawTokens)

	return AssemblyResult{
		Context:          &result,
		Items:            items,
		Effectiveness:    effectiveness,
		ResolvedStrategy: strategyName,
		RawTokens:        rawTokens,
		AssembledHits:    len(items),
	}
}

// assembleFromItems builds final AssembledContext from selected items
func assembleFromItems(items []pkg.StrategyContextItem, opts StrategyOptions) pkg.StrategyAssembledContext {
	if len(items) == 0 {
		return pkg.StrategyAssembledContext{}
	}

	var sb strings.Builder
	totalTokens := 0

	for i, item := range items {
		if i > 0 {
			sb.WriteString("\n\n")
		}
		sb.WriteString("[Memory ")
		sb.WriteString(item.MemoryID)
		sb.WriteString(" | score=")
		sb.WriteString(fmt.Sprintf("%.2f", item.Score))
		sb.WriteString("]\n")
		sb.WriteString(item.Content)
		totalTokens += item.Tokens
	}

	text := sb.String()

	rawTokens := 0
	for _, item := range items {
		rawTokens += item.Tokens
	}

	compressionRatio := 0.0
	if rawTokens > 0 {
		compressionRatio = float64(totalTokens) / float64(rawTokens)
	}

	return pkg.StrategyAssembledContext{
		Text:             text,
		TotalTokens:      totalTokens,
		UsedItems:        len(items),
		CompressionRatio: compressionRatio,
	}
}
