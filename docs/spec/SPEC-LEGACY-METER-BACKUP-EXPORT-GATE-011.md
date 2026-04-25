---
doc_id: SPEC-LEGACY-METER-BACKUP-EXPORT-GATE-011
title: Legacy Meter Backup Export Execution Gate Contract
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

# SPEC-LEGACY-METER-BACKUP-EXPORT-GATE-011

## Scope

This spec defines execution gate design only.

This spec does not authorize backup export execution or cleanup execution.

## Gate Contract (Design)

- `schema_version=res-legacy-meter-backup-export-gate-v1`
- `mode=gate_design_only`
- `backup_export_allowed=false`
- `cleanup_allowed=false`
- `execution_endpoint_allowed=false`

## Required Inputs

- cleanup preview artifact
- backup export readiness artifact
- meter parity report
- read-path switch flags
- operator approval required
- hash-bound approval
- free-space verification required
- destination policy

## Default Blocking Reasons

- `gate_design_only`
- `missing_operator_approval`
- `backup_destination_not_selected`
- `free_space_not_verified`
- `artifact_hashes_not_bound`
- `cleanup_execution_forbidden`

## Safety Rules

- export/copy/archive execution forbidden
- delete/move/compress/truncate execution forbidden
- no legacy meter file mutation
- no production read-path switch
- no legacy fallback removal

## Non-Goals

- no new API
- no execution endpoint
- no runtime behavior change
