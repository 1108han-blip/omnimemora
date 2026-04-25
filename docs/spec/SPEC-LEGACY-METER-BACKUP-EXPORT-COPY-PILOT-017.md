---
doc_id: SPEC-LEGACY-METER-BACKUP-EXPORT-COPY-PILOT-017
title: Single Backup Export Copy Pilot Contract
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-26
depends_on:
  - ADR-RES-017
supersedes: []
last_verified_commit: "583be04"
---

# SPEC-LEGACY-METER-BACKUP-EXPORT-COPY-PILOT-017

## Scope

This spec defines single copy-only backup export pilot execution.

No full export and no cleanup execution is authorized in this line.

## Copy Pilot Record Contract

- `schema_version=res-legacy-meter-backup-export-copy-pilot-v1`
- `mode=single_copy_pilot_only`
- `pilot_id`
- `executed_at`
- `status`
- `pilot_scope_override`
- `full_export_allowed`
- `gate_ref`
- `package_manifest_ref`
- `selected_candidate`
- `target_path`
- `copied_bytes`
- `source_sha256`
- `copied_sha256`
- `checksum_match`
- `source_retained=true`
- `cleanup_started=false`
- `read_path_unchanged=true`
- `blocking_reasons`
- `summary`

## Candidate Rule

- candidate must be selected from package manifest file list (`files` or `would_export_files`)
- candidate must be legacy meter file (`meters_index.json` or `meters_*.json`)
- default selector chooses smallest bytes candidate
- source must exist

## Target and Copy Rule

- target root must be configured pilot root
- target filename must be deterministic based on source
- no overwrite:
  - existing same checksum => `already_copied`
  - existing different checksum => `target_conflict` block
- source checksum and copied checksum must match

## Gate Rule

- execution gate artifact is required
- if gate is blocked only by missing operator approval:
  - pilot override may allow single-file copy (`pilot_scope_override=true`)
  - full export still remains disallowed
- if override disabled, safe block with `blocked_missing_operator_approval`

## API Contract

- `POST /data-lifecycle/meter-storage/backup-export/copy-pilot/run-one`
- `GET /data-lifecycle/meter-storage/backup-export/copy-pilot/latest`

## Status Projection

`/data-lifecycle/status.meter_storage_v2.backup_export` extends with:

- `copy_pilot_status`
- `copy_pilot_source_retained`
- `copy_pilot_checksum_match`
- `copy_pilot_cleanup_started=false`
- `copy_pilot_read_path_unchanged=true`

## Safety Rules

- no full export endpoint
- no cleanup endpoint
- no delete/move/compress/truncate endpoint
- no read path switch
- source retained
