// app/service.go - Core application service with business logic
// Business logic must use Store interface, never direct SQL
package app

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/google/uuid"
	ctxpkg "github.com/omnimemora/local-runtime/app/context"
	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/metering"
	"github.com/omnimemora/local-runtime/pkg"
	"github.com/omnimemora/local-runtime/policy"
	"github.com/omnimemora/local-runtime/scope"
	"github.com/omnimemora/local-runtime/store"
)

// Service is the core application service
type Service struct {
	cfg            *config.RuntimeConfig
	store          store.Store
	scopeModel     *scope.Model
	metering       *metering.Collector
	ctxAssembler   *ctxpkg.Assembler // Phase 2c: context strategy assembler
	policyManager  *policy.Manager   // CSP-001: compile strategy policy manager
}

// NewService creates a new application service.
// CSP-001: policy manager is initialised here and LoadActive is called once at
// startup; strategy resolution consults the policy manager but falls back to
// built-in defaults safely if the policy directory is missing or corrupt.
func NewService(cfg *config.RuntimeConfig, store store.Store, meterCollector *metering.Collector) *Service {
	pm := policy.NewManager("")
	// Load active policy at startup; errors are logged but never fail service init
	if err := pm.LoadActive(); err != nil {
		log.Printf("policy manager: LoadActive warning (builtin fallback active): %v", err)
	}
	return &Service{
		cfg:           cfg,
		store:         store,
		scopeModel:    scope.NewModel(cfg),
		metering:      meterCollector,
		ctxAssembler:  ctxpkg.NewAssembler(), // Phase 2c
		policyManager: pm,
	}
}

// WriteMemory handles memory write with scope enforcement and metering
func (s *Service) WriteMemory(ctx context.Context, req *pkg.WriteRequest, scopeRef *pkg.ScopeRef) (*pkg.WriteResponse, error) {
	// Apply scope defaults BEFORE enforcement
	// This is the single authoritative point for scope defaults
	if scopeRef.Scope == pkg.ScopeAgent && scopeRef.SharingMode == "" {
		scopeRef.SharingMode = pkg.SharingModeIsolated
	}
	if scopeRef.Scope == pkg.ScopeWorkspace && scopeRef.SharingMode == "" {
		scopeRef.SharingMode = pkg.SharingModeShared
	}

	// Custom scope not implemented
	if scopeRef.Scope == pkg.ScopeCustom {
		return nil, NewNotImplementedError("custom scope")
	}

	// Enforce scope rules
	if err := s.scopeModel.EnforceWrite(scopeRef); err != nil {
		return nil, NewScopeError(err.Error())
	}

	// Calculate content hash for dedup
	hasher := sha256.New()
	hasher.Write([]byte(req.Content))
	contentHash := hex.EncodeToString(hasher.Sum(nil))

	// Create memory record
	now := time.Now().UTC()
	record := &pkg.MemoryRecord{
		MemoryID:    fmt.Sprintf("mem_%s", uuid.New().String()[:8]),
		Content:     req.Content,
		ContentHash: contentHash,
		Metadata:    req.Metadata,
		ScopeRef:    scopeRef,
		CreatedAt:   now,
		UpdatedAt:   now,
	}

	// Dedup check within same scope (includes tenant_id)
	existingID, err := s.store.QueryByHash(ctx, contentHash, scopeRef)
	if err == nil && existingID != "" {
		s.recordWriteMetering(scopeRef, req, existingID, true)
		return &pkg.WriteResponse{
			MemoryID:    existingID,
			Status:      "written",
			Scope:       scopeRef.Scope,
			SharingMode: scopeRef.SharingMode,
			CreatedAt:   now,
			RequestID:   req.RequestID,
			DedupHit:    true,
		}, nil
	}

	// Write to store
	if err := s.store.Write(ctx, record); err != nil {
		return nil, NewStoreError("failed to write memory", err)
	}

	s.recordWriteMetering(scopeRef, req, record.MemoryID, false)

	return &pkg.WriteResponse{
		MemoryID:    record.MemoryID,
		Status:      "written",
		Scope:       scopeRef.Scope,
		SharingMode: scopeRef.SharingMode,
		CreatedAt:   now,
		RequestID:   req.RequestID,
		DedupHit:    false,
	}, nil
}

// QueryMemory handles memory query with scope enforcement
func (s *Service) QueryMemory(ctx context.Context, req *pkg.QueryRequest, scopeRef *pkg.ScopeRef) (*pkg.QueryResult, error) {
	// Custom scope not implemented
	if scopeRef.Scope == pkg.ScopeCustom {
		return nil, NewNotImplementedError("custom scope")
	}

	// Enforce scope rules for read
	if err := s.scopeModel.EnforceRead(scopeRef); err != nil {
		return nil, NewScopeError(err.Error())
	}

	startTime := time.Now()

	// Execute query through store (store handles scope + tenant filtering)
	queryReq := &store.QueryRequest{
		Query:     req.Query,
		ScopeRef:  scopeRef,
		Limit:     req.Limit,
		RequestID: req.RequestID,
	}

	result, err := s.store.Query(ctx, queryReq)
	if err != nil {
		return nil, NewStoreError("query failed", err)
	}

	tookMs := time.Since(startTime).Milliseconds()

	response := &pkg.QueryResult{
		RequestID:    req.RequestID,
		Query:        req.Query,
		Results:      make([]pkg.QueryMatch, len(result.Results)),
		Total:        result.Total,
		ScopeApplied: scopeRef.Scope,
		TookMs:       tookMs,
	}

	for i, r := range result.Results {
		response.Results[i] = pkg.QueryMatch{
			MemoryID:  r.MemoryID,
			Content:   r.Content,
			Score:     r.Score,
			Scope:     r.Scope,
			CreatedAt: r.CreatedAt,
			Metadata:  r.Metadata,
		}
	}

	s.recordQueryMetering(scopeRef, req.RequestID, req.Query, len(result.Results))

	return response, nil
}

