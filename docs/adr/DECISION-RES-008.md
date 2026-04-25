---
doc_id: ADR-RES-008
title: Legacy Meter Cleanup Readiness Design Freeze
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-007
supersedes: []
last_verified_commit: ""
---

# ADR-RES-008: Legacy Meter Cleanup Readiness Design

## Summary

Design-only line for legacy meter cleanup readiness.

Fixed conclusion:

- `legacy meter cleanup readiness designed; cleanup execution not started`

## Decision

1. Keep current operating baseline:
   - `cleanup_eligibility=readiness_only`
   - all active meter read paths remain sqlite-first with legacy fallback
2. Define cleanup readiness conditions and gate contract only.
3. Do not execute destructive actions in this line.

## Readiness Conditions

Cleanup design requires all of the following before any future execution line:

- parity passed (`critical_mismatch_count=0`)
- read-path flags visible and sqlite-first enabled for:
  - request meter
  - request_evidence
  - metrics residual
  - status read model
- explicit operator approval required
- backup/export required before destructive action

## Explicit Non-Goals

- no cleanup API implementation
- no delete/move/compress/truncate execution
- no legacy fallback shutdown
- no legacy meter file mutation
- no Codex live validation expansion

## Consequences

- Positive: future cleanup line gets auditable readiness prerequisites and rollback boundaries.
- Positive: current production safety posture remains unchanged.
- Negative: storage reclamation is intentionally deferred.
