---
doc_id: ADR-RES-004
title: Request Evidence Meter Read-Path Switch to SQLite-First with Legacy Fallback
owner: product-arch
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-003
supersedes: []
last_verified_commit: ""
---

# ADR-RES-004: Request Evidence Meter Read-Path Switch

## Summary

Switch only `/debug/request_evidence` meter read source to:

- `sqlite_first_legacy_fallback`

Fixed conclusion:

- `request_evidence meter read path switched to sqlite-first with legacy fallback; metrics and status read model remain legacy-authoritative`

## Decision

1. Introduce dedicated request-evidence meter resolver with read mode:
   - `legacy_only`
   - `sqlite_first_legacy_fallback` (default)
2. Keep existing `build_request_evidence_payload()` legacy path unchanged for compatibility.
3. Add resolved request-evidence builder that:
   - selects sqlite-first with legacy fallback
   - appends read diagnostics and shadow parity status
4. Route `/debug/request_evidence` to resolved builder only.
5. Keep `build_context_diff_payload()`, metrics read model, and status read model on legacy-authoritative path.

## Rollback

Env rollback switch:

- `OMNIMEMORA_REQUEST_EVIDENCE_METER_READ_PATH=legacy_only`

## Explicit Boundaries

- no metrics read-path switch
- no status read-model authority switch
- no context-diff read-path switch
- no legacy meter file cleanup

## Consequences

- Positive: request_evidence can validate sqlite meter read availability under real traffic with legacy fallback safety.
- Positive: parity signal can be observed without broad read-model migration.
- Negative: metrics/status read-model migration remains deferred to separate gated lines.
