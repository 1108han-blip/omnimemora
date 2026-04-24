# CSP-001 Compile Strategy Policy — Policy Bundle Promotion Path

**Date:** 2026-04-24
**Batch:** Policy Bundle Promotion Path (Phase 6 / CSP-001)
**Result:** PASS — bundle promoted, evidence verified

---

## Batch Goal

Wire the compile strategy policy bundle into the promotion workflow so that:

1. `promotion.sh` copies `config/compile_strategy_policies/` (manifest.json + active policy file) alongside the runtime binary to `~/.omnimemora/service/current/tools/config/compile_strategy_policies/`
2. `NewManager` discovers the bundle at runtime via `os.Executable()` + sibling layout
3. Promotion fails explicitly if the bundle source is missing (no silent `builtin` fallback in production)
4. Running evidence shows `policy_version=local-default-v1`, `policy_source=bundled`

---

## Changes Delivered

### `4_core/local-runtime/policy/manager.go`

- `NewManager("")` now calls `resolvePolicyDir("")` to auto-discover the policy directory
- `resolvePolicyDir("")` resolution order:
  1. **Binary-bundle layout**: `os.Dir(os.Executable())/config/compile_strategy_policies/` — used by promoted service binary
  2. **CWD layout**: `config/compile_strategy_policies/` relative to working directory — used in repo/dev
  3. **Not found**: returns empty string, triggering built-in fallback silently (never an error)
- `NewManager(explicitPath)` still works for tests and custom deployments

### `tools/promotion/promotion.sh`

- Step `[2b/5]`: copies `manifest.json` and `local-default-v1.json` from `$runtime_src/config/compile_strategy_policies/` to `$CURRENT_SERVICE_DIR/tools/config/compile_strategy_policies/`
- Step `[2c/5]`: verifies `manifest.json` exists in destination; fails promotion explicitly if source dir or manifest is missing
- Promotion log fields added:
  - `runtime_compile_strategy_policy_bundle`: `present` | `missing`
  - `runtime_compile_strategy_policy_active_version`: version string
  - `runtime_compile_strategy_policy_bundle_path`: absolute path to destination

### `4_core/local-runtime/policy/manager_test.go`

- `TestLoadActive_BundleLayout`: loads policy from explicit bundle-style path; verifies `local-default-v1` + `bundled` in resolved defaults
- `TestLoadActive_MissingBundlePath_FallsBack`: verifies `NewManager("")` with no valid path falls back to `builtin` without error
- `TestResolveAuto_BundlePolicy`: verifies question/long-query/short auto-resolution rules work from bundle-loaded policy

---

## Test Results

```
cd 4_core/local-runtime && go test ./policy/... -v
...
--- PASS: TestLoadActive_BundleLayout
--- PASS: TestLoadActive_MissingBundlePath_FallsBack
--- PASS: TestResolveAuto_BundlePolicy
--- PASS: TestInvalidateCache_DoesNotLoseBuiltinBaseline
...
PASS
18/18 tests pass
```

---

## Promotion Execution

```
TARGET=runtime+adapter ./tools/promotion/promotion.sh runtime+adapter
```

**Result:** `final_status: running_reality_promoted`

---

## Running Evidence (SQLite — non-Codex metering record)

```sql
SELECT compile_strategy_policy_version,
       compile_strategy_policy_source,
       context_strategy_requested,
       context_strategy_resolved,
       context_mode_resolved
FROM   metering_events
WHERE  id = (SELECT MAX(id) FROM metering_events);
```

| Field | Value | Status |
|---|---|---|
| `compile_strategy_policy_version` | `local-default-v1` | ✅ |
| `compile_strategy_policy_policy_source` | `bundled` | ✅ |
| `context_strategy_requested` | `auto` | ✅ |
| `context_strategy_resolved` | `recency_boost_select` | ✅ |
| `context_mode_resolved` | `balanced` | ✅ |

All five evidence fields confirm the runtime is serving the promoted bundle policy, not the built-in fallback.

---

## Commit

```
e92805f runtime: promote compile strategy policy bundle
```

Worktree clean after commit.

---

## Gate Status

| Gate | Status |
|------|--------|
| Repo contract protected (tests pass) | ✅ 18/18 |
| No silent fallback in promotion (fails explicitly) | ✅ |
| Bundle discovered via `os.Executable()` | ✅ |
| Promotion log fields emitted | ✅ |
| Running evidence: `policy_version=local-default-v1` | ✅ |
| Running evidence: `policy_source=bundled` | ✅ |
| Worktree clean | ✅ |
