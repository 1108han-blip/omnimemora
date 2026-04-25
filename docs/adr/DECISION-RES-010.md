---
doc_id: ADR-RES-010
title: Legacy Meter Backup Export Readiness Only
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

# ADR-RES-010: Legacy Meter Backup Export Preview/Readiness Only

## Summary

Add backup export readiness planning surface before any future cleanup/export execution.

Fixed conclusion:

- `legacy meter backup export readiness planned; backup export execution not started; cleanup execution not started`

## Decision

1. Add backup-export-readiness artifact and read-only APIs:
   - `GET /data-lifecycle/meter-storage/backup-export/readiness`
   - `POST /data-lifecycle/meter-storage/backup-export/readiness/rebuild`
2. Keep safety gates blocked in this line:
   - `mode=backup_export_readiness_only`
   - `backup_export_allowed=false`
   - `cleanup_allowed=false`
3. Project readiness summary to:
   - `/data-lifecycle/status.meter_storage_v2.backup_export`

## Safety Boundary

- no real export/copy/archive endpoint
- no cleanup execute/delete/move/compress/truncate endpoint
- no legacy meter file mutation
- no fallback shutdown
- no UI changes
- no Codex live validation expansion

## Consequences

- Positive: future export/cleanup lines get auditable package scope, checksum plan, and capacity estimates.
- Positive: current production safety posture unchanged.
- Negative: backup export execution remains deferred.
