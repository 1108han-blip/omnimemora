// app/context/strategy.go - Context Strategy Interface and Core Types
// Phase 2c: Context Intelligence Layer
package context

import (
	"github.com/omnimemora/local-runtime/pkg"
)

// ContextMode represents the context construction mode
type ContextMode string

const (
	ModePrecise    ContextMode = "precise"    // TokenBudget=300, MaxItems=3
	ModeBalanced   ContextMode = "balanced"   // TokenBudget=800, MaxItems=6
	ModeAggressive ContextMode = "aggressive" // TokenBudget=1500, MaxItems=10
)

// StrategyOptions contains options passed to strategies
type StrategyOptions struct {
	Mode        ContextMode
	TokenBudget int
	MaxItems    int
}

// GetDefaults returns default values for a mode
func (o StrategyOptions) GetDefaults() StrategyOptions {
	switch o.Mode {
	case ModePrecise:
		return StrategyOptions{Mode: ModePrecise, TokenBudget: 300, MaxItems: 3}
	case ModeAggressive:
		return StrategyOptions{Mode: ModeAggressive, TokenBudget: 1500, MaxItems: 10}
	default: // balanced
		return StrategyOptions{Mode: ModeBalanced, TokenBudget: 800, MaxItems: 6}
	}
}

// ResolveMode converts string mode to ContextMode
func ResolveMode(mode string) ContextMode {
	switch mode {
	case "precise":
		return ModePrecise
	case "aggressive":
		return ModeAggressive
	default:
		return ModeBalanced
	}
}

// ContextStrategy is the interface for context selection strategies
type ContextStrategy interface {
	Name() string
	Select(results []pkg.StrategySearchResult, query string, opts StrategyOptions) []pkg.StrategyContextItem
	Assemble(items []pkg.StrategyContextItem, opts StrategyOptions) pkg.StrategyAssembledContext
}

// strategyRegistry holds all registered strategies
var strategyRegistry = map[string]ContextStrategy{
	"topk_excerpt":          &TopKExcerptStrategy{},
	"recency_boost_select":  &RecencyBoostStrategy{},
	"diversity_select":      &DiversityStrategy{},
}

// GetStrategy returns a strategy by name, returns nil if not found
func GetStrategy(name string) ContextStrategy {
	if s, ok := strategyRegistry[name]; ok {
		return s
	}
	return nil
}

// DefaultStrategy is the fallback strategy
const DefaultStrategy = "topk_excerpt"
