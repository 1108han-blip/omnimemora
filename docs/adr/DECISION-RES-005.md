---
doc_id: ADR-RES-005
title: Metrics Residual Meter Read-Path Switch to SQLite-First with Legacy Fallback
owner: product-arch
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-004
supersedes: []
last_verified_commit: ""
---

# ADR-RES-005: Metrics Residual Meter Read-Path Switch

## Summary

RES-005 does not reopen KPI mainline endpoints because `/metrics/summary`, `/metrics/summary_24h`, and `/metrics/core_capabilities` are already DLP summary-first.

This decision switches only metrics residual/degraded meter reads to:

- `sqlite_first_legacy_fallback`

Fixed conclusion:

- `metrics residual meter reads switched to sqlite-first with legacy fallback; status read model remains legacy-authoritative`

## Decision

1. Introduce dedicated metrics meter resolver with read modes:
   - `legacy_only`
   - `sqlite_first_legacy_fallback` (default)
2. Extend SQLite mirror query surfaces for residual metrics reads:
   - tenant-filtered query
   - time-window query
   - bounded recent query
   - tenant listing
3. Limit metrics wiring changes to residual paths only:
   - recent requests
   - tenant list
   - core capabilities trend
   - summary/core degraded fallback path
4. Keep DLP summary-first hot path unchanged.
5. Keep status read model authority unchanged.

## Rollback

Env rollback switch:

- `OMNIMEMORA_METRICS_METER_READ_PATH=legacy_only`

## Explicit Boundaries

- no status read model authority switch
- no request_evidence read-path changes
- no request meter read-path changes
- no legacy meter file cleanup

## Consequences

- Positive: residual metrics paths gain sqlite-first availability checks with fallback resilience.
- Positive: DLP summary-first contract remains intact for hot reads.
- Negative: status read model migration remains deferred to a separate gated line.
