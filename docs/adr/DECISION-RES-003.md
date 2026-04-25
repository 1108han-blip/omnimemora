---
doc_id: ADR-RES-003
title: Narrow Request Meter Read-Path Switch to SQLite-First with Legacy Fallback
owner: product-arch
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-002
supersedes: []
last_verified_commit: ""
---

# ADR-RES-003: Narrow Request Meter Read-Path Switch

## Summary

Switch only `GET /requests/{request_id}/meter` to:

- `sqlite_first_legacy_fallback`

Fixed conclusion:

- `request meter read path switched to sqlite-first with legacy fallback`
- `request_evidence and metrics remain legacy-authoritative`

## Decision

1. Introduce dedicated meter read resolver for request-meter surface only.
2. Keep diagnostics/status read model and request-evidence builder on legacy meter authority.
3. Keep metrics summary/read-model paths unchanged.
4. Add read-path diagnostics headers on request-meter endpoint:
   - `x-omnimemora-meter-read-mode`
   - `x-omnimemora-meter-read-source`
5. On sqlite miss/malformed/read error, fallback to legacy and do not fail request if legacy has the record.
6. Record fallback degraded evidence in DLP ledger.

## Rollback

Env rollback switch:

- `OMNIMEMORA_REQUEST_METER_READ_PATH=legacy_only`

Supported values:

- `legacy_only`
- `sqlite_first_legacy_fallback` (default)

## Explicit Boundaries

- no request-evidence read-path switch
- no metrics read-path switch
- no status read-model meter authority switch
- no legacy meter file cleanup

## Consequences

- Positive: smallest production read-path switch validates SQLite V2 real availability.
- Positive: legacy fallback keeps request-meter response resilience.
- Negative: broader read-path migrations remain deferred to future gated lines.
