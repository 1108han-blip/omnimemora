---
doc_id: ADR-RES-012
title: Legacy Meter Backup Export Dry-Run Preview
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-011
supersedes: []
last_verified_commit: ""
---

# ADR-RES-012: Legacy Meter Backup Export Dry-Run Preview

## Summary

Introduce non-destructive backup export dry-run planning artifact and read-only APIs.

Fixed conclusion:

- `legacy meter backup export dry-run preview generated; backup export execution not started; cleanup execution not started`

## Decision

1. Add dry-run plan artifact:
   - `schema_version=res-legacy-meter-backup-export-plan-v1`
   - `mode=dry_run_preview_only`
2. Keep all execution gates blocked in RES-012:
   - `backup_export_allowed=false`
   - `cleanup_allowed=false`
   - `execution_allowed=false`
3. Add read-only API surface:
   - `GET /data-lifecycle/meter-storage/backup-export/plan`
   - `POST /data-lifecycle/meter-storage/backup-export/plan/rebuild`
4. Add status projection under:
   - `/data-lifecycle/status.meter_storage_v2.backup_export`

## Safety Boundary

- no real backup package generation
- no file copy/move/archive
- no delete/compress/truncate/cleanup execution
- no legacy meter file mutation
- no production read-path switch
- no fallback removal

## Consequences

- Positive: future execution line gets hash-bound, capacity-bound dry-run evidence.
- Positive: execution risk remains bounded while planning fidelity increases.
- Negative: export execution remains deferred.
