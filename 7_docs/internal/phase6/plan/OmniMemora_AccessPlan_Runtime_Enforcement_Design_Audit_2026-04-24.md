# OmniMemora AccessPlan Runtime Enforcement Design Audit (2026-04-24)

## Audit Scope

- Batch type: docs-only design audit
- Validation target: repository source inspection only
- Runtime target: `4_core/local-runtime`
- Projection source: `5_connectors/adapter/application/access_plan.py` and `request_evidence`
- Excluded: runtime multi-domain implementation, promotion, live request validation, Codex install/run/live gate

## Reality Separation

- Repository reality: inspected source supports single-`ScopeRef` runtime execution and adapter-side AccessPlan projection, but not request-level AccessPlan enforcement in runtime read/write paths.
- Candidate reality: this batch adds only this audit record.
- Running reality: not evaluated in this batch. No promotion was run, and no live `5173 / 18011 / 8765` behavior is claimed.

## Current Runtime Capability Map

### Runtime Entrypoints

- `/memory/write`, `/memory/query`, and `/memory/search` each resolve exactly one `ScopeRef` from request context, reject `custom` with `501 NOT_IMPLEMENTED`, then call one service method with that single scope.
  - Evidence: `4_core/local-runtime/api/routes.go:43-144`
- `scopeMiddleware` parses one scope from headers/body/config and stores a single `scope_ref` in request context.
  - Evidence: `4_core/local-runtime/api/middleware.go:176-203`
- Body parsing accepts scalar `scope`, `sharing_mode`, `agent_id`, `workspace_id`, `user_id`, and `tenant_id`; it does not parse `access_plan`, `read_domains`, or write-domain arrays.
  - Evidence: `4_core/local-runtime/api/middleware.go:211-250`

### Scope Model and Tenant Isolation

- `ScopeRef` is the runtime governance primitive. It contains one `tenant_id`, one user/workspace/agent identity tuple, one `scope`, one `sharing_mode`, and optional `custom_scope_id`.
  - Evidence: `4_core/local-runtime/pkg/types.go:27-37`
- Supported scope enums are `agent`, `workspace`, `user`, and `custom`; supported sharing modes are `isolated`, `shared`, `shared_read_only`, and `custom`.
  - Evidence: `4_core/local-runtime/pkg/types.go:7-24`
- `EnforceWrite` and `EnforceRead` validate the selected single scope. Custom scope policy has partial registry semantics in the model, but current HTTP runtime entrypoints still reject `custom` before service execution.
  - Evidence: `4_core/local-runtime/scope/model.go:77-170`
- SQLite filtering always applies tenant filtering before scope-specific filtering. This preserves tenant isolation in the current single-scope model.
  - Evidence: `4_core/local-runtime/store/sqlite_store.go:480-529`

### Write Path

- `Service.WriteMemory` applies default sharing mode for agent/workspace, rejects custom scope, enforces one scope, computes one content hash, checks dedup within that one scope, writes one `MemoryRecord`, and records one metering event.
  - Evidence: `4_core/local-runtime/app/service.go:43-112`
- Dedup is scoped by content hash plus `scope`, `agent_id`, `workspace_id`, and `tenant_id`; it is not AccessPlan-aware and does not dedup across planned secondary domains.
  - Evidence: `4_core/local-runtime/store/sqlite_store.go:321-341`

### Query and Search Path

- `Service.QueryMemory` enforces one read scope, calls store `Query` once, returns `scope_applied` as one scope, and records one query metering event.
  - Evidence: `4_core/local-runtime/app/service.go:114-165`
- `Service.SearchMemory` enforces one read scope, calls store `Search` once, ranks the single-scope result set, optionally assembles context from that result set, returns `scope_applied` as one scope, and records one search metering event.
  - Evidence: `4_core/local-runtime/app/service.go:168-335`
- SQLite `Query` and `Search` each call `buildScopeFilter` once. The filter can express tenant + one scope boundary, not a prioritized multi-domain read plan.
  - Evidence: `4_core/local-runtime/store/sqlite_store.go:201-318`

### Metering

