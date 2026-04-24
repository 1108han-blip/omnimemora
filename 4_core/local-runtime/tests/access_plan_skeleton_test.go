package tests

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/omnimemora/local-runtime/api"
	"github.com/omnimemora/local-runtime/config"
	"github.com/omnimemora/local-runtime/lifecycle"
	"github.com/omnimemora/local-runtime/pkg"
	"github.com/omnimemora/local-runtime/store"
)

func newAccessPlanTestServer(t *testing.T) *api.Server {
	t.Helper()
	tmpDir := t.TempDir()
	s, err := store.NewSQLiteStore(tmpDir)
	if err != nil {
		t.Fatalf("failed to create store: %v", err)
	}
	t.Cleanup(func() {
		_ = s.Close()
	})

	cfg := config.DefaultRuntimeConfig()
	rtCtx := &lifecycle.RuntimeContext{
		Config:  cfg,
		Store:   s,
		Version: "1.0.0",
	}
	return api.NewServer(cfg, s, rtCtx, 18765)
}

func doJSONRequest(t *testing.T, server *api.Server, method, path string, payload any, headers map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	body, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}
	req := httptest.NewRequest(method, path, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	rec := httptest.NewRecorder()
	server.Handler().ServeHTTP(rec, req)
	return rec
}

func accessPlan(identityTenant, instance string, read []pkg.MemoryDomainRef, primary *pkg.MemoryDomainRef, secondary []pkg.MemoryDomainRef, allowSecondary bool) *pkg.AccessPlan {
	return &pkg.AccessPlan{
		Identity: &pkg.AccessPlanIdentity{
			TenantID:   identityTenant,
			FamilyID:   "openclaw",
			InstanceID: instance,
			RequestID:  "req-access-plan",
		},
		ReadDomains:           read,
		PrimaryWriteDomain:    primary,
		SecondaryWriteDomains: secondary,
		AllowSecondaryWrites:  allowSecondary,
		SharingPolicySource:   "test",
	}
}

func TestAccessPlanLegacyWriteCompatibility(t *testing.T) {
	server := newAccessPlanTestServer(t)
	rec := doJSONRequest(
		t,
		server,
		"POST",
		"/memory/write",
		pkg.WriteRequest{Content: "legacy write without access plan"},
		map[string]string{
			"X-OmniMemora-Agent": "legacy_agent",
		},
	)
	if rec.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp pkg.WriteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if resp.EnforcementTrace != nil {
		t.Fatalf("legacy write should not emit enforcement_trace")
	}
}