// SearchMemory handles keyword search with scope enforcement and Phase 2a ranking
func (s *Service) SearchMemory(ctx context.Context, req *pkg.SearchRequest, scopeRef *pkg.ScopeRef) (*pkg.SearchResponse, error) {
	// Custom scope not implemented
	if scopeRef.Scope == pkg.ScopeCustom {
		return nil, NewNotImplementedError("custom scope")
	}

	// Enforce scope rules for read
	if err := s.scopeModel.EnforceRead(scopeRef); err != nil {
		return nil, NewScopeError(err.Error())
	}

	startTime := time.Now()

	// Execute search through store
	searchReq := &store.SearchRequest{
		Keyword:   req.Keyword,
		ScopeRef:  scopeRef,
		Limit:     req.Limit,
		RequestID: req.RequestID,
	}

	result, err := s.store.Search(ctx, searchReq)
	if err != nil {
		return nil, NewStoreError("search failed", err)
	}

	// Get capabilities for ranking decisions
	var capabilities store.SearchCapabilities
	if sqliteStore, ok := s.store.(*store.SQLiteStore); ok {
		capabilities = sqliteStore.GetCapabilities()
	}

	// Phase 2a: Rank candidates
	scoredResults := s.rankCandidates(result.Results, req.Keyword, capabilities)

	// Sort: final_score DESC, updated_at DESC, memory_id ASC
	sortSearchResults(scoredResults)

	// Top-k truncation
	limit := req.Limit
	if limit <= 0 {
		limit = 10
	}
	if len(scoredResults) > limit {
		scoredResults = scoredResults[:limit]
	}

	tookMs := time.Since(startTime).Milliseconds()

	// Build response
	response := &pkg.SearchResponse{
		RequestID:    req.RequestID,
		Keyword:      req.Keyword,
		Results:      make([]pkg.SearchResultItem, len(scoredResults)),
		Total:        len(scoredResults),
		ScopeApplied: scopeRef.Scope,
		TookMs:       tookMs,
	}

	for i, r := range scoredResults {
		item := pkg.SearchResultItem{
			MemoryID:      r.Candidate.MemoryID,
			Content:       r.Candidate.Content,
			Score:         r.FinalScore,
			VectorScore:   0, // Reserved for Phase 2c
			TokenEstimate: len(r.Candidate.Content) / 4,
			CreatedAt:     r.Candidate.CreatedAt,
			UpdatedAt:     r.Candidate.UpdatedAt,
		}
		if req.Options.IncludeBreakdown {
			item.ScoreBreakdown = &pkg.ScoreBreakdown{
				TextMatchScore: r.TextMatchScore,
				RecencyBoost:   r.RecencyBoost,
				AccessBoost:    r.AccessBoost,
				VectorScore:    0,
			}
		}
		response.Results[i] = item
	}

	// Phase 2c: Optional context assembly via strategy layer
	var rawTokens, compressedTokens, savedTokens, assembledHits int
	var resolvedStrategy, contextMode string
	var strategyEffectiveness *pkg.StrategyEffectiveness

	if req.Options.AssembleContext && len(scoredResults) > 0 {
		// Convert scoredResults to strategy input
		results := make([]pkg.StrategySearchResult, len(scoredResults))
		for i, r := range scoredResults {
			results[i] = pkg.StrategySearchResult{
				MemoryID:      r.Candidate.MemoryID,
				Content:       r.Candidate.Content,
				Score:         r.FinalScore,
				TokenEstimate: estimateTokens(r.Candidate.Content),
				CreatedAt:     r.Candidate.CreatedAt,
			}
		}

		// CSP-001: Strategy resolution via policy manager
		// requestedStrategy is the raw value from request (may be "auto" or empty or explicit)
		requestedStrategy := req.Options.ContextStrategy

		if requestedStrategy == "auto" {
			// Use policy auto rules (or built-in fallback)
			resolvedStrategy = s.policyManager.ResolveAuto(req.Keyword)
		} else if requestedStrategy != "" {
			// Explicit strategy: validate it is known, fall back to topk_excerpt if unknown
			if ctxpkg.GetStrategy(requestedStrategy) == nil {
				resolvedStrategy = ctxpkg.DefaultStrategy
			} else {
				resolvedStrategy = requestedStrategy
			}
		} else {
			// Blank strategy: use policy default (or built-in fallback)
			resolvedStrategy = s.policyManager.GetDefaultStrategy()
		}

		// CSP-001: Mode resolution — use policy mode defaults (or built-in fallback)
		contextMode = req.Options.ContextMode
		mode := ctxpkg.ResolveMode(contextMode)
		tokenBudget, maxItems := s.policyManager.GetModeDefaults(string(mode))
		opts := ctxpkg.StrategyOptions{
			Mode:        mode,
			TokenBudget: tokenBudget,
			MaxItems:    maxItems,
		}

		// Build cache key components with scope info
		cacheComp := ctxpkg.CacheKeyComponents{
			TenantID:    scopeRef.TenantID,
			WorkspaceID: scopeRef.WorkspaceID,
			AgentID:     scopeRef.AgentID,
			Scope:       string(scopeRef.Scope),
			Query:       req.Keyword,
		}

		// Execute strategy
		ctxResult := s.ctxAssembler.AssembleContext(results, req.Keyword, resolvedStrategy, opts, cacheComp)

		// Honest token accounting: use actual values from assembler
		if ctxResult.Context != nil && len(ctxResult.Items) > 0 {
			rawTokens = ctxResult.RawTokens                           // honest sum of item.Tokens (original content)
			compressedTokens = estimateTokens(ctxResult.Context.Text) // actual assembled text tokens
			savedTokens = rawTokens - compressedTokens
			if savedTokens < 0 {
				savedTokens = 0
			}
			assembledHits = ctxResult.AssembledHits
			strategyEffectiveness = ctxResult.Effectiveness

			// Assembled is true only if we have meaningful content
			assembled := ctxResult.Context.TotalTokens > 0

			response.Context = &pkg.AssembledContext{
				Assembled:        assembled,
				Strategy:         ctxResult.ResolvedStrategy, // always the resolved strategy
				Items:            []pkg.ContextItem{},
				CombinedText:     ctxResult.Context.Text,
				RawTokens:        rawTokens,
				CompressedTokens: compressedTokens,
				SavedTokens:      savedTokens,
				// Phase 3: Enhanced observability
				CompressionRatio: func() float64 {
					if rawTokens > 0 {
						return float64(compressedTokens) / float64(rawTokens)
					}
					return 0
				}(),
				StrategyResolved: ctxResult.ResolvedStrategy,
				Mode:             contextMode,
				ItemsSelected:    assembledHits,
				TokenBudgetUsed:  compressedTokens,
			}
		}
	}
	// When assemble_context=false, all token fields remain 0 (honest default)

	// CSP-001: Capture policy evidence from active policy
	policyResolved := s.policyManager.GetResolved()

	s.recordSearchMetering(
		scopeRef,
		req.RequestID,
		result.Total,
		len(scoredResults),
		rawTokens,
		compressedTokens,
		savedTokens,
		assembledHits,
		resolvedStrategy,
		contextMode,
		strategyEffectiveness,
		policyResolved.PolicyVersion,
		string(policyResolved.PolicySource),
		req.Options.ContextStrategy, // raw requested (may be "auto" or empty)
		resolvedStrategy,
		string(ctxpkg.ResolveMode(contextMode)),
	)

	return response, nil
}

