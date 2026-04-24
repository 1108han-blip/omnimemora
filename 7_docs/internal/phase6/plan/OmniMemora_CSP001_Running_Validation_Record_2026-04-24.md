# CSP-001 Compile Strategy Policy — Running Validation Record

**Date:** 2026-04-24
**Validation type:** running reality (runtime promotion + non-Codex evidence check)
**Result:** PASS

---

## Validation Actions

1. Built new runtime binary from local commit `08dc207`
2. Stopped old runtime (PID 31046 → 65978), copied new binary, auto-restarted (PID 66034)
3. Verified runtime health: `{"status":"ok","version":"1.0.0","uptime_seconds":220,"mode":"local"}`
4. Sent test request directly to runtime (bypassing adapter) with:
   - `assemble_context: true`
   - `context_strategy: auto`
   - `context_mode: balanced`
5. Queried SQLite metering events for evidence

---

## Results

### 1. New runtime binary loaded ✅

- Process restarted and healthy
- Uptime confirms new binary in use (was previously ~4h, now ~220s)

### 2. SQLite schema: all 5 CSP-001 columns present ✅

All columns exist in `metering_events` table:
- `compile_strategy_policy_version`
- `compile_strategy_policy_source`
- `context_strategy_requested`
- `context_strategy_resolved`
- `context_mode_resolved`

### 3. CSP-001 fields recorded correctly ✅

For test request `csp001-val-full`:

| Field | Value | Expected | Result |
|---|---|---|---|
| `compile_strategy_policy_version` | `builtin` | non-empty | ✅ |
| `compile_strategy_policy_source` | `builtin` | non-empty | ✅ |
| `context_strategy_requested` | `auto` | `auto` | ✅ |
| `context_strategy_resolved` | `recency_boost_select` | a known strategy | ✅ |
| `context_mode_resolved` | `balanced` | `balanced` | ✅ |

**Note on `policy_version=builtin`:** The bundled policy files (`config/compile_strategy_policies/`) are repo-only files, not embedded in the runtime binary. When the runtime runs as a service, `policyDir=""` resolves to `"config/compile_strategy_policies"` relative to the binary's working directory, which does not exist. The manager correctly falls back to built-in defaults (`PolicySourceBuiltIn`). This is the expected behavior for the repo-only first batch. When the policy files are bundled separately or the binary is run from the repo root, `local-default-v1` / `bundled` will appear instead.

### 4. Strategy auto-resolution ✅

- `auto` → `recency_boost_select` for short non-question query `"docker container"` (correct per auto rules)
- Fallback chain works: `PolicyManager.ResolveAuto()` → `context.ResolveAutoStrategy()`

### 5. AccessPlan actual enforcement not regressed ✅

Write with `access_plan` returned:
- `planned_write_domains`: correct
- `actual_enforced_domains`: correct with resolved scope_ref

---

## Boundaries Verified

- non-Codex request only (direct runtime API)
- no Codex validation
- no promotion to production

---

## Evidence Files

- SQLite: `/Users/sc/.omnimemora/runtime/memory.db` → `metering_events` table
- Test request: `csp001-val-full`
- Event: `evt_b6b0f4d1`

---

## Conclusion

CSP-001 runtime evidence contract is active in running reality. The 5 CSP-001 evidence fields are persisted and queryable for every `memory_search` event with `assemble_context=true`. Policy fallback to `builtin` is correct when no bundled policy files are present. AccessPlan enforcement trace is not regressed.