func TestAccessPlanQueryPrivateThenWorkspaceOrder(t *testing.T) {
	server := newAccessPlanTestServer(t)
	domainPrivate := pkg.MemoryDomainRef{
		DomainID:  "d-private",
		TenantID:  "tenant-ap-1",
		ScopeType: pkg.DomainInstancePrivate,
	}
	domainWorkspace := pkg.MemoryDomainRef{
		DomainID:  "d-workspace",
		TenantID:  "tenant-ap-1",
		ScopeType: pkg.DomainWorkspaceShared,
		ScopeKey:  "ws-ap-1",
	}

	// write private
	rec := doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "accessplanmultiread shared keyword",
		AccessPlan: accessPlan(
			"tenant-ap-1",
			"inst-ap-1",
			nil,
			&domainPrivate,
			nil,
			false,
		),
	}, nil)
	if rec.Code != http.StatusCreated {
		t.Fatalf("private write expected 201, got %d: %s", rec.Code, rec.Body.String())
	}

	// write workspace
	rec = doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "accessplanmultiread shared keyword",
		AccessPlan: accessPlan(
			"tenant-ap-1",
			"inst-ap-1",
			nil,
			&domainWorkspace,
			nil,
			false,
		),
	}, nil)
	if rec.Code != http.StatusCreated {
		t.Fatalf("workspace write expected 201, got %d: %s", rec.Code, rec.Body.String())
	}

	// query with private-first read domains
	rec = doJSONRequest(t, server, "POST", "/memory/query", pkg.QueryRequest{
		Query: "accessplanmultiread",
		Limit: 10,
		AccessPlan: accessPlan(
			"tenant-ap-1",
			"inst-ap-1",
			[]pkg.MemoryDomainRef{domainPrivate, domainWorkspace},
			nil,
			nil,
			false,
		),
	}, nil)
	if rec.Code != http.StatusOK {
		t.Fatalf("query expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp pkg.QueryResult
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if resp.Total < 2 {
		t.Fatalf("expected at least 2 results, got %d", resp.Total)
	}
	if resp.Results[0].DomainID != "d-private" {
		t.Fatalf("expected private domain first, got %s", resp.Results[0].DomainID)
	}
	if resp.EnforcementTrace == nil || len(resp.EnforcementTrace.ActualEnforcedDomains) < 2 {
		t.Fatalf("expected enforcement trace for both domains")
	}
}

func TestAccessPlanTenantIsolationForWorkspaceShared(t *testing.T) {
	server := newAccessPlanTestServer(t)
	domainWorkspaceA := pkg.MemoryDomainRef{
		DomainID:  "d-ws-a",
		TenantID:  "tenant-a",
		ScopeType: pkg.DomainWorkspaceShared,
		ScopeKey:  "same-workspace-key",
	}
	_ = doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "tenant-a-only-workspace-memory",
		AccessPlan: accessPlan(
			"tenant-a",
			"inst-a",
			nil,
			&domainWorkspaceA,
			nil,
			false,
		),
	}, nil)

	domainWorkspaceB := pkg.MemoryDomainRef{
		DomainID:  "d-ws-b",
		TenantID:  "tenant-b",
		ScopeType: pkg.DomainWorkspaceShared,
		ScopeKey:  "same-workspace-key",
	}
	rec := doJSONRequest(t, server, "POST", "/memory/query", pkg.QueryRequest{
		Query: "tenant-a-only-workspace-memory",
		Limit: 10,
		AccessPlan: accessPlan(
			"tenant-b",
			"inst-b",
			[]pkg.MemoryDomainRef{domainWorkspaceB},
			nil,
			nil,
			false,
		),
	}, nil)
	if rec.Code != http.StatusOK {
		t.Fatalf("query expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp pkg.QueryResult
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if resp.Total != 0 {
		t.Fatalf("tenant isolation violated, expected 0 results, got %d", resp.Total)
	}
}

func TestAccessPlanSecondaryWriteRejectedWithoutAuthorization(t *testing.T) {
	server := newAccessPlanTestServer(t)
	domainPrivate := pkg.MemoryDomainRef{
		DomainID:  "d-priv-noauth",
		TenantID:  "tenant-noauth",
		ScopeType: pkg.DomainInstancePrivate,
	}
	domainWorkspace := pkg.MemoryDomainRef{
		DomainID:  "d-ws-noauth",
		TenantID:  "tenant-noauth",
		ScopeType: pkg.DomainWorkspaceShared,
		ScopeKey:  "ws-noauth",
	}

	rec := doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "secondary write should be rejected without authorization",
		AccessPlan: accessPlan(
			"tenant-noauth",
			"inst-noauth",
			nil,
			&domainPrivate,
			[]pkg.MemoryDomainRef{domainWorkspace},
			false,
		),
	}, nil)
	if rec.Code != http.StatusCreated {
		t.Fatalf("write expected 201, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp pkg.WriteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if resp.EnforcementTrace == nil {
		t.Fatalf("expected enforcement_trace")
	}
	privateApplied := false
	workspaceRejected := false
	for _, d := range resp.EnforcementTrace.ActualEnforcedDomains {
		if d.DomainID == "d-priv-noauth" && d.Decision == "applied" && d.MemoryID != "" {
			privateApplied = true
		}
		if d.DomainID == "d-ws-noauth" && d.Decision == "rejected" && d.Reason == "secondary_write_not_authorized" {
			workspaceRejected = true
		}
	}
	if !privateApplied || !workspaceRejected {
		t.Fatalf("expected private applied and workspace rejected, private=%v workspace=%v", privateApplied, workspaceRejected)
	}
}

func TestAccessPlanPrimaryAndSecondaryWriteAndDedupBoundary(t *testing.T) {
	server := newAccessPlanTestServer(t)
	domainPrivate := pkg.MemoryDomainRef{
		DomainID:  "d-priv-write",
		TenantID:  "tenant-dedup",
		ScopeType: pkg.DomainInstancePrivate,
	}
	domainWorkspace := pkg.MemoryDomainRef{
		DomainID:  "d-ws-write",
		TenantID:  "tenant-dedup",
		ScopeType: pkg.DomainWorkspaceShared,
		ScopeKey:  "ws-dedup",
	}
	rec := doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "same-content-cross-domain-dedup-boundary",
		AccessPlan: accessPlan(
			"tenant-dedup",
			"inst-dedup",
			nil,
			&domainPrivate,
			[]pkg.MemoryDomainRef{domainWorkspace},
			true,
		),
	}, nil)
	if rec.Code != http.StatusCreated {
		t.Fatalf("write expected 201, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp pkg.WriteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if resp.EnforcementTrace == nil || len(resp.EnforcementTrace.ActualEnforcedDomains) < 2 {
		t.Fatalf("expected primary + secondary trace")
	}
	primaryID := ""
	secondaryID := ""
	for _, d := range resp.EnforcementTrace.ActualEnforcedDomains {
		if d.DomainID == "d-priv-write" {
			primaryID = d.MemoryID
		}
		if d.DomainID == "d-ws-write" {
			secondaryID = d.MemoryID
		}
	}
	if primaryID == "" || secondaryID == "" {
		t.Fatalf("expected memory IDs for both domains, got primary=%q secondary=%q", primaryID, secondaryID)
	}
	if primaryID == secondaryID {
		t.Fatalf("dedup boundary violated: private/shared should not collapse into one memory_id")
	}
}

