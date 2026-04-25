---
doc_id: SPEC-LEGACY-METER-BACKUP-EXPORT-DRY-RUN-012
title: Legacy Meter Backup Export Dry-Run Plan Contract
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-012
supersedes: []
last_verified_commit: ""
---

# SPEC-LEGACY-METER-BACKUP-EXPORT-DRY-RUN-012

## Scope

This spec defines dry-run preview and non-destructive planning only.

No export/copy/archive execution and no cleanup execution is authorized in this line.

## Plan Artifact Contract

- `schema_version=res-legacy-meter-backup-export-plan-v1`
- `mode=dry_run_preview_only`
- `status`
- `backup_export_allowed=false`
- `cleanup_allowed=false`
- `execution_allowed=false`
- `source_readiness_hash`
- `source_cleanup_preview_hash`
- `destination_policy`
- `destination_status`
- `would_export_files`
- `estimated_export_bytes`
- `required_free_bytes`
- `blocking_reasons`
- `summary`

## Inputs

- RES-009 cleanup preview
- RES-010 backup export readiness
- RES-011 gate design constraints
- parity report and read-path flags
- optional destination env:
  - `OMNIMEMORA_DLP_METER_BACKUP_EXPORT_DESTINATION`

## API Contract

- `GET /data-lifecycle/meter-storage/backup-export/plan`
- `POST /data-lifecycle/meter-storage/backup-export/plan/rebuild`

## Status Projection

`/data-lifecycle/status.meter_storage_v2.backup_export` extends with:

- `plan_status`
- `dry_run_mode`
- `candidate_file_count`
- `estimated_export_bytes`
- `destination_status`
- `blocking_reasons_count`

## Safety Rules

- destination check is read-only (no directory create, no file write)
- export/copy/archive execution forbidden
- cleanup execution forbidden
- no legacy meter file mutation

## Non-Goals

- no execution endpoint
- no real backup package
- no runtime destructive behavior
