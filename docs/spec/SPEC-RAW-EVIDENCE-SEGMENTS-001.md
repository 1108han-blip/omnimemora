---
doc_id: SPEC-RAW-EVIDENCE-SEGMENTS-001
title: Raw Evidence Segments - Observe-Only Manifested Segmentation
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-RES-001
supersedes: []
last_verified_commit: ""
---

# SPEC-RAW-EVIDENCE-SEGMENTS-001

## Scope

This spec covers additive segmentation for three raw evidence streams:

- `compile_events`
- `proxy_events`
- `trace_events`

## Mode

Default mode is `dual_write_observe_only`:

- legacy source path: keep writing, keep as production read truth
- segment path: mirror write only
- mirror write failure: non-fatal, ledger degraded record only

## Manifest Contract

Schema: `dlp-raw-evidence-segments-manifest-v1`

Each segment entry includes:

- `kind`
- `segment_id`
- `state` (`active` or `sealed`)
- `path`
- `bytes`
- `line_count`
- `sha256`
- `created_at`
- `sealed_at`
- `first_event_at`
- `last_event_at`

## Rotation Policy

- default max bytes: `32 * 1024 * 1024`
- default max age: `6 * 60 * 60` seconds
- env override:
  - `OMNIMEMORA_DLP_RAW_EVIDENCE_SEGMENT_MAX_BYTES`
  - `OMNIMEMORA_DLP_RAW_EVIDENCE_SEGMENT_MAX_AGE_SECONDS`

## API Surface

Read-only endpoints:

- `GET /data-lifecycle/raw-evidence/segments`
- `POST /data-lifecycle/raw-evidence/segments/manifest/rebuild`

Health projection:

- `/data-lifecycle/status.raw_evidence_segments`

## Non-Goals

- no request_evidence read-path migration
- no delete/compress/move endpoint
- no source evidence mutation
- no archive-at-scale execution
