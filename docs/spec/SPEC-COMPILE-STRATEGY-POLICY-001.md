# Compile Strategy Policy — Implementation Scope (First Batch)

**Decision:** D-2026-04-24-CSP-001
**Batch:** First Implementation Batch

---

## Goal

Deliver a working local-only compile strategy policy layer that is
functionally identical to the current hardcoded defaults, with full
metering evidence and a clean structure for future cloud candidate
integration.

---

## Scope

### Out of scope for this batch

- Cloud candidate pack download path (fetch/verify/store).
- Recommendation policy (`recommendation_policy` family).
- Any UI changes.
- Codex validation or thick memory expansion.
- New API routes (no new endpoints).

---

## Deliverables

| # | Deliverable | File(s) | Description |
|---|-------------|---------|-------------|
| 1 | Design record | `docs/adr/DECISION-CSP-001.md` | Accepted design rationale |
| 2 | Policy files | `config/compile_strategy_policies/manifest.json`<br>`config/compile_strategy_policies/local-default-v1.json` | Initial bundled policy |
| 3 | Policy types | `policy/types.go` | `CompileStrategyPolicy`, `Manifest`, `PolicyVersion` types |
| 4 | Policy manager | `policy/manager.go` | Load active, load candidate, promote, resolve auto, built-in fallback |
| 5 | Policy test | `policy/manager_test.go` | All seven acceptance tests from the design |
| 6 | Wiring | `app/service.go` updated<br>`app/context/strategy.go` updated | Service consults policy manager at startup; strategy resolution uses policy; hardcoded defaults remain fallback |
| 7 | Metering extension | `metering/event.go` updated<br>`metering/collector.go` updated<br>`store/sqlite_store.go` updated | New evidence fields persisted |

---

## Acceptance Tests (First Batch)

1. Local default policy loads and matches current behaviour.
2. Missing/invalid policy falls back to built-in runtime defaults.
3. Candidate policy does not affect active execution before promotion.
4. Manual promotion switches active policy version.
5. `auto` resolves according to active policy rules.
6. Metering records actual policy version and resolved strategy.
7. Cloud disabled/unreachable does not affect compile.

---

## Key Boundaries

- **No cloud compile.** Compile decisions are local-only.
- **No per-request remote strategy decision.**
- **No automatic promotion.** Manual CLI/API step required.
- **No thick memory product expansion.**
- **No Codex validation.**
- **No UI changes.**

---

## File Map

```
local-runtime/
├── config/
│   └── compile_strategy_policies/
│       ├── manifest.json              ← new (bundled, ship with binary)
│       └── local-default-v1.json     ← new (bundled, ship with binary)
├── policy/
│   ├── types.go                      ← new
│   ├── manager.go                    ← new
│   └── manager_test.go               ← new
├── app/
│   ├── service.go                    ← modified (wire policy manager)
│   └── context/
│       └── strategy.go              ← modified (export ResolveMode, GetDefaults for policy fallback use)
├── metering/
│   ├── event.go                      ← modified (new fields)
│   └── collector.go                 ← modified (persist new fields)
├── store/
│   └── sqlite_store.go               ← modified (ALTER TABLE metering_events)
└── main.go                           ← modified (initialize policy manager)
```

---

## References

- Design record: `docs/adr/DECISION-CSP-001.md`
- Existing strategy defaults: `app/context/strategy.go`, `app/context/strategy_auto.go`
- Metering schema: `metering/event.go`, `metering/collector.go`
