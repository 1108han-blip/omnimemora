// app/context/strategy_recency.go - Recency Boost Strategy
// Applies recency boost during selection to prevent old data from dominating
package context

import (
	"sort"
	"strings"
	"time"

	"github.com/omnimemora/local-runtime/pkg"
)

// RecencyBoostStrategy applies recency boost during selection
type RecencyBoostStrategy struct{}

func (s *RecencyBoostStrategy) Name() string {
	return "recency_boost_select"
}

func (s *RecencyBoostStrategy) Select(results []pkg.StrategySearchResult, query string, opts StrategyOptions) []pkg.StrategyContextItem {
	if len(results) == 0 {
		return nil
	}

	type scoredResult struct {
		result      pkg.StrategySearchResult
		boostScore float64
	}

	scored := make([]scoredResult, len(results))
	now := time.Now()

	for i, r := range results {
		age := now.Sub(r.CreatedAt)
		var recencyBoost float64
		switch {
		case age <= 24*time.Hour:
			recencyBoost = 0.15
		case age <= 7*24*time.Hour:
			recencyBoost = 0.10
		case age <= 30*24*time.Hour:
			recencyBoost = 0.05
		case age <= 90*24*time.Hour:
			recencyBoost = 0.02
		default:
			recencyBoost = 0.0
		}
		scored[i] = scoredResult{result: r, boostScore: r.Score + recencyBoost}
	}

	// Sort by efficiency score (boostScore/tokens) descending
	sort.Slice(scored, func(i, j int) bool {
		return efficiencyScore(scored[i].result.TokenEstimate, scored[i].boostScore) >
			efficiencyScore(scored[j].result.TokenEstimate, scored[j].boostScore)
	})

	maxItems := opts.MaxItems
	if maxItems <= 0 {
		maxItems = 6
	}

	items := make([]pkg.StrategyContextItem, 0, maxItems)
	totalTokens := 0

	for i := 0; i < len(scored) && i < maxItems; i++ {
		// Check token budget
		if totalTokens+scored[i].result.TokenEstimate > opts.TokenBudget && len(items) > 0 {
			break
		}
		items = append(items, pkg.StrategyContextItem{
			MemoryID:  scored[i].result.MemoryID,
			Content:   extractExcerptSimple(scored[i].result.Content, query),
			Score:     scored[i].boostScore,
			Tokens:    scored[i].result.TokenEstimate,
			CreatedAt: scored[i].result.CreatedAt,
		})
		totalTokens += scored[i].result.TokenEstimate
	}
	return items
}

func (s *RecencyBoostStrategy) Assemble(items []pkg.StrategyContextItem, opts StrategyOptions) pkg.StrategyAssembledContext {
	return assembleFromItems(items, opts)
}

func extractExcerptSimple(content, keyword string) string {
	if len(content) <= 300 {
		return content
	}
	lowerContent := strings.ToLower(content)
	lowerKeyword := strings.ToLower(keyword)
	hitIdx := strings.Index(lowerContent, lowerKeyword)
	if hitIdx >= 0 {
		start := hitIdx - 120
		if start < 0 {
			start = 0
		}
		end := hitIdx + 300
		if end > len(content) {
			end = len(content)
		}
		return strings.TrimSpace(content[start:end])
	}
	return strings.TrimSpace(content[:300])
}
