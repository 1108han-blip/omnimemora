---
doc_id: ADR-RES-002
title: Meter Storage V2 SQLite Mirror Introduction
owner: product-arch
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-DLP-001
  - ADR-RES-001
supersedes: []
last_verified_commit: ""
---

# ADR-RES-002: Meter Storage V2 SQLite Mirror Introduction

## Summary

Introduce `Meter Storage V2` as adapter-local SQLite mirror storage in observe-only mode.

Fixed conclusion:

- `meter storage v2 introduced`
- `legacy meter JSON retained`
- `production read path switch deferred until parity is proven`

## Decision

1. Add `meter_store_v2` SQLite mirror store with WAL enabled.
2. Keep mode fixed to `dual_write_observe_only` in this line.
3. Keep legacy `meters_index.json` and `meters_*.json` as production authority.
4. Keep request-path write semantics:
   legacy write path executes first; mirror write is best-effort and non-fatal.
5. Add parity/rebuild/status governance surfaces under DLP:
   - status
   - rebuild (non-destructive)
   - parity report
   - parity+rebuild
6. Add health projection `meter_storage_v2` to `/data-lifecycle/status`.

## Explicit Boundaries

- no legacy file delete/truncate/move/compress
- no `/requests/{id}/meter` read-path switch in this batch
- no `request_evidence` read-path switch in this batch
- no destructive meter endpoint
- no Codex live validation gate in this batch
- no user-client memory governance change

## Consequences

- Positive: meter storage coupling pressure is reduced with structured mirror data.
- Positive: parity can be continuously measured before any read-path migration.
- Negative: dual-write introduces additional write overhead.
- Negative: production read-path migration remains deferred to a later gated batch.
