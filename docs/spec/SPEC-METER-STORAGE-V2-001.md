---
doc_id: SPEC-METER-STORAGE-V2-001
title: Meter Storage V2 - SQLite Mirror and Parity Governance
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-002
supersedes: []
last_verified_commit: ""
---

# SPEC-METER-STORAGE-V2-001

## Scope

This spec covers observe-only `Meter Storage V2` with adapter-local SQLite mirror:

- dual-write mirror for meter writes
- non-destructive rebuild from legacy JSON
- parity status/reporting surfaces

## Storage Contract

Default SQLite file:

- `~/.omnimemora/adapter/meter_store_v2/meter_store.sqlite3`

Core tables:

- `meter_records`
- `meter_store_meta`
- `meter_write_errors`

`meter_records` minimum columns:

- `request_id TEXT PRIMARY KEY`
- `tenant TEXT`
- `agent TEXT`
- `family_id TEXT`
- `timestamp TEXT`
- `task_type TEXT`
- `context_state TEXT`
- `baseline_tokens_estimate INTEGER`
- `actual_tokens_estimate INTEGER`
- `saved_tokens_estimate INTEGER`
- `savings_ratio REAL`
- `payload_json TEXT`
- `created_at TEXT`

Indexes:

- `request_id`
- `(tenant, timestamp)`
- `(family_id, timestamp)`
- `(agent, timestamp)`
- `(timestamp)`

## Write Semantics

Mode: `dual_write_observe_only`

- legacy write path remains authoritative
- SQLite mirror write executes after legacy path logic
- mirror failure is non-fatal for request path
- mirror failure is recorded through:
  - `meter_write_errors`
  - DLP degraded ledger trigger `meter_store_v2_dual_write`

## Read Semantics

In this line:

- legacy remains authoritative for `/requests/{id}/meter`
- `request_evidence` remains legacy-authoritative
- SQLite is shadow-only for diagnostics/parity/rebuild tooling

## API Surface

Read-only / non-destructive endpoints only:

- `GET /data-lifecycle/meter-storage/status`
- `POST /data-lifecycle/meter-storage/rebuild`
- `GET /data-lifecycle/meter-storage/parity`
- `POST /data-lifecycle/meter-storage/parity/rebuild`

Health projection:

- `/data-lifecycle/status.meter_storage_v2`

## Non-Goals

- no production meter read-path switch
- no `request_evidence` read-path switch
- no legacy meter file cleanup/retirement
- no delete/truncate/compact/switch endpoint
