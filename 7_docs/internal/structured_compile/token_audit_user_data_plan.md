# Token Audit and User Pattern Lite Data Plan

Date: 2026-05-13

## Product Decision

OmniMemora should not build a broad user-profile or behavior-surveillance system.

OmniMemora may build a lightweight user database when the data directly supports:

- token saving,
- cost transparency,
- provider-aligned token audit,
- user-visible control over what context enters LLM requests.

The first user data target is not personalization for its own sake. The target is reducing repeated prompts and making AI traffic accounting trustworthy.

## Allowed Data Areas

### User Pattern Lite

Purpose: reduce repeated prompt tokens by storing compact, stable, user-controlled context.

Allowed records:

- explicit response preferences,
- stable project boundaries,
- repeated workflow constraints,
- repeated corrections,
- short product or workspace facts that prevent repeated explanation.

Not allowed:

- sensitive personal profiling,
- psychological, relationship, health, finance, location, or consumption inference,
- hidden behavior tracking from meter/proxy/trace/compile logs,
- model-generated habit claims without evidence,
- automatic upstream injection of low-confidence records.

### Token Audit Mode

Purpose: make LLM middleman/token accounting transparent and provider-aligned.

Allowed records:

- provider and model,
- tokenizer or official count source,
- request/response usage numbers returned by the upstream provider,
- local token estimate,
- estimate confidence class,
- payload hashes and normalized shape metadata,
- detected accounting deltas such as hidden system/tool/schema overhead,
- user-visible audit summaries.

Not allowed:

- storing full raw prompts by default,
- storing full tool outputs by default,
- treating rough estimates as official billing truth,
- hiding confidence level from the user,
- using audit records as a behavior-profile source.

## Database Direction

A small user database is allowed if it stays bounded, modular, and user-facing.

Initial database principles:

- Use SQLite unless there is a concrete reason not to.
- Keep the database separate from large JSONL trace/proxy/compile logs.
- Store hashes, references, counters, and compact metadata by default.
- Put raw text behind explicit retention and purpose gates.
- Keep retention short for audit raw material; keep user-approved patterns only while useful.
- Provide delete/export/disable paths before normal release.
- Do not make request forwarding depend on slow database writes.

Candidate tables:

| Table | Purpose | Size Boundary |
|---|---|---|
| `user_pattern_candidates` | pending lightweight preference/workflow/project/correction records | compact text only, reviewed before compile injection |
| `user_patterns` | approved records allowed for compile consideration | compact text only, with scope and expiry |
| `token_audit_records` | per-request accounting summary | hashes and counts, no raw payload by default |
| `token_audit_deltas` | provider/local/middleman accounting deltas | numeric and categorical fields only |
| `user_data_events` | user-visible create/update/delete/approval events | compact metadata |

This database is not a replacement for `memory.db` in the first phase. It is a product-facing user data plane for token-saving and token-audit control. Whether it later merges with, references, or wraps `memory.db` remains an implementation decision.

## Module Direction

Adding modules is allowed. Large files are not.

Preferred module split:

- `user_data/`: small SQLite schema and repository helpers.
- `token_audit/`: provider-specific counters, official usage reconciliation, confidence classification.
- `user_patterns/`: candidate extraction, approval state, compile eligibility.
- `compile_injection/`: small selector that turns approved records into compact context only when relevant.

Boundaries:

- No model-based extraction on the upstream-critical path.
- No historical file scans on normal request paths.
- No long JSON blobs when normalized columns or compact records are enough.
- No module should become a catch-all for compile, memory, audit, and UI behavior.

## Token Audit MVP

The first useful version should answer:

- What did the client send?
- What did OmniMemora forward?
- What did the upstream provider count?
- What did OmniMemora estimate?
- Was the count official, official-count-API, tokenizer-estimated, or rough?
- Did a middleman/provider add or hide meaningful token overhead?

Provider confidence classes:

- `official_usage`: upstream response provided usage fields.
- `official_count_api`: provider count endpoint was used before generation.
- `provider_tokenizer`: local tokenizer matches a provider-supported tokenizer.
- `compatible_estimate`: tokenizer is close but not official for the exact model.
- `rough_estimate`: fallback only; not suitable for billing claims.

## User Controls Required Before Normal Release

- View stored user patterns.
- Delete stored user patterns.
- Disable User Pattern Lite injection.
- View token audit summaries.
- Delete or expire token audit records.
- Show confidence class beside token counts.
- Explain whether a count is billable truth, provider-reported usage, or local estimate.

## Running Requirements

Token Audit Mode and User Pattern Lite must not slow the core request path.

Targets:

- request forwarding does not wait on noncritical audit persistence;
- user-pattern selection is bounded and small;
- database writes use short transactions;
- raw logs remain capped by existing internal retention policy;
- `/health`, `/metrics/core_capabilities`, `/metrics/summary`, and `/compile/status` remain responsive during validation.

## Next Gate

Before implementation:

1. Decide whether the first database is a new SQLite file or a bounded extension around existing runtime storage.
2. Define exact first provider scope for Token Audit Mode.
3. Define which fields may be stored without raw prompt text.
4. Add tests for retention, delete/export control, confidence labels, and no raw-payload default.
5. Keep the implementation in focused modules and avoid growing existing ingress files.
