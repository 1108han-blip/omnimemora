---
doc_id: SPEC-LEGACY-METER-CLEANUP-READINESS-008
title: Legacy Meter Cleanup Readiness and Gate Contract
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

# SPEC-LEGACY-METER-CLEANUP-READINESS-008

## Scope

This spec defines readiness design only for future legacy meter cleanup.

This spec does not authorize cleanup execution.

## Current Baseline

- `cleanup_eligibility=readiness_only`
- sqlite-first read modes enabled for request meter, request_evidence, metrics residual, status read model
- legacy fallback still enabled

## Future Gate Preconditions

Before any cleanup execution proposal can be opened:

- parity report status = `passed`
- parity report `critical_mismatch_count=0`
- read-path switches all enabled
- explicit operator approval required
- backup/export required

## Safety Contract

In this design line:

- `cleanup_allowed=false`
- `mode=readiness_design_only`
- delete/move/compress/truncate execution forbidden

## Rollback Position

- rollback path remains available by keeping legacy meter files and legacy fallback intact.
- fallback removal is not required in this line.

## Non-Goals

- no API endpoint changes
- no data file mutation
- no destructive cleanup execution
