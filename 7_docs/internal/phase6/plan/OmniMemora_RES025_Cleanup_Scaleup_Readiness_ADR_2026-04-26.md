# OmniMemora RES-025 ADR - Cleanup Scale-Up Readiness Before Any Scope Expansion (2026-04-26)

## Status

Design/readiness only (pre-closeout draft).

## Decision

RES-025 adopts a strict readiness-first path:

- design and verify a read-only cleanup scale-up readiness contract
- do not start a second source move
- do not start delete/compress/truncate/batch cleanup
- keep `cleanup_scope_expansion_started=false`

Target closeout conclusion for this line:

`cleanup scale-up readiness designed; cleanup scope expansion not started`

## Context

RES-023 proved a single-file reversible quarantine pilot.
RES-024 proved a post-pilot stability window on that single-file outcome.
These outcomes validate local safety for one controlled case, but they do not prove batch or broader-scope safety.

Scale-up directly from RES-023/024 is unsafe because:

1. `n=1` success does not establish safe behavior under multiple candidates.
2. Multi-file sequencing can introduce ordering, rollback, and observability gaps not present in single-file flow.
3. Approval scope for one file is not equivalent to approval scope for scale-up.
4. Existing safety guarantees are framed as observe-only/pilot-first; direct expansion would break that governance contract.
5. Running truth still requires explicit evidence that no new source move was started outside the pilot path.

## Why This ADR Exists

This ADR prevents an implicit jump from pilot success to scale execution.
It requires a formal readiness artifact to express:

- whether scale-up is ready (`ready_for_scaleup`)
- why it is blocked (`blocking_reasons`)
- what operator action is required (`required_operator_decision`)
- what the maximum next step can be (`allowed_next_step`, `max_batch_size_recommendation`)

## Consequences

Positive:

- preserves additive, auditable governance before any cleanup-at-scale discussion
- separates design/readiness truth from execution truth
- keeps running validation bounded to product API evidence (`18011`)

Tradeoff:

- no immediate throughput gain from cleanup execution
- additional design and validation cycle required before any expansion proposal

## Non-Goals (Frozen in RES-025)

- second source move
- cleanup-at-scale execution
- delete/compress/truncate/batch cleanup
- production read-path switch related to cleanup execution

## Guardrail Statement

Until a later explicitly approved phase opens execution, RES-025 remains design/readiness only, and:

- `cleanup_scope_expansion_started=false`
- scale-up execution endpoints remain absent
- running validation must not claim expanded cleanup execution