// WriteMemoryWithAccessPlan orchestrates multi-domain write execution from request-level AccessPlan.
// Store remains a single-scope executor; orchestration stays in service layer.
func (s *Service) WriteMemoryWithAccessPlan(ctx context.Context, req *pkg.WriteRequest, fallbackScope *pkg.ScopeRef) (*pkg.WriteResponse, error) {
	if req == nil {
		return nil, NewScopeError("write request is nil")
	}
	if req.AccessPlan == nil {
		return s.WriteMemory(ctx, req, fallbackScope)
	}

	plan := req.AccessPlan
	if plan.PrimaryWriteDomain == nil {
		return nil, NewScopeError("access_plan.primary_write_domain is required")
	}

	trace := &pkg.EnforcementTrace{
		PlannedReadDomains:    append([]pkg.MemoryDomainRef{}, plan.ReadDomains...),
		PlannedWriteDomains:   make([]pkg.MemoryDomainRef, 0, 1+len(plan.SecondaryWriteDomains)),
		ActualEnforcedDomains: []pkg.EnforcedDomain{},
	}
	trace.PlannedWriteDomains = append(trace.PlannedWriteDomains, *plan.PrimaryWriteDomain)
	trace.PlannedWriteDomains = append(trace.PlannedWriteDomains, plan.SecondaryWriteDomains...)

	primaryResp, primaryTrace, primaryErr := s.writeOneDomainWithPlan(ctx, req, fallbackScope, plan, *plan.PrimaryWriteDomain, true)
	trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, primaryTrace)
	if primaryErr != nil {
		if appErr, ok := primaryErr.(*AppError); ok {
			return nil, appErr
		}
		return nil, NewStoreError("access-plan primary write failed", primaryErr)
	}

	for _, secondary := range plan.SecondaryWriteDomains {
		if !plan.AllowSecondaryWrites {
			trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, pkg.EnforcedDomain{
				DomainID:  secondary.DomainID,
				Operation: "write",
				Decision:  "rejected",
				Reason:    "secondary_write_not_authorized",
			})
			continue
		}
		_, secondaryTrace, secondaryErr := s.writeOneDomainWithPlan(ctx, req, fallbackScope, plan, secondary, false)
		if secondaryErr != nil {
			secondaryTrace.Decision = "failed"
			if secondaryTrace.Reason == "" {
				secondaryTrace.Reason = secondaryErr.Error()
			}
		}
		trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, secondaryTrace)
	}

	primaryResp.EnforcementTrace = trace
	return primaryResp, nil
}

