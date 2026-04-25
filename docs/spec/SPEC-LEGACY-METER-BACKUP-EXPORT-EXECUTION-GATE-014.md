---
doc_id: SPEC-LEGACY-METER-BACKUP-EXPORT-EXECUTION-GATE-014
title: Legacy Meter Backup Export Execution Gate Candidate Contract
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-014
supersedes: []
last_verified_commit: ""
---

# SPEC-LEGACY-METER-BACKUP-EXPORT-EXECUTION-GATE-014

## Scope

This spec defines execution gate candidate evaluation only.

No export/copy/archive execution and no cleanup execution is authorized in this line.

## Operator Approval Artifact Contract

- `schema_version=res-legacy-meter-backup-export-operator-approval-v1`
- `approval_id`
- `operator_id`
- `approved_at`
- `expires_at`
- `approved_plan_hash`
- `approved_package_manifest_hash`
- `approved_readiness_hash`
- `approved_cleanup_preview_hash`
- `destination_path`
- `reason`

## Execution Gate Contract

- `schema_version=res-legacy-meter-backup-export-execution-gate-v1`
- `mode=execution_gate_only`
- `allowed`
- `status`
- `artifact_hashes`
- `approval.status`
- `approval.operator_id`
- `approval.expires_at`
- `approval.destination_path`
- `blocking_reasons`
- `summary`
- `backup_export_execution_started=false`
- `cleanup_execution_started=false`

## Decision Rule

- default without operator approval: `allowed=false` + `missing_operator_approval`
- with approval:
  - expires-at must be valid and unexpired
  - destination path must match current plan destination path
  - all bound hashes must match current artifacts
- any mismatch or invalid field blocks gate

## Inputs

- RES-009 cleanup preview
- RES-010 backup export readiness
- RES-012 backup export plan
- RES-013 backup export package manifest
- RES-013 approval template
- optional local operator approval artifact

## API Contract

- `GET /data-lifecycle/meter-storage/backup-export/execution/gate`
- `POST /data-lifecycle/meter-storage/backup-export/execution/gate/rebuild`
- `GET /data-lifecycle/meter-storage/backup-export/operator-approval`

## Status Projection

`/data-lifecycle/status.meter_storage_v2.backup_export` extends with:

- `execution_gate_status`
- `execution_gate_allowed`
- `approval_status`
- `blocking_reasons_count`
- `backup_export_execution_started=false`
- `cleanup_execution_started=false`

## Safety Rules

- no API create/approve operator approval
- no execute/copy/archive/delete/move/compress/truncate endpoint
- no destination write/copy/package creation
- no legacy meter file mutation

## Non-Goals

- no real backup export execution
- no cleanup execution
- no automatic approval injection in running validation
