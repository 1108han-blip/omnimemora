---
doc_id: SPEC-METRICS-RESIDUAL-METER-READ-PATH-005
title: Metrics Residual Meter Read Resolver - SQLite First with Legacy Fallback
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-005
supersedes: []
last_verified_commit: ""
---

# SPEC-METRICS-RESIDUAL-METER-READ-PATH-005

## Scope

This spec applies only to metrics residual/degraded meter read surfaces:

- recent requests
- tenant list
- core capability trend
- summary/core fallback paths that require meter scans

## Read Modes

Env:

- `OMNIMEMORA_METRICS_METER_READ_PATH`

Supported:

- `legacy_only`
- `sqlite_first_legacy_fallback` (default)

## SQLite Query Contract

`meter_store_v2` must provide:

- query by tenant
- query by timestamp window
- bounded recent query
- tenant listing

All queries are read-only and non-destructive.

## Resolver Contract

Metrics resolver returns:

- selected meter list
- selected source (`sqlite | legacy_fallback | legacy`)
- degraded flag and degraded reason

Fallback behavior in sqlite-first mode:

- sqlite read error -> fallback legacy
- sqlite payload malformed -> fallback legacy
- sqlite empty result while legacy has data -> fallback legacy

## Service Wiring Contract

`metrics_service` residual paths use resolver:

- `_collect_meters`
- `_collect_meters_24h`
- `list_tenants`
- `compute_core_capabilities_trend`

DLP summary-first hot path remains unchanged.

## Status Projection Contract

`/data-lifecycle/status.meter_storage_v2.read_path` includes:

- `metrics_switch_enabled`
- `metrics_read_mode`
- `status_read_model_switch_enabled=false`
- `legacy_fallback_enabled=true` when sqlite-first modes are enabled

## Non-Goals

- no status read model migration
- no request_evidence migration
- no request meter migration
- no legacy meter file delete/move/compress/truncate