// QueryMemoryWithAccessPlan orchestrates ordered multi-domain read execution.
func (s *Service) QueryMemoryWithAccessPlan(ctx context.Context, req *pkg.QueryRequest, fallbackScope *pkg.ScopeRef) (*pkg.QueryResult, error) {
	if req == nil {
		return nil, NewScopeError("query request is nil")
	}
	if req.AccessPlan == nil {
		return s.QueryMemory(ctx, req, fallbackScope)
	}

	startTime := time.Now()
	plan := req.AccessPlan
	trace := &pkg.EnforcementTrace{
		PlannedReadDomains:    append([]pkg.MemoryDomainRef{}, plan.ReadDomains...),
		PlannedWriteDomains:   []pkg.MemoryDomainRef{},
		ActualEnforcedDomains: []pkg.EnforcedDomain{},
	}

	combined := make([]pkg.QueryMatch, 0)
	scopeApplied := pkg.ScopeType("")
	queryReq := *req
	queryReq.AccessPlan = nil

	for _, domain := range plan.ReadDomains {
		scopeRef, rejectReason, err := s.scopeRefFromAccessDomain(plan, fallbackScope, domain)
		if rejectReason != "" {
			trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, pkg.EnforcedDomain{
				DomainID:  domain.DomainID,
				Operation: "query",
				Decision:  "rejected",
				Reason:    rejectReason,
			})
			continue
		}
		if err != nil {
			trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, pkg.EnforcedDomain{
				DomainID:  domain.DomainID,
				Operation: "query",
				Decision:  "failed",
				Reason:    err.Error(),
			})
			continue
		}

		subResp, subErr := s.QueryMemory(ctx, &queryReq, scopeRef)
		if subErr != nil {
			trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, pkg.EnforcedDomain{
				DomainID:  domain.DomainID,
				ScopeRef:  scopeRef,
				Operation: "query",
				Decision:  "failed",
				Reason:    subErr.Error(),
			})
			continue
		}
		if scopeApplied == "" {
			scopeApplied = subResp.ScopeApplied
		}
		for i := range subResp.Results {
			subResp.Results[i].DomainID = domain.DomainID
		}
		combined = append(combined, subResp.Results...)
		trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, pkg.EnforcedDomain{
			DomainID:    domain.DomainID,
			ScopeRef:    scopeRef,
			Operation:   "query",
			Decision:    "applied",
			ResultCount: len(subResp.Results),
		})
	}

	if req.Limit > 0 && len(combined) > req.Limit {
		combined = combined[:req.Limit]
	}
	if scopeApplied == "" && fallbackScope != nil {
		scopeApplied = fallbackScope.Scope
	}

	return &pkg.QueryResult{
		RequestID:        req.RequestID,
		Query:            req.Query,
		Results:          combined,
		Total:            len(combined),
		ScopeApplied:     scopeApplied,
		TookMs:           time.Since(startTime).Milliseconds(),
		EnforcementTrace: trace,
	}, nil
}

// SearchMemoryWithAccessPlan orchestrates ordered multi-domain search execution.
func (s *Service) SearchMemoryWithAccessPlan(ctx context.Context, req *pkg.SearchRequest, fallbackScope *pkg.ScopeRef) (*pkg.SearchResponse, error) {
	if req == nil {
		return nil, NewScopeError("search request is nil")
	}
	if req.AccessPlan == nil {
		return s.SearchMemory(ctx, req, fallbackScope)
	}

	startTime := time.Now()
	plan := req.AccessPlan
	trace := &pkg.EnforcementTrace{
		PlannedReadDomains:    append([]pkg.MemoryDomainRef{}, plan.ReadDomains...),
		PlannedWriteDomains:   []pkg.MemoryDomainRef{},
		ActualEnforcedDomains: []pkg.EnforcedDomain{},
	}

	combined := make([]pkg.SearchResultItem, 0)
	scopeApplied := pkg.ScopeType("")
	searchReq := *req
	searchReq.AccessPlan = nil

	for _, domain := range plan.ReadDomains {
		scopeRef, rejectReason, err := s.scopeRefFromAccessDomain(plan, fallbackScope, domain)
		if rejectReason != "" {
			trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, pkg.EnforcedDomain{
				DomainID:  domain.DomainID,
				Operation: "search",
				Decision:  "rejected",
				Reason:    rejectReason,
			})
			continue
		}
		if err != nil {
			trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, pkg.EnforcedDomain{
				DomainID:  domain.DomainID,
				Operation: "search",
				Decision:  "failed",
				Reason:    err.Error(),
			})
			continue
		}

		subResp, subErr := s.SearchMemory(ctx, &searchReq, scopeRef)
		if subErr != nil {
			trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, pkg.EnforcedDomain{
				DomainID:  domain.DomainID,
				ScopeRef:  scopeRef,
				Operation: "search",
				Decision:  "failed",
				Reason:    subErr.Error(),
			})
			continue
		}
		if scopeApplied == "" {
			scopeApplied = subResp.ScopeApplied
		}
		for i := range subResp.Results {
			subResp.Results[i].DomainID = domain.DomainID
			if subResp.Results[i].Scope == "" {
				subResp.Results[i].Scope = subResp.ScopeApplied
			}
		}
		combined = append(combined, subResp.Results...)
		trace.ActualEnforcedDomains = append(trace.ActualEnforcedDomains, pkg.EnforcedDomain{
			DomainID:    domain.DomainID,
			ScopeRef:    scopeRef,
			Operation:   "search",
			Decision:    "applied",
			ResultCount: len(subResp.Results),
		})
	}

	if req.Limit > 0 && len(combined) > req.Limit {
		combined = combined[:req.Limit]
	}
	if scopeApplied == "" && fallbackScope != nil {
		scopeApplied = fallbackScope.Scope
	}

	return &pkg.SearchResponse{
		RequestID:        req.RequestID,
		Keyword:          req.Keyword,
		Results:          combined,
		Total:            len(combined),
		ScopeApplied:     scopeApplied,
		TookMs:           time.Since(startTime).Milliseconds(),
		Context:          nil,
		EnforcementTrace: trace,
	}, nil
}

