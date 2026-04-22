---
doc_id: ADR-0002-CLOUD-REFACTOR
title: Cloud Responsibility Reset (Cloudflare + Railway + Local)
owner: platform-team
reviewers: [arch-lead]
status: active
version: 2.0.0
effective_date: 2026-04-22
depends_on: [ADR-0003-INTERFACE-ACCESS-PATHS]
supersedes: [ADR-0002-CLOUD-REFACTOR@1.0.0]
last_verified_commit: ""
---

# ADR-0002: Cloud Responsibility Reset

## Context

Cloud-side narratives had drifted into deprecated assumptions (cloud-hosted memory plane, cloud compile path, and legacy naming exposed as current product vocabulary).
Current product truth is local-first execution:

- `5173` = user control entry
- `18011` = only product data ingress when user routing is enabled
- `8765` = internal memory plane

Cloud is optional enhancement, not execution truth.

## Decision

### 1. Fixed Responsibility Split

Cloudflare (`doloclaw.com`):

- only external domain entry
- control-plane API/auth/tenant/billing/policy access
- candidate fetch entry

Cloudflare must not:

- host primary memory plane
- host primary compile engine
- expose cloud as `/memory/*` product truth

Railway:

- recommendation candidate snapshot/state storage
- lightweight async aggregation/background jobs
- low-cost persistence for candidate pipeline support

Railway must not:

- serve primary `/memory/*`
- become main compile path

Local (`18011` + `8765`):

- execution truth (active/fallback)
- local promotion decides active policy effect
- offline availability remains unchanged

### 2. Candidate Policy Rule

- remote cloud provides candidate only
- local active is authoritative
- remote candidate cannot overwrite local active directly

### 3. Naming Rule

Current product entry surfaces must not expose legacy naming as current nouns.
Compatibility code may exist internally, but operator/customer-facing defaults and active docs must use current product naming.

## Implementation Contract (Batch 1)

Batch 1 scope is boundary reset + cleanup + skeleton:

- remove deprecated cloud prototype surfaces from active repo path
- publish new cloud split spec
- add minimal candidate-source skeleton:
  - Cloudflare candidate pointer fetch
  - Railway candidate snapshot fetch
  - local loader integration as non-blocking optional candidate source

Out of scope for Batch 1:

- full cloud candidate management backend
- production synchronization workflow
- cloud-side full admin console rebuild

## Consequences

Positive:

- cloud role becomes explicit and enforceable
- local-first execution truth is preserved
- future candidate-source implementation can proceed without role ambiguity

Negative:

- historical docs/legacy compatibility areas still require a later dedicated purge batch

## Validation Targets

Repository reality:

- deprecated cloud prototype directories removed
- active docs no longer describe cloud memory plane as current fact
- current-facing naming no longer defaults to legacy cloud-era terms

Running reality target (non-regression):

- `18011 / 8765 / 5173` behavior unchanged by cloud cleanup

## Follow-up

Next batch: `legacy compatibility purge` for deep historical branches and compatibility internals outside active product entry surfaces.
