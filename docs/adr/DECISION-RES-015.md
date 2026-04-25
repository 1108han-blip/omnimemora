---
doc_id: ADR-RES-015
title: Legacy Meter Backup Export Execution Proposal Only
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-014
supersedes: []
last_verified_commit: "2611f3f"
---

# ADR-RES-015: Legacy Meter Backup Export Execution Proposal Only

## Summary

Introduce a proposal-only execution artifact that aggregates gate, approval, package manifest, destination snapshot, estimated impact, and rollback requirements without starting backup export execution.

Fixed conclusion:

- `backup export execution proposal generated; backup export execution not started; cleanup execution not started`

## Decision

1. Add execution proposal artifact:
   - `schema_version=res-legacy-meter-backup-export-execution-proposal-v1`
   - `mode=proposal_only`
2. Add read-only API surface:
   - `GET /data-lifecycle/meter-storage/backup-export/execution/proposal`
   - `POST /data-lifecycle/meter-storage/backup-export/execution/proposal/rebuild`
3. Add status projection:
   - `execution_proposal_status`
   - `operator_decision_required`
   - `backup_export_execution_started=false`
   - `cleanup_execution_started=false`
4. Preserve explicit non-goals:
   - no execute/run/copy/archive endpoint for backup export proposal
   - no cleanup execution/delete/move/compress/truncate endpoint

## Safety Boundary

- proposal generation only; no backup export execution
- no cleanup execution
- no destination write/copy/archive
- no legacy meter file mutation
- no production read-path switch

## Consequences

- Positive: operator receives a deterministic and auditable final proposal artifact before any future execution line.
- Positive: RES-014 gate/approval contracts are reused and surfaced in one review artifact.
- Negative: real export remains deferred to a later explicit operator decision and separate execution batch.
