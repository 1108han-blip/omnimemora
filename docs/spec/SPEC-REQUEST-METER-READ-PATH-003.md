---
doc_id: SPEC-REQUEST-METER-READ-PATH-003
title: Request Meter Read Resolver - SQLite First with Legacy Fallback
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-003
supersedes: []
last_verified_commit: ""
---

# SPEC-REQUEST-METER-READ-PATH-003

## Scope

This spec applies only to:

- `GET /requests/{request_id}/meter`

## Read Modes

Env:

- `OMNIMEMORA_REQUEST_METER_READ_PATH`

Supported:

- `legacy_only`
- `sqlite_first_legacy_fallback` (default)

## Resolver Contract

Resolver returns:

- `TokenSavingsMeter` compatible object (or None)
- read mode
- read source (`sqlite | legacy_fallback | legacy`)
- degraded flag and degraded reason

Fallback behavior in sqlite-first mode:

- sqlite read error -> fallback legacy
- sqlite payload malformed -> fallback legacy
- sqlite miss -> fallback legacy

If legacy also misses:

- endpoint returns `404`

## Response Contract

`/requests/{request_id}/meter` response body shape remains unchanged.

Optional diagnostics headers:

- `x-omnimemora-meter-read-mode`
- `x-omnimemora-meter-read-source`

## Health Projection

`/data-lifecycle/status.meter_storage_v2.read_path` includes:

- `request_meter_switch_enabled=true` when sqlite-first mode
- `request_evidence_switch_enabled=false`
- `metrics_switch_enabled=false`
- `legacy_fallback_enabled=true` when sqlite-first mode
- `request_meter_read_mode`

## Non-Goals

- no request-evidence migration
- no metrics migration
- no status read-model migration
- no legacy meter file retirement
