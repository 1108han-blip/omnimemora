---
doc_id: PLAN-PHASE3-WORKING-PRINCIPLES
title: Phase 3 Working Principles
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-09
depends_on: [ADR-0001-PRODUCT-BOUNDARY]
supersedes: []
last_verified_commit: ""
---

# WORKING_PRINCIPLES_README

## Purpose

This file records the execution principles used for experiment data operations in this phase.

## Core Principles

1. Safety first
- No destructive actions on active runtime/probe processes unless explicitly requested.
- Prefer read-only verification before any write action.

2. Reproducibility
- Every result must be traceable to archived raw data + checksum manifest.
- Commands and outputs should be deterministic and scriptable.

3. Auditability
- Keep immutable timestamped archives.
- Preserve metadata (time, timezone, source path, run label).

4. Separation of concerns
- Raw evidence, operational scripts, and paper exports are stored separately.
- Raw files remain untouched; analysis uses anonymized derived exports.

5. Minimum necessary change
- Implement smallest possible code/document changes to unblock target outcomes.
- Avoid unrelated refactors during critical validation windows.

6. Clear failure semantics
- Verification and heartbeat scripts use non-zero exit on failure/stale states.
- Any failed integrity/freshness check blocks acceptance sign-off.

## Operator Commitments

- I will not rewrite historical raw meter data.
- I will use checksum verification before reporting key metrics.
- I will keep sensitive query/user fields anonymized in publication artifacts.

## Current Tooling Location

- `tools/verification/data_governance/`
- `7_docs/internal/phase3/EXPERIMENT_DATA_GOVERNANCE_SOP.md`

