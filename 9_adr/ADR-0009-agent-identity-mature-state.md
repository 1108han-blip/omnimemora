---
doc_id: ADR-0009-AGENT-IDENTITY-MATURE-STATE
title: OmniMemora Agent Identity Mature-State Contract
owner: platform-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-23
depends_on: [ADR-0003-INTERFACE-ACCESS-PATHS, ADR-0005-AGENT-IDENTITY]
supersedes: [ADR-0005-AGENT-IDENTITY]
last_verified_commit: ""
---

# ADR-0009: Agent Identity Mature-State Contract

## Context

Current implementation is accepted as a transitional state, not the final product contract.
The observed transitional behavior includes:

- canonical-first flow
- unmapped passthrough exists
- family control shell dominates operator-facing surfaces

This transitional behavior is useful for continuity, but it is not the mature-state target.

## Decision

OmniMemora formally adopts a three-layer identity contract:

- `runtime agent_id`
- `source_agent_id`
- `agent_family`

### Mature-State Role Split

- `8765` is the `agent_id` semantic baseline layer.
- `18011` is the admission + preservation layer.
- `5173` is truth projection only; it must not redefine identity semantics.

### Runtime Principal

`runtime agent_id` is the formal principal and is used for:

- scope
- memory isolation
- record attribution
- metering
- connector ownership
- layered integration

### Source Identity

`source_agent_id` is the upstream input identity and must be fully preserved for:

- integration handoff
- return path semantics
- diagnostics
- mapping traceability

`source_agent_id` must not automatically become the formal principal.

### Control Shell Identity

`agent_family` remains a control shell / aggregation view for:

- control cards
- family routing
- summary views

`agent_family` is not the formal principal.

## Admission Principles

Admission from `source_agent_id` to `runtime agent_id` must follow:

- only stable, explicit, reproducible source identities may be promoted to formal `runtime agent_id`
- inferred identities must not be written directly as formal principal
- when source identity is not admission-ready, it must stay in `source_agent_id` while principal follows explicit fallback policy

## Control Plane Principles

- family-level control shell remains valid
- instance/identity visibility must obey one unified contract
- UI/control projection must not force backend semantic rewrites

## Consequences

Positive:

- transitional-state and mature-state are explicitly separated
- future implementation can converge toward one durable contract
- projection and principal semantics are no longer conflated

Trade-off:

- transitional compatibility paths may remain temporarily, but they are no longer treated as end-state definitions

## Scope of This ADR

This ADR defines contract and direction only.
It does not define D1 truth-repair implementation details or D2 rollout mechanics.
