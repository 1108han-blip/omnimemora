---
doc_id: SPEC-LEGACY-METER-BACKUP-EXPORT-APPROVAL-PACKAGE-MANIFEST-013
title: Legacy Meter Backup Export Approval Template and Package Manifest Preview Contract
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-013
supersedes: []
last_verified_commit: ""
---

# SPEC-LEGACY-METER-BACKUP-EXPORT-APPROVAL-PACKAGE-MANIFEST-013

## Scope

This spec defines approval-template and package-manifest preview only.

No export/copy/archive execution and no cleanup execution is authorized in this line.

## Approval Template Contract

- `schema_version=res-legacy-meter-backup-export-approval-template-v1`
- `mode=approval_template_only`
- `approval_valid=false`
- `backup_export_allowed=false`
- `cleanup_allowed=false`
- `operator_id`
- `approved_at`
- `expires_at`
- `approved_plan_hash`
- `approved_readiness_hash`
- `approved_cleanup_preview_hash`
- `approved_package_manifest_hash`
- `destination_path`
- `reason`

## Package Manifest Preview Contract

- `schema_version=res-legacy-meter-backup-export-package-manifest-v1`
- `mode=package_manifest_preview_only`
- `status`
- `package_id`
- `source_plan_hash`
- `source_readiness_hash`
- `source_cleanup_preview_hash`
- `would_export_files`
- `file_hashes`
- `total_bytes`
- `destination_policy_snapshot`
- `backup_export_allowed=false`
- `cleanup_allowed=false`

## Inputs

- RES-012 backup export dry-run plan
- RES-010 backup export readiness
- RES-009 cleanup preview

## API Contract

- `GET /data-lifecycle/meter-storage/backup-export/approval-template`
- `POST /data-lifecycle/meter-storage/backup-export/approval-template/rebuild`
- `GET /data-lifecycle/meter-storage/backup-export/package-manifest`
- `POST /data-lifecycle/meter-storage/backup-export/package-manifest/rebuild`

## Status Projection

`/data-lifecycle/status.meter_storage_v2.backup_export` extends with:

- `approval_template_status`
- `package_manifest_status`
- `package_manifest_file_count`
- `package_manifest_total_bytes`
- `execution_allowed=false`
- `cleanup_allowed=false`

## Safety Rules

- package manifest build must not create/copy/archive files
- destination checks are read-only only
- approval template is invalid by default and cannot unlock execution
- export/copy/archive execution forbidden
- cleanup execution forbidden
- no legacy meter file mutation

## Non-Goals

- no execution endpoint
- no real backup package
- no runtime destructive behavior
