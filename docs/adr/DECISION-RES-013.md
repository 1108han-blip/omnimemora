---
doc_id: ADR-RES-013
title: Legacy Meter Backup Export Approval Template and Package Manifest Preview
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-012
supersedes: []
last_verified_commit: "2a25512"
---

# ADR-RES-013: Legacy Meter Backup Export Approval Template and Package Manifest Preview

## Summary

Introduce approval-template and package-manifest preview artifacts for backup export governance.

Fixed conclusion:

- `backup export approval template and package manifest preview generated; backup export execution not started; cleanup execution not started`

## Decision

1. Add approval template artifact:
   - `schema_version=res-legacy-meter-backup-export-approval-template-v1`
   - `mode=approval_template_only`
2. Add package manifest preview artifact:
   - `schema_version=res-legacy-meter-backup-export-package-manifest-v1`
   - `mode=package_manifest_preview_only`
3. Keep all execution gates blocked in RES-013:
   - `approval_valid=false`
   - `backup_export_allowed=false`
   - `cleanup_allowed=false`
4. Add read-only API surface:
   - `GET /data-lifecycle/meter-storage/backup-export/approval-template`
   - `POST /data-lifecycle/meter-storage/backup-export/approval-template/rebuild`
   - `GET /data-lifecycle/meter-storage/backup-export/package-manifest`
   - `POST /data-lifecycle/meter-storage/backup-export/package-manifest/rebuild`
5. Extend status projection under:
   - `/data-lifecycle/status.meter_storage_v2.backup_export`

## Safety Boundary

- no real backup package generation
- no file copy/move/archive
- no delete/compress/truncate/cleanup execution
- no legacy meter file mutation
- no production read-path switch
- no fallback removal

## Consequences

- Positive: operator-review inputs become hash-bound and auditable before execution lines.
- Positive: package scope and byte estimates are reproducible without touching destination.
- Negative: execution remains explicitly blocked in this line.
