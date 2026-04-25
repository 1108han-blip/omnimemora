---
doc_id: ADR-RES-009
title: Legacy Meter Cleanup Preview Only
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-008
supersedes: []
last_verified_commit: ""
---

# ADR-RES-009: Legacy Meter Cleanup Preview Only

## Summary

Implement preview-only capability for legacy meter cleanup impact estimation.

Fixed conclusion:

- `legacy meter cleanup preview generated; cleanup execution not started`

## Decision

1. Add read-only cleanup preview artifact and APIs:
   - `GET /data-lifecycle/meter-storage/cleanup/preview`
   - `POST /data-lifecycle/meter-storage/cleanup/preview/rebuild`
2. Keep cleanup blocked in RES-009:
   - `mode=preview_only`
   - `cleanup_allowed=false`
3. Project cleanup preview summary to:
   - `/data-lifecycle/status.meter_storage_v2.cleanup`

## Safety Boundary

- no execute/delete/move/compress/truncate cleanup endpoint
- no legacy meter file mutation
- no fallback shutdown
- no UI change
- no Codex live validation expansion

## Preconditions Used by Preview

- parity status and `critical_mismatch_count`
- read-path flags for request meter/request_evidence/metrics/status
- legacy fallback enabled
- backup/export required and operator approval required (thus blocked in this line)

## Consequences

- Positive: future cleanup planning becomes auditable and quantifiable.
- Positive: current production safety and fallback posture remain unchanged.
- Negative: storage reclamation remains deferred by design.
