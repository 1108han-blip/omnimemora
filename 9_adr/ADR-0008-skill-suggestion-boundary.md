# ADR-0008 Skill Suggestion Boundary

- Status: Accepted
- Date: 2026-04-22

## Context

OmniMemora has completed architecture governance for `18011` (product path) and `8765` (internal runtime/memory plane).
Skill Suggestion is needed as advisory assistance, but must not become an execution/control surface.

## Decision

Skill Suggestion is a pure-logic advisory module under `4_core/logic/skill_suggestion`.

Boundary constraints:

- advisory-only
- non-executing
- non-installing
- non-routing
- no plugin/skill download
- no transparent-forwarding mutation
- no direct UI logic
- Batch 1 keeps suggestions in sidecar metadata (`skill_suggestions`) only
- Batch 1 never injects suggestions into `packed_context`

Integration constraints:

- `engine.optimize_context()` may produce `skill_suggestions` for `decision` / `continuation`
- `implementation` returns empty suggestions
- adapter only forwards suggestions as compile metadata sidecar
- product entry remains `18011`; `8765` remains internal runtime/memory plane

## Consequences

Positive:

- suggestion capability can evolve without touching prompt mainline behavior
- strict boundary prevents execution/control side effects

Negative:

- Batch 1 recommendation quality is intentionally limited (rule-based, static catalog)

Follow-up:

- UI presentation and dynamic catalog discovery are separate batches
