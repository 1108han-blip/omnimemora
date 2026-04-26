---
doc_id: ADR-RES-018
title: Backup Export Restore/Readback Validation
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-26
depends_on:
  - ADR-RES-017
supersedes: []
last_verified_commit: "2d53fd2"
---

# ADR-RES-018: Backup Export Restore/Readback Validation

## Summary

Record validation-only restore/readback for the RES-017 single backup export copy pilot.

Fixed conclusion:

- `backup export restore/readback validation passed; source retained; cleanup execution not started`

## Decision

1. Treat RES-018 as validation-only:
   - validates that the backup export copy can be read back
   - validates checksum/lineage linkage back to the retained source
   - records restore/readback evidence without changing production behavior
2. Do not authorize production restore:
   - no restore-to-production
   - no overwrite of production meter state
   - no promotion of backup copy into the active source location
3. Do not switch any read path:
   - no production read-path switch
   - no fallback/readthrough activation as product truth
   - no change to legacy/source authority semantics
4. Keep cleanup blocked:
   - cleanup execution not started
   - no delete/move/compress/truncate
   - no source mutation

## Safety Boundary

- validation-only
- source retained
- no production restore
- no production read-path switch
- no cleanup execution
- no delete/move/compress/truncate
- no source move

## Consequences

- Positive: establishes that the copied backup export artifact is restorable/readable as evidence before any cleanup line.
- Positive: keeps the legacy source authoritative and retained after validation.
- Negative: cleanup, deletion, movement, compression, truncation, and production restore remain deferred to later explicit decisions.
