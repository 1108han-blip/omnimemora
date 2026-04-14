// app/context/strategy_topk.go - Top-K Excerpt Strategy
// Baseline strategy: score sort, top-k selection, token budget truncate
package context

import (
	"sort"
	"strings"

	"github.com/omnimemora/local-runtime/pkg"
)

// TopKExcerptStrategy is the baseline strategy
type TopKExcerptStrategy struct{}

func (s *TopKExcerptStrategy) Name() string {
	return "topk_excerpt"
}

// normalizedTokenCost applies a floor to prevent extreme bias toward tiny fragments (Phase 2c.5)
func normalizedTokenCost(tokens int) float64 {
	if tokens <= 0 {
		return 1.0
	}
	if tokens < 80 {
		return 80.0 // token floor to prevent short fragments from dominating
	}
	return float64(tokens)
}

// efficiencyScore calculates score normalized by token cost (with floor)
func efficiencyScore(tokens int, score float64) float64 {
	return score / normalizedTokenCost(tokens)
}

func (s *TopKExcerptStrategy) Select(results []pkg.StrategySearchResult, query string, opts StrategyOptions) []pkg.StrategyContextItem {
	if len(results) == 0 {
		return nil
	}

	// Sort by efficiency score (score/tokens) descending
	sorted := make([]pkg.StrategySearchResult, len(results))
	copy(sorted, results)
	sort.Slice(sorted, func(i, j int) bool {
		return efficiencyScore(sorted[i].TokenEstimate, sorted[i].Score) >
			efficiencyScore(sorted[j].TokenEstimate, sorted[j].Score)
	})

	maxItems := opts.MaxItems
	if maxItems <= 0 {
		maxItems = 6
	}
	if len(sorted) < maxItems {
		maxItems = len(sorted)
	}

	items := make([]pkg.StrategyContextItem, 0, maxItems)
	totalTokens := 0

	for i := 0; i < maxItems; i++ {
		// Check token budget (don't exceed if we already have items)
		if totalTokens+sorted[i].TokenEstimate > opts.TokenBudget && len(items) > 0 {
			break
		}
		items = append(items, pkg.StrategyContextItem{
			MemoryID:  sorted[i].MemoryID,
			Content:   s.extractExcerpt(sorted[i].Content, query),
			Score:     sorted[i].Score,
			Tokens:    sorted[i].TokenEstimate,
			CreatedAt: sorted[i].CreatedAt,
		})
		totalTokens += sorted[i].TokenEstimate
	}
	return items
}

func (s *TopKExcerptStrategy) Assemble(items []pkg.StrategyContextItem, opts StrategyOptions) pkg.StrategyAssembledContext {
	return assembleFromItems(items, opts)
}

func (s *TopKExcerptStrategy) extractExcerpt(content, keyword string) string {
	if len(content) <= 300 {
		return strings.TrimSpace(content)
	}
	lowerContent := strings.ToLower(content)
	lowerKeyword := strings.ToLower(keyword)
	hitIdx := strings.Index(lowerContent, lowerKeyword)
	if hitIdx >= 0 {
		windowStart := hitIdx - 120
		if windowStart < 0 {
			windowStart = 0
		}
		windowEnd := hitIdx + 300
		if windowEnd > len(content) {
			windowEnd = len(content)
		}
		return strings.TrimSpace(content[windowStart:windowEnd])
	}
	if len(content) > 300 {
		return strings.TrimSpace(content[:300])
	}
	return strings.TrimSpace(content)
}