func (s *Service) writeOneDomainWithPlan(
	ctx context.Context,
	req *pkg.WriteRequest,
	fallbackScope *pkg.ScopeRef,
	plan *pkg.AccessPlan,
	domain pkg.MemoryDomainRef,
	primary bool,
) (*pkg.WriteResponse, pkg.EnforcedDomain, error) {
	if domain.ScopeType == pkg.DomainSharedReadOnly {
		trace := pkg.EnforcedDomain{
			DomainID:  domain.DomainID,
			Operation: "write",
			Decision:  "rejected",
			Reason:    "shared_read_only domain is read-only",
		}
		if primary {
			return nil, trace, NewScopeError(trace.Reason)
		}
		return nil, trace, nil
	}

	scopeRef, rejectReason, err := s.scopeRefFromAccessDomain(plan, fallbackScope, domain)
	if rejectReason != "" {
		trace := pkg.EnforcedDomain{
			DomainID:  domain.DomainID,
			Operation: "write",
			Decision:  "rejected",
			Reason:    rejectReason,
		}
		if primary {
			if domain.ScopeType == pkg.DomainCustomShared {
				return nil, trace, NewNotImplementedError("custom_shared access-plan domain")
			}
			return nil, trace, NewScopeError(rejectReason)
		}
		return nil, trace, nil
	}
	if err != nil {
		trace := pkg.EnforcedDomain{
			DomainID:  domain.DomainID,
			Operation: "write",
			Decision:  "failed",
			Reason:    err.Error(),
		}
		return nil, trace, err
	}

	writeReq := *req
	writeReq.AccessPlan = nil
	resp, writeErr := s.WriteMemory(ctx, &writeReq, scopeRef)
	if writeErr != nil {
		trace := pkg.EnforcedDomain{
			DomainID:  domain.DomainID,
			ScopeRef:  scopeRef,
			Operation: "write",
			Decision:  "failed",
			Reason:    writeErr.Error(),
		}
		return nil, trace, writeErr
	}

	trace := pkg.EnforcedDomain{
		DomainID:  domain.DomainID,
		ScopeRef:  scopeRef,
		Operation: "write",
		Decision:  "applied",
		MemoryID:  resp.MemoryID,
	}
	return resp, trace, nil
}

func (s *Service) scopeRefFromAccessDomain(
	plan *pkg.AccessPlan,
	fallbackScope *pkg.ScopeRef,
	domain pkg.MemoryDomainRef,
) (*pkg.ScopeRef, string, error) {
	identity := &pkg.AccessPlanIdentity{}
	if plan != nil && plan.Identity != nil {
		identity = plan.Identity
	}

	scopeRef := &pkg.ScopeRef{}
	if fallbackScope != nil {
		*scopeRef = *fallbackScope
	}

	tenantID := strings.TrimSpace(domain.TenantID)
	if tenantID == "" {
		tenantID = strings.TrimSpace(identity.TenantID)
	}
	if tenantID == "" && fallbackScope != nil {
		tenantID = strings.TrimSpace(fallbackScope.TenantID)
	}
	scopeRef.TenantID = tenantID

	switch domain.ScopeType {
	case pkg.DomainInstancePrivate:
		instanceID := strings.TrimSpace(identity.InstanceID)
		if instanceID == "" {
			instanceID = strings.TrimSpace(domain.ScopeKey)
		}
		if instanceID == "" {
			return nil, "", fmt.Errorf("instance_id is required for instance_private domain")
		}
		scopeRef.Scope = pkg.ScopeAgent
		scopeRef.AgentID = instanceID
		scopeRef.SharingMode = pkg.SharingModeIsolated
		scopeRef.WorkspaceID = ""
		scopeRef.UserID = ""
		scopeRef.CustomScopeID = ""
	case pkg.DomainWorkspaceShared:
		workspaceID := strings.TrimSpace(domain.ScopeKey)
		if workspaceID == "" {
			return nil, "", fmt.Errorf("scope_key is required for workspace_shared domain")
		}
		scopeRef.Scope = pkg.ScopeWorkspace
		scopeRef.WorkspaceID = workspaceID
		scopeRef.SharingMode = pkg.SharingModeShared
		scopeRef.UserID = ""
		scopeRef.CustomScopeID = ""
	case pkg.DomainUserShared:
		userID := strings.TrimSpace(domain.ScopeKey)
		if userID == "" {
			return nil, "", fmt.Errorf("scope_key is required for user_shared domain")
		}
		scopeRef.Scope = pkg.ScopeUser
		scopeRef.UserID = userID
		scopeRef.SharingMode = pkg.SharingModeShared
		scopeRef.WorkspaceID = ""
		scopeRef.CustomScopeID = ""
	case pkg.DomainSharedReadOnly:
		workspaceID := strings.TrimSpace(domain.ScopeKey)
		if workspaceID == "" {
			return nil, "", fmt.Errorf("scope_key is required for shared_read_only domain")
		}
		scopeRef.Scope = pkg.ScopeWorkspace
		scopeRef.WorkspaceID = workspaceID
		scopeRef.SharingMode = pkg.SharingModeSharedReadOnly
		scopeRef.UserID = ""
		scopeRef.CustomScopeID = ""
	case pkg.DomainCustomShared:
		return nil, "custom_shared domain is not implemented", nil
	default:
		return nil, "", fmt.Errorf("unsupported access-plan domain scope_type=%q", domain.ScopeType)
	}

	if domain.ScopeType == pkg.DomainSharedReadOnly {
		return scopeRef, "", nil
	}
	if domain.SharingMode != "" {
		scopeRef.SharingMode = domain.SharingMode
	}
	return scopeRef, "", nil
}

