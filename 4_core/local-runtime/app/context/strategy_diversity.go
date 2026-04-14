// app/context/strategy_diversity.go - Diversity Strategy
// Deduplicates by content similarity using FNV hash of first 200 chars
package context

import (
	"hash/fnv"
	"sort"
	"strings"

	"github.com/omnimemora/local-runtime/pkg"
)

// DiversityStrategy deduplicates by content similarity
type DiversityStrategy struct{}

func (s *DiversityStrategy) Name() string {
	return "diversity_select"
}

func (s *DiversityStrategy) Select(results []pkg.StrategySearchResult, query string, opts StrategyOptions) []pkg.StrategyContextItem {
	if len(results) == 0 {
		return nil
	}

	// Sort by score descending first
	sorted := make([]pkg.StrategySearchResult, len(results))
	copy(sorted, results)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Score > sorted[j].Score
	})

	// Deduplicate by FNV hash of first 200 chars
	seen := make(map[uint32]bool)
	unique := []pkg.StrategySearchResult{}

	for _, r := range sorted {
		// Normalize: lowercase, trim, take first 200 chars
		normalized := r.Content
		if len(normalized) > 200 {
			normalized = normalized[:200]
		}
		normalized = strings.ToLower(strings.TrimSpace(normalized))

		h := fnv.New32a()
		h.Write([]byte(normalized))
		fingerprint := h.Sum32()

		if !seen[fingerprint] {
			seen[fingerprint] = true
			unique = append(unique, r)
		}
	}

	maxItems := opts.MaxItems
	if maxItems <= 0 {
		maxItems = 6
	}

	items := make([]pkg.StrategyContextItem, 0, maxItems)
	totalTokens := 0

	for i := 0; i < len(unique) && i < maxItems; i++ {
		// Check token budget
		if totalTokens+unique[i].TokenEstimate > opts.TokenBudget && len(items) > 0 {
			break
		}
		items = append(items, pkg.StrategyContextItem{
			MemoryID:  unique[i].MemoryID,
			Content:   extractExcerptSimple(unique[i].Content, query),
			Score:     unique[i].Score,
			Tokens:    unique[i].TokenEstimate,
			CreatedAt: unique[i].CreatedAt,
		})
		totalTokens += unique[i].TokenEstimate
	}
	return items
}

func (s *DiversityStrategy) Assemble(items []pkg.StrategyContextItem, opts StrategyOptions) pkg.StrategyAssembledContext {
	return assembleFromItems(items, opts)
}
