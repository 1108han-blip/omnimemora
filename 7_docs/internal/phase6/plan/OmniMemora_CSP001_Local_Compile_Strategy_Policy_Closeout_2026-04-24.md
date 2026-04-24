# CSP-001 First Implementation Batch — Closeout Record

**Decision:** D-2026-04-24-CSP-001
**Batch:** First Implementation Batch
**Date:** 2026-04-24
**Status:** ✅ Complete

---

## Scope Coverage

All three layers — policy, service, metering — were implemented.

| Layer | Deliverables | Status |
|---|---|---|
| Policy | `types.go`, `manager.go`, `manager_test.go`, bundled policy files | ✅ |
| Service wiring | `app/service.go` updated | ✅ |
| Metering | `metering/event.go`, `metering/collector.go`, `store/sqlite_store.go` | ✅ |

---

## Changes

### New files
- `config/compile_strategy_policies/manifest.json` — tracks active/candidate versions
- `config/compile_strategy_policies/local-default-v1.json` — mirrors current hardcoded defaults
- `policy/types.go` — `CompileStrategyPolicy`, `Manifest`, `ResolvedDefaults`, `PolicySource` types
- `policy/manager.go` — `LoadActive`, `LoadCandidate`, `PromoteCandidate`, `ResolveAuto`, `GetModeDefaults`, `GetResolved`
- `policy/manager_test.go` — 15 tests covering all 7 acceptance criteria

### Modified files
- `app/service.go` — `Service` owns `*policy.Manager`; strategy resolution delegates to manager; `recordSearchMetering` signature extended with policy evidence fields
- `metering/event.go` — added `CompileStrategyPolicyVersion`, `CompileStrategyPolicySource`, `ContextStrategyRequested`, `ContextStrategyResolved`, `ContextModeResolved`
- `metering/collector.go` — `INSERT` extended with 5 new columns
- `store/sqlite_store.go` — idempotent `ALTER TABLE` migrations for 5 new metering columns

---

## Evidence

- `go test ./policy -v` → **15/15 PASS** (0.451s)
- `go test ./tests -run 'Search|Meter|Context|Policy|AccessPlan' -timeout 60s` → **ok** (0.303s)
- `go test ./... -timeout 120s` → all packages **ok**
- `go build ./...` → **no errors**
- `git diff --check` → **no whitespace errors**

---

## Boundaries Honored

| Boundary | Verified |
|---|---|
| No cloud compile | ✅ Manager has no network calls |
| No per-request remote strategy decision | ✅ Policy loaded once at startup |
| No automatic promotion | ✅ `PromoteCandidate` requires explicit call |
| No thick memory product expansion | ✅ Only strategy/mode defaults |
| No Codex validation | ✅ No Codex references added |
| No UI changes | ✅ No UI touched |

---

## Next Batch

Next batch: docs sync + repo-only evidence contract hardening; no promotion/live until local repo tests are clean enough to define the running target.
