---
doc_id: SPEC-LEGACY-METER-BACKUP-EXPORT-RESTORE-READBACK-018
title: Legacy Meter Backup Export Restore/Readback Validation Contract
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-26
depends_on:
  - ADR-RES-018
  - SPEC-LEGACY-METER-BACKUP-EXPORT-COPY-PILOT-017
supersedes: []
last_verified_commit: "98028df"
---

# SPEC-LEGACY-METER-BACKUP-EXPORT-RESTORE-READBACK-018

## Scope

This spec defines validation-only restore/readback for the RES-017 single backup export copy pilot.

It does not authorize production restore, production read-path switching, cleanup execution, source movement, source deletion, compression, or truncation.

## Validation Record Contract

- `schema_version=res-legacy-meter-backup-export-restore-readback-v1`
- `mode=restore_readback_validation_only`
- `report_id`
- `generated_at`
- `status`
- `copy_pilot_ref`
- `source_path`
- `backup_copy_path`
- `source_sha256`
- `backup_copy_sha256`
- `checksum_match`
- `production_restore_started=false`
- `read_path_unchanged=true`
- `source_retained=true`
- `cleanup_started=false`
- `blocking_reasons`
- `summary`

## Validation Rules

- Validation must use the RES-017 copy-pilot artifact as its input.
- The backup copy must be readable without mutating the retained source.
- Source and backup-copy checksums must match for a passed result.
- Readback validation may inspect copied content for integrity, but must not install it as production state.
- A passed RES-018 result is not cleanup approval.

## Forbidden Effects

- no production restore
- no overwrite of production meter state
- no production read-path switch
- no cleanup execution
- no delete/move/compress/truncate
- no source mutation
- no source move

## Status Projection

Any status or closeout wording for RES-018 must preserve these explicit fields:

- `restore_readback_validation_status`
- `restore_readback_validation_mode=restore_readback_validation_only`
- `restore_readback_checksum_match`
- `restore_readback_source_retained=true`
- `restore_readback_production_restore_started=false`
- `restore_readback_read_path_unchanged=true`
- `restore_readback_cleanup_started=false`

## Exit Condition

RES-018 can be marked passed only when the validation record preserves all safety invariants:

- source retained
- checksum/readback validation passed
- production restore not started
- production read path unchanged
- cleanup/delete/move/compress/truncate not started
