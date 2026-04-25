---
doc_id: SPEC-LEGACY-METER-CLEANUP-PREVIEW-009
title: Legacy Meter Cleanup Preview Artifact and API Contract
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-009
supersedes: []
last_verified_commit: ""
---

# SPEC-LEGACY-METER-CLEANUP-PREVIEW-009

## Scope

This spec defines preview-only cleanup capability for legacy meter files.

No cleanup execution is authorized in this line.

## Inputs

- legacy meter files inventory:
  - `meters_index.json`
  - `meters_*.json`
- sqlite parity report
- read-path flags
- readiness requirements from RES-008

## Preview Output Contract

- `schema_version=res-legacy-meter-cleanup-preview-v1`
- `mode=preview_only`
- `cleanup_allowed=false`
- `would_cleanup_files`
- `would_retain_files`
- `estimated_reclaim_bytes`
- `blocking_reasons`
- `backup_export_required=true`
- `operator_approval_required=true`

## Eligibility Logic

Preview eligibility evaluation checks all:

- parity passed
- `critical_mismatch_count=0`
- all read-path switches enabled
- legacy fallback enabled
- backup/export missing => cleanup blocked
- approval missing => cleanup blocked

`cleanup_allowed` remains `false` in RES-009.

## API Contract

- `GET /data-lifecycle/meter-storage/cleanup/preview`
- `POST /data-lifecycle/meter-storage/cleanup/preview/rebuild`

If preview artifact is missing, GET returns schema+`status=missing`.

## Status Projection

`/data-lifecycle/status.meter_storage_v2.cleanup` includes:

- `status`
- `mode=preview_only`
- `cleanup_allowed=false`
- `candidate_file_count`
- `estimated_reclaim_bytes`
- `blocking_reasons_count`

## Non-Goals

- no execute/delete/move/compress/truncate endpoint
- no legacy file mutation
- no fallback removal
