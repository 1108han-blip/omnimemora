---
doc_id: ADR-RES-001
title: Raw Evidence Segmentation Observe-Only Introduction
owner: product-arch
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-DLP-001
supersedes: []
last_verified_commit: ""
---

# ADR-RES-001: Raw Evidence Segmentation Observe-Only Introduction

## Summary

Introduce raw evidence segmentation for `compile_events / proxy_events / trace_events` in additive observe-only mode.

Fixed conclusion:

- `raw evidence segmentation introduced`
- `legacy source retained`
- `archive-at-scale execution still not started`

## Decision

1. Add `Raw Evidence Segments` module under DLP.
2. Enable `dual_write_observe_only`:
   legacy source JSONL remains production truth, segment write is mirror-only.
3. Segment write failure is non-fatal:
   no request-path interruption; write DLP ledger degraded record only.
4. Add manifest contract:
   `schema_version=dlp-raw-evidence-segments-manifest-v1`.
5. Rotation defaults:
   per segment `32MiB` or `6h`, env-overridable.
6. Add read-only APIs and health projection only:
   no delete/compress/move/read-path switch in this line.

## Explicit Boundaries

- no delete
- no compression
- no source evidence move
- no production read-path switch
- no Codex live validation gate in this batch
- no user-client memory governance change

## Consequences

- Positive: unbounded single-file growth starts transitioning to segmented mirror artifacts.
- Positive: retention/traceability/archive planning can consume manifest-derived candidates later.
- Negative: additional write overhead in observe-only mirror path.
- Negative: running validation and promotion evidence are still pending.
