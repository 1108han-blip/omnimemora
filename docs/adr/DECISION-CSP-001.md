# Compile Strategy Policy — Design Record

**Decision ID:** D-2026-04-24-CSP-001
**Date:** 2026-04-24
**Status:** Accepted — Local Import Implemented (Batch 1/3)

---

## Context

The OmniMemora local runtime assembles context for LLM prompts by applying a
context strategy (e.g. `topk_excerpt`, `diversity_select`) against ranked
search results.  The strategy name, mode (precise/balanced/aggressive), and
token budget have so far been either hardcoded defaults or passed through
the request-level `context_strategy` / `context_mode` fields.

The design requirement is to formalise a **local-first policy layer** that:

- Is **authoritative** over the active compile strategy at runtime.
- Permits **cloud-hosted candidate packs** to be downloaded and evaluated
  offline, but **never automatically promoted**.
- Clearly separates the compile-strategy policy family from the existing
  `recommendation_policy` (skill suggestions) family.
- Records runtime evidence of the active policy version and resolved
  strategy in every metering event.

---

## Decision

### 1 — Two distinct policy families

| Family | Purpose | Delivery | Activation |
|--------|---------|----------|------------|
| `recommendation_policy` | Advisory skill suggestions, sidecar only | cloud / local | Never active; advisory only |
| `compile_strategy_policy` | Context assembly, token budget, allowed strategies | local files + future cloud candidate packs | Manual promotion; local active always authoritative |

These families MUST NOT share storage, schema, or loading paths.

### 2 — Compile strategy policy document schema

Each policy version is a JSON file in `config/compile_strategy_policies/`.
The schema covers only lightweight local settings:

```jsonc
{
  "version": "local-default-v1",
  "description": "Initial production-ready default",
  "default_context_strategy": "topk_excerpt",
  "allowed_strategies": [
    "topk_excerpt",
    "recency_boost_select",
    "diversity_select"
  ],
  "auto_resolution": {
    "enabled": true,
    "rules": {
      "question_patterns": "topk_excerpt",
      "long_query_threshold_chars": 50,
      "long_query_strategy": "diversity_select",
      "default_strategy": "recency_boost_select"
    }
  },
  "mode_defaults": {
    "precise":   { "token_budget": 300,  "max_items": 3  },
    "balanced":  { "token_budget": 800,  "max_items": 6  },
    "aggressive": { "token_budget": 1500, "max_items": 10 }
  }
}
```

### 3 — Manifest

`config/compile_strategy_policies/manifest.json` tracks all known versions:

```jsonc
{
  "active_version": "local-default-v1",
  "candidate_version": null,
  "versions": [
    {
      "version": "local-default-v1",
      "status": "active",
      "policy_file": "local-default-v1.json",
      "source": "bundled",
      "verified_at": "2026-04-24T00:00:00Z"
    }
  ]
}
```

### 4 — Policy Manager responsibilities

The `policy` package provides a `Manager` that:

1. **LoadActive()** — reads the manifest, finds the `active_version`, loads
   the corresponding policy file, validates the schema, falls back to
   built-in runtime defaults if missing or invalid.
2. **LoadCandidate()** — reads any candidate version present in the manifest
   without activating it.
3. **PromoteCandidate()** — copies candidate to active (updates manifest,
   copies file).  Returns an error if no candidate is present.
4. **ResolveAuto()** — given a query string, applies the `auto_resolution`
   rules from the active policy (or built-in defaults if policy is absent).
   Does not fall back to remote or cloud sources.

### 5 — Wiring to runtime hot path

In `app/service.go` the strategy resolution block is updated to consult the
policy manager:

```
requested_strategy
  → if "auto"   → policy.ResolveAuto(query)
  → else        → requested_strategy
  → if unknown  → DefaultStrategy (topk_excerpt)
```

The active policy is obtained once at service startup (not per-request).
Invalid policy fields never cause compile failure; the fallback chain is:

1. Active policy field value.
2. Built-in runtime constant (`strategy.go`, `strategy_auto.go`).
3. Hard-coded safe default (`topk_excerpt`).

### 6 — Metering / Evidence

New fields are added to `metering.Event` and persisted to the
`metering_events` table:

| Field | Type | Description |
|-------|------|-------------|
| `compile_strategy_policy_version` | `string` | Version of the active compile strategy policy |
| `compile_strategy_policy_source` | `string` | `"bundled"` / `"local"` / `"cloud-candidate"` |
| `context_strategy_requested` | `string` | Raw value from request (including `"auto"`) |
| `context_strategy_resolved` | `string` | Final strategy name after resolution |
| `context_mode_resolved` | `string` | Final mode after policy resolution |

Existing Phase 2c fields (`ContextStrategy`, `ContextMode`) map to
`context_strategy_resolved` and `context_mode_resolved`.

### 7 — Local candidate pack import (first batch — complete)

The local candidate pack import entry is delivered as of 2026-04-24 (commit `cb4d737`).
The entry reads a JSON candidate pack from the local filesystem, validates it
(SHA-256 hash, structural fields), and writes it to the candidate cache via
`Manager.AcceptCandidate()`. It does not trigger cloud download, does not
auto-promote, and does not enter the compile hot path.

CLI commands delivered:
- `omnimemora import-candidate <path>` — import local JSON pack
- `omnimemora policy-status [--json]` — report active/candidate version separation

The cloud candidate download path remains deferred (see Next Batch below).

### 8 — Cloud candidate download (implemented)

The cloud candidate download path is delivered as of 2026-04-24 (commit `eabe930`).
A pull-style HTTP fetch entry (`omnimemora fetch-candidate <cloud-url> <candidate-id>`)
reads a candidate pack from a configurable cloud URL and writes it to the local
candidate cache via the same `AcceptCandidate()` path as local import — no second
candidate-write logic.

Explicit boundaries:
- Cloud only distributes candidate pack; does not participate in compile decisions.
- No per-request remote strategy decision.
- No auto-promote; candidate staged only.
- No background polling; each invocation is one discrete HTTP GET.
- On HTTP/parse/validation/write failure, manifest and candidate file are unchanged.

---

## Consequences

### Positive

- Compile strategy behaviour becomes observable and reproducible.
- Operators can diff policy files and audit policy changes via git.
- Metering provides a complete chain from request → policy version → resolved
  strategy.
- Cloud candidate evaluation can be added incrementally without touching
  runtime hot-path code.

### Negative / Risks

- A new directory and file format adds maintenance surface; validation
  functions must be kept up to date.
- Adding new policy fields in future schemas requires a migration story
  (version bump + fallback chain).
- The manifest file requires atomic writes on promotion; a future version
  may need a lock file or DB-backed status.

### Mitigations

- Policy validation is strict: unknown fields are ignored, missing required
  fields fall back to built-in constants, so invalid policy never breaks
  compile.
- `local-default-v1.json` is generated from the code's current defaults so
  behaviour is identical to pre-policy code.

---

## References

- Existing related policy managers: `policy_version_manager.py` and `recommendation_policy_version_manager.py` exist in the adapter layer; CSP-001 introduces the first Go runtime compile-strategy policy manager.
- Runtime strategy defaults: `app/context/strategy.go`, `strategy_auto.go`.
- Metering schema: `metering/event.go`.
- Compile hot path: `app/service.go` → `SearchMemory`.