// DeleteMemory handles memory deletion with scope enforcement
func (s *Service) DeleteMemory(ctx context.Context, req *pkg.DeleteRequest, scopeRef *pkg.ScopeRef) (*pkg.DeleteResponse, error) {
	// Custom scope not implemented
	if scopeRef.Scope == pkg.ScopeCustom {
		return nil, NewNotImplementedError("custom scope")
	}

	// Enforce scope rules for delete
	if err := s.scopeModel.EnforceWrite(scopeRef); err != nil {
		return nil, NewScopeError(err.Error())
	}

	// Execute delete through store
	err := s.store.Delete(ctx, req.MemoryID, scopeRef)
	if err != nil {
		return nil, NewStoreError("delete failed", err)
	}

	return &pkg.DeleteResponse{
		MemoryID:  req.MemoryID,
		Status:    "deleted",
		RequestID: req.RequestID,
	}, nil
}

// GetMetrics returns aggregated metrics
func (s *Service) GetMetrics(ctx context.Context) (*pkg.MetricsResponse, error) {
	data, err := s.metering.GetMetricsData(ctx)
	if err != nil {
		return nil, err
	}

	// Runtime-session total savings: resets on process restart.
	// Calendar buckets (today/week/month) remain cumulative by date.
	sessionSaved := int64(0)
	if saved, err := s.metering.GetSavedTokensSince(ctx, s.scopeModel.StartedAt()); err == nil {
		sessionSaved = saved
	}

	resp := &pkg.MetricsResponse{
		Runtime: pkg.RuntimeMetrics{
			Version:       s.cfg.Version,
			UptimeSeconds: int64(time.Since(s.scopeModel.StartedAt()).Seconds()),
			Mode:          s.cfg.Mode,
		},
		Totals: pkg.TotalsMetrics{
			MemoryCount:           data.Totals.MemoryCount,
			TotalWrites:           data.Totals.TotalWrites,
			TotalQueries:          data.Totals.TotalQueries,
			TotalInputTokens:      data.Totals.TotalInputTokens,
			TotalCompressedTokens: data.Totals.TotalCompressedTokens,
			TotalSavedTokens:      data.Totals.TotalSavedTokens,
			TotalQueryCount:       data.Totals.TotalQueryCount,
			TotalRecallHits:       data.Totals.TotalRecallHits,
		},
		ByScope: make(map[string]map[string]pkg.ScopeMetrics),
		ByDay:   make([]pkg.DailyMetrics, len(data.ByDay)),
		// Phase 3: Token savings and efficiency
		TokenSavings: &pkg.TokenSavingsMetrics{
			TotalSavedTokens: sessionSaved,
			TodaySavedTokens: data.TodaySavedTokens,
			WeekSavedTokens:  data.WeekSavedTokens,
			MonthSavedTokens: data.MonthSavedTokens,
		},
		Efficiency: &pkg.EfficiencyMetrics{
			AvgCompressionRatio: data.AvgCompressionRatio,
			AvgSavedPerQuery:    data.AvgSavedPerQuery,
		},
		DemoEventsOccurred: data.DemoEventsOccurred,
	}

	for _, sd := range data.ByScope {
		scopeKey := sd.Scope
		if _, ok := resp.ByScope[scopeKey]; !ok {
			resp.ByScope[scopeKey] = make(map[string]pkg.ScopeMetrics)
		}
		key := sd.AgentID
		if scopeKey == "workspace" {
			key = sd.WorkspaceID
		}
		resp.ByScope[scopeKey][key] = pkg.ScopeMetrics{
			TotalSavedTokens: sd.SavedTokens,
		}
	}

	for i, dd := range data.ByDay {
		resp.ByDay[i] = pkg.DailyMetrics{
			Date:        dd.Date,
			SavedTokens: dd.SavedTokens,
			QueryCount:  dd.QueryCount,
		}
	}

	return resp, nil
}

// GetHealth returns health status
func (s *Service) GetHealth(ctx context.Context) (*pkg.HealthResponse, error) {
	uptime := time.Since(s.scopeModel.StartedAt()).Seconds()

	memoryCount, err := s.store.Count(ctx)
	if err != nil {
		memoryCount = 0
	}

	return &pkg.HealthResponse{
		Status:               "ok",
		Version:              s.cfg.Version,
		Mode:                 s.cfg.Mode,
		UptimeSeconds:        int64(uptime),
		StoreType:            s.cfg.Local.DBType,
		RegisteredConnectors: 0,
		MemoryCount:          memoryCount,
	}, nil
}

