// app/context/strategy_auto.go - Auto Strategy Resolution
// Automatically selects the best strategy based on query characteristics
package context

import (
	"strings"
)

// ResolveAutoStrategy selects an appropriate strategy based on query characteristics
// This is the minimal viable auto-selection logic
func ResolveAutoStrategy(query string) string {
	q := strings.ToLower(strings.TrimSpace(query))

	// Question-type queries benefit from precise topk selection
	if strings.Contains(q, "?") ||
		strings.HasPrefix(q, "what") ||
		strings.HasPrefix(q, "how") ||
		strings.HasPrefix(q, "why") ||
		strings.HasPrefix(q, "when") ||
		strings.HasPrefix(q, "where") ||
		strings.HasPrefix(q, "who") {
		return "topk_excerpt"
	}

	// Long queries benefit from diversity to avoid repetition
	if len(q) > 50 {
		return "diversity_select"
	}

	// Default to recency for general queries
	return "recency_boost_select"
}
