---
doc_id: ADR-RES-011
title: Legacy Meter Backup Export Execution Gate Design Freeze
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

# ADR-RES-011: Legacy Meter Backup Export Execution Gate Design

## Summary

Design-only freeze for backup export execution gate.

Fixed conclusion:

- `backup export execution gate designed; backup export execution not started; cleanup execution not started`

## Decision

1. Define execution gate contract only; no execution implementation in this line.
2. Keep gate outputs fixed in RES-011:
   - `mode=gate_design_only`
   - `backup_export_allowed=false`
   - `cleanup_allowed=false`
   - `execution_endpoint_allowed=false`
3. Require explicit gate inputs for any future execution line:
   - cleanup preview
   - backup export readiness
   - parity status
   - read-path switch flags
   - operator approval required
   - hash-bound approval
   - free-space verification required
   - destination policy

## Blocking Model

Default blocking reasons include:

- `gate_design_only`
- `missing_operator_approval`
- `backup_destination_not_selected`
- `free_space_not_verified`
- `artifact_hashes_not_bound`
- `cleanup_execution_forbidden`

## Explicit Non-Goals

- no API additions
- no export/copy/archive execution
- no delete/move/compress/truncate execution
- no legacy meter file mutation
- no read-path or fallback changes

## Consequences

- Positive: execution risk is reduced by pre-binding approvals, hashes, and capacity checks.
- Positive: current safety posture remains unchanged.
- Negative: backup export execution remains deferred.