// recordWriteMetering records a metering event for write operations
func (s *Service) recordWriteMetering(scopeRef *pkg.ScopeRef, req *pkg.WriteRequest, memoryID string, dedupHit bool) {
	inputTokens := len(req.Content) / 4
	if inputTokens == 0 {
		inputTokens = 1
	}
	compressedTokens := inputTokens
	savedTokens := 0
	if !dedupHit {
		savedTokens = inputTokens - compressedTokens
	}

	event := &metering.Event{
		EventID:          fmt.Sprintf("evt_%s", uuid.New().String()[:8]),
		RequestID:        req.RequestID,
		EventType:        "memory_write",
		TenantID:         scopeRef.TenantID,
		UserID:           scopeRef.UserID,
		WorkspaceID:      scopeRef.WorkspaceID,
		AgentID:          scopeRef.AgentID,
		Scope:            string(scopeRef.Scope),
		SharingMode:      string(scopeRef.SharingMode),
		InputTokens:      inputTokens,
		CompressedTokens: compressedTokens,
		SavedTokens:      savedTokens,
		QueryCount:       0,
		RecallHits:       0,
		RecallHitRate:    0,
		Timestamp:        time.Now().UTC(),
		RuntimeVersion:   s.cfg.Version,
		StoreType:        s.cfg.Local.DBType,
	}

	if err := s.metering.Record(event); err != nil {
		log.Printf(
			"metering record error: request_id=%s event=memory_write tenant=%s workspace=%s agent=%s err=%v",
			req.RequestID,
			scopeRef.TenantID,
			scopeRef.WorkspaceID,
			scopeRef.AgentID,
			err,
		)
	}
}

// recordQueryMetering records a metering event for query operations
func (s *Service) recordQueryMetering(scopeRef *pkg.ScopeRef, requestID, query string, hitCount int) {
	inputTokens := len(query) / 4
	if inputTokens == 0 {
		inputTokens = 1
	}

	recallHitRate := 0.0
	if hitCount > 0 {
		recallHitRate = 1.0
	}

	event := &metering.Event{
		EventID:          fmt.Sprintf("evt_%s", uuid.New().String()[:8]),
		RequestID:        requestID,
		EventType:        "memory_query",
		TenantID:         scopeRef.TenantID,
		UserID:           scopeRef.UserID,
		WorkspaceID:      scopeRef.WorkspaceID,
		AgentID:          scopeRef.AgentID,
		Scope:            string(scopeRef.Scope),
		SharingMode:      string(scopeRef.SharingMode),
		InputTokens:      inputTokens,
		CompressedTokens: inputTokens,
		SavedTokens:      0,
		QueryCount:       1,
		RecallHits:       hitCount,
		RecallHitRate:    recallHitRate,
		Timestamp:        time.Now().UTC(),
		RuntimeVersion:   s.cfg.Version,
		StoreType:        s.cfg.Local.DBType,
	}

	if err := s.metering.Record(event); err != nil {
		log.Printf(
			"metering record error: request_id=%s event=memory_query tenant=%s workspace=%s agent=%s err=%v",
			requestID,
			scopeRef.TenantID,
			scopeRef.WorkspaceID,
			scopeRef.AgentID,
			err,
		)
	}
}

// scoredSearchResult holds a candidate with its computed scores
type scoredSearchResult struct {
	Candidate      store.SearchCandidate
	TextMatchScore float64
	RecencyBoost   float64
	AccessBoost    float64
	FinalScore     float64
}

// rankCandidates applies Phase 2a ranking logic to search candidates
func (s *Service) rankCandidates(candidates []store.SearchCandidate, keyword string, capabilities store.SearchCapabilities) []scoredSearchResult {
	results := make([]scoredSearchResult, 0, len(candidates))

	for _, c := range candidates {
		sr := scoredSearchResult{Candidate: c}

		// Calculate text_match_score
		if capabilities.BM25Available && c.RawTextScore != 0 {
			// BM25 is inverse (lower = more relevant), so invert it
			sr.TextMatchScore = 1.0 / (1.0 + c.RawTextScore)
		} else {
			// fallback_text_score: exact phrase > all terms > partial > LIKE
			sr.TextMatchScore = s.computeFallbackTextScore(c.Content, keyword)
		}

		// Calculate recency_boost
		sr.RecencyBoost = s.calcRecencyBoost(c.UpdatedAt)

		// Calculate access_boost
		sr.AccessBoost = s.calcAccessBoost(c.AccessCount)

		// Final score (vector_score = 0 for Phase 2a)
		sr.FinalScore = sr.TextMatchScore + sr.RecencyBoost + sr.AccessBoost

		results = append(results, sr)
	}

	return results
}

// computeFallbackTextScore calculates text match when BM25 is unavailable
func (s *Service) computeFallbackTextScore(content, keyword string) float64 {
	// Exact phrase hit
	if strings.Contains(strings.ToLower(content), strings.ToLower(keyword)) {
		// Check if it's an exact phrase match
		lowerContent := strings.ToLower(content)
		lowerKeyword := strings.ToLower(keyword)
		// Look for keyword as a distinct phrase (word boundaries)
		words := strings.Fields(lowerKeyword)
		if len(words) > 1 {
			// Multi-word phrase - check if all words appear consecutively
			for i := 0; i <= len(lowerContent)-len(lowerKeyword); i++ {
				if strings.Contains(lowerContent[i:i+len(lowerKeyword)], lowerKeyword) {
					return 1.00 // Exact phrase
				}
			}
		}
		// Single word or multi-word but not exact phrase
		if strings.Contains(lowerContent, lowerKeyword) {
			return 0.80 // All terms matched (best approximation)
		}
	}

	// Partial term match via word overlap
	contentLower := strings.ToLower(content)
	keywordLower := strings.ToLower(keyword)
	keywordWords := strings.Fields(keywordLower)
	matchedWords := 0
	for _, kw := range keywordWords {
		if strings.Contains(contentLower, kw) {
			matchedWords++
		}
	}
	if matchedWords > 0 {
		return 0.50 // Partial terms matched
	}

	return 0.30 // LIKE fallback (lowest)
}