func TestAccessPlanSecondaryReadOnlyRejectedEvenWhenAuthorized(t *testing.T) {
	server := newAccessPlanTestServer(t)
	domainPrivate := pkg.MemoryDomainRef{
		DomainID:  "d-priv-ro-secondary",
		TenantID:  "tenant-ro-secondary",
		ScopeType: pkg.DomainInstancePrivate,
	}
	readOnlySecondary := pkg.MemoryDomainRef{
		DomainID:  "d-ro-secondary",
		TenantID:  "tenant-ro-secondary",
		ScopeType: pkg.DomainSharedReadOnly,
		ScopeKey:  "ws-ro-secondary",
	}

	rec := doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "secondary read-only must be rejected",
		AccessPlan: accessPlan(
			"tenant-ro-secondary",
			"inst-ro-secondary",
			nil,
			&domainPrivate,
			[]pkg.MemoryDomainRef{readOnlySecondary},
			true,
		),
	}, nil)
	if rec.Code != http.StatusCreated {
		t.Fatalf("write expected 201, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp pkg.WriteResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if resp.EnforcementTrace == nil {
		t.Fatalf("expected enforcement_trace")
	}
	privateApplied := false
	readOnlyRejected := false
	for _, d := range resp.EnforcementTrace.ActualEnforcedDomains {
		if d.DomainID == "d-priv-ro-secondary" && d.Decision == "applied" && d.MemoryID != "" {
			privateApplied = true
		}
		if d.DomainID == "d-ro-secondary" && d.Decision == "rejected" {
			readOnlyRejected = true
		}
	}
	if !privateApplied || !readOnlyRejected {
		t.Fatalf("expected private applied and read_only secondary rejected, private=%v readOnly=%v", privateApplied, readOnlyRejected)
	}
}

func TestAccessPlanWriteRejectsReadOnlyAndCustomShared(t *testing.T) {
	server := newAccessPlanTestServer(t)

	readOnly := pkg.MemoryDomainRef{
		DomainID:  "d-ro",
		TenantID:  "tenant-ro",
		ScopeType: pkg.DomainSharedReadOnly,
		ScopeKey:  "ws-ro",
	}
	rec := doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "should be rejected read-only",
		AccessPlan: accessPlan(
			"tenant-ro",
			"inst-ro",
			nil,
			&readOnly,
			nil,
			false,
		),
	}, nil)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("read_only write expected 400, got %d: %s", rec.Code, rec.Body.String())
	}

	custom := pkg.MemoryDomainRef{
		DomainID:  "d-custom",
		TenantID:  "tenant-custom",
		ScopeType: pkg.DomainCustomShared,
		ScopeKey:  "custom-scope",
	}
	rec = doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "should be rejected custom-shared",
		AccessPlan: accessPlan(
			"tenant-custom",
			"inst-custom",
			nil,
			&custom,
			nil,
			false,
		),
	}, nil)
	if rec.Code != http.StatusNotImplemented {
		t.Fatalf("custom_shared write expected 501, got %d: %s", rec.Code, rec.Body.String())
	}
}

func TestAccessPlanSearchKeepsDomainProvenance(t *testing.T) {
	server := newAccessPlanTestServer(t)
	domainPrivate := pkg.MemoryDomainRef{
		DomainID:  "d-search-private",
		TenantID:  "tenant-search",
		ScopeType: pkg.DomainInstancePrivate,
	}
	domainWorkspace := pkg.MemoryDomainRef{
		DomainID:  "d-search-workspace",
		TenantID:  "tenant-search",
		ScopeType: pkg.DomainWorkspaceShared,
		ScopeKey:  "ws-search",
	}

	_ = doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "ap-search-provenance keyword",
		AccessPlan: accessPlan(
			"tenant-search",
			"inst-search",
			nil,
			&domainPrivate,
			nil,
			false,
		),
	}, nil)
	_ = doJSONRequest(t, server, "POST", "/memory/write", pkg.WriteRequest{
		Content: "ap-search-provenance keyword",
		AccessPlan: accessPlan(
			"tenant-search",
			"inst-search",
			nil,
			&domainWorkspace,
			nil,
			false,
		),
	}, nil)

	rec := doJSONRequest(t, server, "POST", "/memory/search", pkg.SearchRequest{
		Keyword: "ap-search-provenance",
		Limit:   10,
		AccessPlan: accessPlan(
			"tenant-search",
			"inst-search",
			[]pkg.MemoryDomainRef{domainPrivate, domainWorkspace},
			nil,
			nil,
			false,
		),
	}, nil)
	if rec.Code != http.StatusOK {
		t.Fatalf("search expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var resp pkg.SearchResponse
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if resp.Total < 2 {
		t.Fatalf("expected at least 2 search results, got %d", resp.Total)
	}
	foundPrivate := false
	foundWorkspace := false
	for _, item := range resp.Results {
		if item.DomainID == "d-search-private" {
			foundPrivate = true
		}
		if item.DomainID == "d-search-workspace" {
			foundWorkspace = true
		}
	}
	if !foundPrivate || !foundWorkspace {
		t.Fatalf("domain provenance missing, private=%v workspace=%v", foundPrivate, foundWorkspace)
	}
}
