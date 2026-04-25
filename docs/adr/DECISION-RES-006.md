---
doc_id: ADR-RES-006
title: Status Read Model Meter Read-Path Switch to SQLite-First with Legacy Fallback
owner: product-arch
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-005
supersedes: []
last_verified_commit: ""
---

# ADR-RES-006: Status Read Model Meter Read-Path Switch

## Summary

Switch only status read-model meter sourcing to:

- `sqlite_first_legacy_fallback`

Fixed conclusion:

- `status read model meter reads switched to sqlite-first with legacy fallback; /agents/control schema and truth semantics unchanged`

## Decision

1. Introduce dedicated status-read-model meter resolver with read modes:
   - `legacy_only`
   - `sqlite_first_legacy_fallback` (default)
2. Restrict wiring changes to status read-model meter collection only:
   - `_collect_observed_family_meters`
   - `compute_family_24h_metrics`
3. Keep unchanged:
   - `derive_traffic_truth` five-level priority
   - family alias behavior (including `cc-haha -> claude_code`)
   - `/agents/control` top-level schema
   - truth enums and message semantics
   - summary fresh/stale/fallback routing

## Rollback

Env rollback switch:

- `OMNIMEMORA_STATUS_READ_MODEL_METER_READ_PATH=legacy_only`

## Explicit Boundaries

- no `/agents/control` schema change
- no control truth semantics change
- no UI changes
- no request meter / request evidence / metrics residual read-path changes
- no legacy meter file cleanup

## Consequences

- Positive: status read-model meter reads gain sqlite-first availability checks with legacy fallback safety.
- Positive: control surface output compatibility remains stable.
- Negative: legacy meter cleanup remains deferred.
