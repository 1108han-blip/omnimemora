---
doc_id: ADR-0001-PRODUCT-BOUNDARY-RESET
title: Product Boundary Reset (Historical)
owner: product-team
reviewers: [arch-lead]
status: superseded
version: 2.0.0
effective_date: 2026-04-22
depends_on: []
supersedes: []
last_verified_commit: ""
---

# ADR-0001 (Historical)

## Status

This ADR is historical and superseded as an active decision surface.

Current product-boundary truth is maintained by:

- `0_blueprint/PRODUCT_DEFINITION.md`
- `9_adr/ADR-0003-interface-access-paths.md`
- `9_adr/ADR-0002-cloud-refactor.md`

## Why superseded

The original text captured an earlier transition-stage narrative and no longer matches the current local-first product boundary and cloud responsibility split.

## Current enforceable boundary

- `5173` is user control entry
- `18011` is only product data ingress when user enables routing
- `8765` is internal memory plane
- cloud is control-plane and candidate-source enhancement, not primary execution plane
