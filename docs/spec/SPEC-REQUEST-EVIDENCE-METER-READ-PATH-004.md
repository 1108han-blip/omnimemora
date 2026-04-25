---
doc_id: SPEC-REQUEST-EVIDENCE-METER-READ-PATH-004
title: Request Evidence Meter Read Resolver - SQLite First with Legacy Fallback
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-004
supersedes: []
last_verified_commit: ""
---

# SPEC-REQUEST-EVIDENCE-METER-READ-PATH-004

## Scope

This spec applies only to:

- `GET /debug/request_evidence`

## Read Modes

Env:

- `OMNIMEMORA_REQUEST_EVIDENCE_METER_READ_PATH`

Supported:

- `legacy_only`
- `sqlite_first_legacy_fallback` (default)

## Resolver Contract

Resolver returns:

- selected meter object or `None`
- selected source (`sqlite | legacy_fallback | legacy`)
- `legacy_meter` and `sqlite_meter` for shadow parity
- degraded flag and degraded reason

Fallback behavior in sqlite-first mode:

- sqlite read error -> fallback legacy
- sqlite payload malformed -> fallback legacy
- sqlite miss -> fallback legacy

If legacy also misses:

- endpoint returns `404`

## Route Contract

`/debug/request_evidence` appends diagnostics headers:

- `x-omnimemora-request-evidence-meter-read-mode`
- `x-omnimemora-request-evidence-meter-read-source`
- `x-omnimemora-request-evidence-meter-shadow-status`

Response body remains backward compatible and may append:

- `request_evidence_meter_read`
- `request_evidence_meter_shadow`

## Shadow Parity Contract

Shadow compares core fields between sqlite and legacy request-evidence payloads:

- `identity`
- `access_plan`
- `actual_enforcement`
- `tokens`
- `request_class`
- `status`

Output:

- `request_evidence_meter_shadow.status = passed | degraded`

## Non-Goals

- no metrics migration
- no status read-model migration
- no context-diff migration
- no legacy meter file delete/move/compress/truncate
