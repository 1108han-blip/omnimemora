---
doc_id: SPEC-LEGACY-METER-BACKUP-EXPORT-EXECUTION-PROPOSAL-015
title: Legacy Meter Backup Export Execution Proposal Contract
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-015
supersedes: []
last_verified_commit: "2611f3f"
---

# SPEC-LEGACY-METER-BACKUP-EXPORT-EXECUTION-PROPOSAL-015

## Scope

This spec defines execution proposal generation only.

No export/copy/archive execution and no cleanup execution is authorized in this line.

## Proposal Contract

- `schema_version=res-legacy-meter-backup-export-execution-proposal-v1`
- `mode=proposal_only`
- `proposal_id`
- `generated_at`
- `proposal_status`
- `execution_started=false`
- `cleanup_started=false`
- `gate_ref`
- `approval_ref`
- `package_manifest_ref`
- `destination_snapshot`
- `estimated_export_bytes`
- `candidate_file_count`
- `rollback_requirements`
- `operator_decision_required=true`
- `blocking_reasons`
- `summary`

## Proposal Status Rule

- default blocked when gate/approval/package manifest inputs are missing or gate is not allowed
- can become `ready_for_operator_decision` only when:
  - gate artifact exists and `status=allowed`
  - operator approval artifact exists
  - package manifest exists
  - proposal still keeps `execution_started=false` and `cleanup_started=false`

## Inputs

- RES-014 execution gate artifact
- RES-014 operator approval artifact
- RES-013 package manifest
- RES-012 plan

## API Contract

- `GET /data-lifecycle/meter-storage/backup-export/execution/proposal`
- `POST /data-lifecycle/meter-storage/backup-export/execution/proposal/rebuild`

## Status Projection

`/data-lifecycle/status.meter_storage_v2.backup_export` extends with:

- `execution_proposal_status`
- `operator_decision_required`
- `backup_export_execution_started=false`
- `cleanup_execution_started=false`

## Safety Rules

- no execute/run/copy/archive endpoint for execution proposal
- no cleanup/delete/move/compress/truncate endpoint
- no destination write/copy/package mutation
- no legacy meter source mutation

## Non-Goals

- no real backup export execution
- no cleanup execution
- no automatic operator decision injection