- Runtime metering records event type, request id, tenant/user/workspace/agent, one scope, and one sharing mode.
  - Evidence: `4_core/local-runtime/app/service.go:454-513`, `4_core/local-runtime/app/service.go:692-733`
- Current metering can prove that a single `ScopeRef` path executed. It cannot prove which AccessPlan read domains were attempted, skipped, merged, or selected, nor which secondary write domains were actually written.

## AccessPlan Enforcement Gaps

1. Request-level `AccessPlan` is not part of runtime request types, middleware context, service signatures, store requests, or metering events.
2. Adapter projection builds `read_domains[]`, `primary_write_domain`, and `secondary_write_domains[]`, but the module explicitly does not perform memory operations.
   - Evidence: `5_connectors/adapter/application/access_plan.py:1-8`, `5_connectors/adapter/application/access_plan.py:169-279`
3. `request_evidence` projects `identity` and `access_plan` from meter/read-model data, but this proves projection visibility, not runtime enforcement.
   - Evidence: `5_connectors/adapter/application/status_read_model.py:1176-1247`
4. Runtime query/search can only execute one scope filter per request. It has no orchestration for private-first reads, shared supplemental reads, merge ordering, de-duplication across domains, or domain provenance.
5. Runtime write can only persist one `MemoryRecord` under one `ScopeRef`. It has no policy gate for secondary shared writes and no record of attempted/allowed/rejected secondary writes.
6. `custom` currently remains unusable through HTTP `/memory/*` entrypoints because the routes return `501 NOT_IMPLEMENTED` before service execution.
7. `QueryByHash` is single-scope and not domain-role-aware. Reusing it for secondary write domains without orchestration would either miss cross-domain intent or incorrectly collapse private/shared writes.
8. Existing metering and response contracts expose `scope_applied`, not `actual_enforced_domains`. Evidence can show a planned AccessPlan and a single executed scope, but not that the plan was enforced.

## Implementation Recommendation

The next implementation batch should use the runtime service layer as the main breakpoint.

Recommended direction:

1. Add an `AccessPlan` runtime contract that can be accepted from the product ingress path, while preserving `ScopeRef` as the bottom-level single-domain execution primitive.
2. Add service-layer orchestration methods that convert one request-level AccessPlan into multiple existing single-`ScopeRef` operations.
3. Keep SQLite `buildScopeFilter` single-domain. Do not encode multi-domain policy, ordering, or provenance inside SQL filter construction.
4. Read path:
   - execute private domain first
   - execute allowed shared/read-only domains as supplemental reads
   - merge and rank results at the service layer
   - retain per-result domain provenance and the read order/decision trace
5. Write path:
   - default writes to `primary_write_domain` mapped to private scope
   - write to `secondary_write_domains[]` only after explicit policy checks
   - keep shared-read-only domains read-only
   - record every attempted, allowed, rejected, and written domain
6. Request evidence must distinguish planned domains from actual enforced domains. The acceptance surface should include at least:
   - `planned_read_domains`
   - `actual_read_domains`
   - `primary_write_domain`
   - `actual_write_domains`
   - per-domain `scope_ref`, `operation`, `decision`, and `reason`
   - per-result domain provenance for read/search results that reach context assembly

## Files to Touch

Expected implementation batch files:

- `4_core/local-runtime/pkg/types.go`
  - Add runtime `AccessPlan`, domain reference, enforced-domain evidence, and response provenance types.
- `4_core/local-runtime/api/middleware.go`
  - Parse AccessPlan without replacing the existing single `ScopeRef` compatibility path.
- `4_core/local-runtime/api/routes.go`
  - Route requests with AccessPlan into service orchestration while preserving legacy single-scope behavior.
- `4_core/local-runtime/app/service.go`
  - Add the orchestration breakpoint. Keep existing `WriteMemory`, `QueryMemory`, and `SearchMemory` as single-domain primitives or thin wrappers.
- `4_core/local-runtime/store/store.go`
  - Add only minimal provenance/result fields if needed by service orchestration; avoid store-level policy decisions.
- `4_core/local-runtime/store/sqlite_store.go`
  - Keep `buildScopeFilter` single-domain; adjust result metadata only if service needs stable domain provenance from records.
