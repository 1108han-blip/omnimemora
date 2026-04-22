---
doc_id: ADR-0007-BACKEND-ABSTRACTION
title: Backend Abstraction Layer (Historical Compatibility Record)
owner: platform-team
reviewers: [arch-lead]
status: superseded
version: 2.0.0
effective_date: 2026-04-22
depends_on: [ADR-0003-INTERFACE-ACCESS-PATHS]
supersedes: []
last_verified_commit: ""
---

# ADR-0007 (Historical Compatibility Record)

## Status

This ADR is retained as historical implementation context and is not an active product-surface decision document.

## Retained conclusion

Adapter backend abstraction remains valid as an internal engineering pattern:

- interface-based backend access
- factory selection
- compatibility backend isolation from product entry surfaces

## Current active boundary

Current product entry and cloud-role decisions are governed by:

- `9_adr/ADR-0003-interface-access-paths.md`
- `9_adr/ADR-0002-cloud-refactor.md`
- `0_blueprint/PRODUCT_DEFINITION.md`

## Compatibility note

Legacy compatibility internals may still exist, but they must not define current operator/customer-facing product truth.
