---
doc_id: ADR-RES-017
title: Single Backup Export Copy Pilot
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-26
depends_on:
  - ADR-RES-016
  - ADR-RES-016A
supersedes: []
last_verified_commit: "583be04"
---

# ADR-RES-017: Single Backup Export Copy Pilot

## Summary

Introduce the first real backup export pilot with strict single-file copy-only scope.

Fixed conclusion:

- `single backup export copy pilot completed; source retained; cleanup execution not started`

## Decision

1. Add copy-only pilot executor:
   - `schema_version=res-legacy-meter-backup-export-copy-pilot-v1`
   - `mode=single_copy_pilot_only`
2. Pilot behavior constraints:
   - copy only one file from backup export package manifest
   - default selects smallest bytes legacy meter candidate in manifest
   - checksum verify source == copied
   - source retained
3. Gate handling:
   - requires RES-014 execution gate artifact
   - allows pilot-only override for missing operator approval when explicitly enabled
   - does not enable full export
4. API surface:
   - `POST /data-lifecycle/meter-storage/backup-export/copy-pilot/run-one`
   - `GET /data-lifecycle/meter-storage/backup-export/copy-pilot/latest`

## Safety Boundary

- no full export/batch export
- no cleanup execution
- no delete/move/compress/truncate
- no read path switch
- no source mutation

## Consequences

- Positive: validates real copy path with minimal risk and deterministic evidence.
- Positive: preserves strict non-destructive boundary for legacy meter source.
- Negative: full export and cleanup remain deferred to later lines.
