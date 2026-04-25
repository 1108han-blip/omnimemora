---
doc_id: SPEC-STATUS-READ-MODEL-METER-READ-PATH-006
title: Status Read Model Meter Resolver - SQLite First with Legacy Fallback
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-006
supersedes: []
last_verified_commit: ""
---

# SPEC-STATUS-READ-MODEL-METER-READ-PATH-006

## Scope

This spec applies only to status read-model meter collection surfaces:

- `_collect_observed_family_meters`
- `compute_family_24h_metrics`

## Read Modes

Env:

- `OMNIMEMORA_STATUS_READ_MODEL_METER_READ_PATH`

Supported:

- `legacy_only`
- `sqlite_first_legacy_fallback` (default)

## Resolver Contract

Resolver returns:

- meter list
- read mode
- read source (`sqlite | legacy_fallback | legacy`)
- degraded flag and degraded reason

Fallback behavior in sqlite-first mode:

- sqlite read error -> fallback legacy
- sqlite payload malformed -> fallback legacy
- sqlite miss with legacy data -> fallback legacy
- sqlite miss with legacy miss -> empty result

## Semantics Compatibility

The following semantics must remain unchanged:

- `derive_traffic_truth` priority levels
- family alias behavior (`cc-haha` remains Claude family variant)
- `traffic_truth` enum values
- observed `last_request_at` precedence
- `/agents/control` top-level schema (`agents`, `count`, `system_status`)

## Status Projection Contract

`/data-lifecycle/status.meter_storage_v2.read_path` includes:

- `status_read_model_switch_enabled`
- `status_read_model_read_mode`
- `legacy_fallback_enabled=true` when sqlite-first modes are enabled

## Non-Goals

- no control schema changes
- no UI changes
- no request meter changes
- no request evidence changes
- no metrics residual changes
- no legacy meter file delete/move/compress/truncate
