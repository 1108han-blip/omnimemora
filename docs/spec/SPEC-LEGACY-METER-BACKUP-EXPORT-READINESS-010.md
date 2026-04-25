---
doc_id: SPEC-LEGACY-METER-BACKUP-EXPORT-READINESS-010
title: Legacy Meter Backup Export Readiness Artifact and API Contract
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-010
supersedes: []
last_verified_commit: ""
---

# SPEC-LEGACY-METER-BACKUP-EXPORT-READINESS-010

## Scope

This spec defines backup export readiness preview only.

No backup export execution and no cleanup execution is authorized in this line.

## Inputs

- RES-009 cleanup preview artifact
- legacy meter files inventory
- parity report
- read-path flags

## Readiness Output Contract

- `schema_version=res-legacy-meter-backup-export-readiness-v1`
- `mode=backup_export_readiness_only`
- `backup_export_allowed=false`
- `cleanup_allowed=false`
- `would_export_files`
- `export_manifest_preview`
- `estimated_export_bytes`
- `required_free_bytes`
- `checksum_algorithm=sha256`
- `blocking_reasons`

## API Contract

- `GET /data-lifecycle/meter-storage/backup-export/readiness`
- `POST /data-lifecycle/meter-storage/backup-export/readiness/rebuild`

If artifact is missing, GET returns schema + `status=missing`.

## Status Projection

`/data-lifecycle/status.meter_storage_v2.backup_export` includes:

- `status`
- `mode=backup_export_readiness_only`
- `backup_export_allowed=false`
- `cleanup_allowed=false`
- `candidate_file_count`
- `estimated_export_bytes`
- `blocking_reasons_count`

## Non-Goals

- no export/copy/archive endpoint
- no delete/move/compress/truncate endpoint
- no legacy file mutation
- no fallback removal