- `4_core/local-runtime/metering/event.go`
  - Add actual enforced-domain evidence fields or a linked enforcement event type.
- `5_connectors/adapter/application/access_plan.py`
  - Add/confirm a deterministic adapter-to-runtime mapping from projected domain refs to runtime scope refs.
- `5_connectors/adapter/ingress/llm_proxy.py`
  - Pass AccessPlan into runtime memory calls once runtime contract exists.
- `5_connectors/adapter/application/status_read_model.py`
  - Project actual enforcement evidence separately from planned AccessPlan.
- Tests under `4_core/local-runtime/tests/` and adapter evidence tests that cover runtime enforcement and read-model projection together.

## Do Not Touch

- Do not implement multi-domain policy inside SQLite `buildScopeFilter`.
- Do not replace `ScopeRef`; keep it as the single-domain execution primitive.
- Do not treat `request_evidence.access_plan` as proof of enforcement until actual runtime enforcement fields exist.
- Do not run promotion in the implementation design batch until repo tests define the target behavior.
- Do not include Codex in install/run/live validation gates.
- Do not write raw meter files manually.
- Do not use legacy `:8000` or runtime-direct behavior as product truth. Product ingress remains `http://127.0.0.1:18011` after opt-in.

## Acceptance Tests for Implementation Batch

Minimum repo tests:

1. Legacy single-scope compatibility:
   - existing `/memory/write`, `/memory/query`, and `/memory/search` requests without AccessPlan keep current behavior.
2. Private-first read:
   - AccessPlan with private + workspace shared read domains executes private first, then workspace shared, and records actual read order.
3. Tenant isolation:
   - a multi-domain AccessPlan never returns records from another tenant, even when workspace/user keys collide.
4. Search merge and provenance:
   - search results include domain provenance and do not lose deterministic ranking when private and shared results are merged.
5. Primary write only by default:
   - AccessPlan writes to private primary domain when no shared-write policy is enabled.
6. Secondary shared write policy:
   - allowed secondary shared domains receive writes only when policy permits; rejected domains appear in actual enforcement evidence with a reason.
7. Shared-read-only protection:
   - read-only domains are searchable but never written.
8. Custom scope boundary:
   - either remains explicit `not implemented` at the AccessPlan mapping layer, or has a complete policy implementation before being enabled.
9. Dedup boundary:
   - dedup stays scoped per actual write domain and does not collapse private and shared domain records incorrectly.
10. Metering/evidence:
   - runtime metering or linked enforcement records expose actual read/write domains, and `request_evidence` displays actual enforced domains separately from planned domains.

Minimum product-path validation after repo tests pass:

1. Promote the required target only when implementation is ready for running reality.
2. Send a real request through `http://127.0.0.1:18011`.
3. Confirm `request_id -> request_evidence -> 5173` shows planned AccessPlan and actual enforced domains as separate facts.
4. Keep Codex excluded from this validation gate unless the protected/deferred boundary is explicitly reopened.

## Codex Protection Boundary

- Codex remains protected/deferred and excluded from install/run/live validation gates.
- This audit does not use Codex live traffic as enforcement evidence.
- Future implementation may use Codex for repository edits and tests, but not as a product validation client unless the operator explicitly reopens that boundary.

## Main Breakpoint

The unique main breakpoint for the next implementation batch is:

`4_core/local-runtime/app/service.go`: add AccessPlan execution orchestration above the existing single-domain `ScopeRef` primitives.

Reason:

- It is high enough to express domain ordering, write policy, merge behavior, provenance, and enforcement evidence.
- It preserves SQLite/store code as a simple single-domain executor.
- It avoids smuggling product policy into low-level SQL filters.
- It creates the right point to emit actual enforced-domain evidence for meter/read-model/request-evidence surfaces.

## Audit Validation

- `git status --short`: clean before document creation.
- Source inspection: targeted `rg`, `sed`, and `nl` over runtime routes, middleware, service, store, scope model, metering, adapter AccessPlan projection, and request evidence projection.
- Promotion: not run.
- Code changes: none.
