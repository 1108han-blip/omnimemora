// app/context/effectiveness.go - Strategy Effectiveness Computation
// Computes metrics to evaluate strategy performance
package context

import (
	"github.com/omnimemora/local-runtime/pkg"
)

// ComputeEffectiveness calculates effectiveness metrics from assembly results
func ComputeEffectiveness(
	items []pkg.StrategyContextItem,
	result pkg.StrategyAssembledContext,
	rawTokens int,
) *pkg.StrategyEffectiveness {
	if len(items) == 0 || result.TotalTokens == 0 {
		return nil
	}

	totalScore := 0.0
	for _, item := range items {
		totalScore += item.Score
	}

	// Avoid division by zero
	compressionRatio := 0.0
	if rawTokens > 0 {
		compressionRatio = float64(result.TotalTokens) / float64(rawTokens)
	}

	return &pkg.StrategyEffectiveness{
		TokensPerItem:    float64(result.TotalTokens) / float64(len(items)),
		CompressionRatio: compressionRatio,
		AvgScore:         totalScore / float64(len(items)),
	}
}