// calcRecencyBoost applies time-based boost
func (s *Service) calcRecencyBoost(updatedAt time.Time) float64 {
	age := time.Since(updatedAt)
	switch {
	case age <= 24*time.Hour:
		return 0.10
	case age <= 7*24*time.Hour:
		return 0.07
	case age <= 30*24*time.Hour:
		return 0.04
	case age <= 90*24*time.Hour:
		return 0.01
	default:
		return 0.0
	}
}

// calcAccessBoost applies access count based boost
func (s *Service) calcAccessBoost(accessCount int) float64 {
	switch {
	case accessCount == 0:
		return 0.00
	case accessCount <= 3:
		return 0.02
	case accessCount <= 10:
		return 0.05
	default:
		return 0.08
	}
}

// scoredResultsSortable implements sort.Interface for scoredSearchResult
type scoredResultsSortable []scoredSearchResult

func (r scoredResultsSortable) Len() int      { return len(r) }
func (r scoredResultsSortable) Swap(i, j int) { r[i], r[j] = r[j], r[i] }
func (r scoredResultsSortable) Less(i, j int) bool {
	if r[i].FinalScore != r[j].FinalScore {
		return r[i].FinalScore > r[j].FinalScore
	}
	if !r[i].Candidate.UpdatedAt.Equal(r[j].Candidate.UpdatedAt) {
		return r[i].Candidate.UpdatedAt.After(r[j].Candidate.UpdatedAt)
	}
	return r[i].Candidate.MemoryID < r[j].Candidate.MemoryID
}

func sortSearchResults(results []scoredSearchResult) {
	sort := scoredResultsSortable(results)
	// Simple bubble sort (stable and simple for small lists)
	for i := 0; i < sort.Len()-1; i++ {
		for j := 0; j < sort.Len()-1-i; j++ {
			if sort.Less(j+1, j) {
				sort.Swap(j, j+1)
			}
		}
	}
}

// Phase 2b: Context Assembly helpers

// estimateTokens estimates token count using the standard 4-char-per-token heuristic
func estimateTokens(text string) int {
	if len(text) == 0 {
		return 0
	}
	return len(text) / 4
}

// recordSearchMetering records a metering event for search operations (Phase 2c.5 + CSP-001)
func (s *Service) recordSearchMetering(
	scopeRef *pkg.ScopeRef,
	requestID string,
	recallHits, returnedHits, rawTokens, compressedTokens, savedTokens, assembledHits int,
	contextStrategy, contextMode string,
	strategyEffectiveness *pkg.StrategyEffectiveness,
	policyVersion, policySource, strategyRequested, strategyResolved, modeResolved string,
) {
	inputTokens := 1 // Placeholder for query token estimation
	// Note: when assemble_context=false, rawTokens/compressedTokens/savedTokens/assembledHits
	// are all 0 - this is honest, not a gap. No fake compressed_tokens for non-assembly searches.

	event := &metering.Event{
		EventID:               fmt.Sprintf("evt_%s", uuid.New().String()[:8]),
		RequestID:             requestID,
		EventType:             "memory_search",
		TenantID:              scopeRef.TenantID,
		UserID:                scopeRef.UserID,
		WorkspaceID:           scopeRef.WorkspaceID,
		AgentID:               scopeRef.AgentID,
		Scope:                 string(scopeRef.Scope),
		SharingMode:           string(scopeRef.SharingMode),
		InputTokens:           inputTokens,
		CompressedTokens:      compressedTokens,
		SavedTokens:           savedTokens,
		QueryCount:            1,
		RecallHits:            recallHits,
		RecallHitRate:         0.0,
		Timestamp:             time.Now().UTC(),
		RuntimeVersion:        s.cfg.Version,
		StoreType:             s.cfg.Local.DBType,
		RawTokens:             rawTokens,
		AssembledHits:         assembledHits,
		ContextStrategy:       strategyResolved, // Phase 2c: maps to context_strategy_resolved
		ContextMode:           contextMode,     // Phase 2c: maps to context_mode_resolved
		StrategyEffectiveness: strategyEffectiveness,
		// CSP-001: compile strategy policy evidence fields
		CompileStrategyPolicyVersion:  policyVersion,
		CompileStrategyPolicySource:   policySource,
		ContextStrategyRequested:     strategyRequested,
		ContextStrategyResolved:      strategyResolved,
		ContextModeResolved:          modeResolved,
	}

	if err := s.metering.Record(event); err != nil {
		log.Printf(
			"metering record error: request_id=%s event=memory_search tenant=%s workspace=%s agent=%s err=%v",
			requestID,
			scopeRef.TenantID,
			scopeRef.WorkspaceID,
			scopeRef.AgentID,
			err,
		)
	}
}
