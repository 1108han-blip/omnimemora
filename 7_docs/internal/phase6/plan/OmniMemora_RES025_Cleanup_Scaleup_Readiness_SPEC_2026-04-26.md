# OmniMemora RES-025 SPEC - Cleanup Scale-Up Readiness (Read-Only) (2026-04-26)

## Fixed Scope

RES-025 is limited to cleanup scale-up readiness design and read-only readiness surfaces.

Fixed boundary:

- `cleanup scope expansion not started`
- no second source move
- no cleanup execute/delete/move/compress/truncate/batch endpoint

## Readiness Artifact Contract

Artifact name:

- `cleanup_scaleup_readiness`

Schema:

- `schema_version=res-legacy-meter-cleanup-scaleup-readiness-v1`
- `mode=scaleup_readiness_only`

Required fields:

- `ready_for_scaleup=false` (default and required in RES-025)
- `cleanup_scope_expansion_started=false` (required)
- `allowed_next_step`
- `blocking_reasons`
- `required_operator_decision`
- `candidate_count`
- `max_batch_size_recommendation`
- `rollback_requirements`

Recommended summary fields:

- `status` (`blocked` or `operator_decision_required`)
- `generated_at`
- `input_artifact_hashes`

## Allowed Input Sources (Read-Only)

Readiness rebuild may read from:

- cleanup preview
- transaction preview
- quarantine pilot latest
- stability-window
- parity
- restore/readback
- rollback drill
- backup export artifacts

No other source is required for RES-025 design readiness.

## Output Constraints

Allowed output:

- readiness/report artifact only

Forbidden output:

- moving any legacy meter file
- deleting any legacy meter file
- compress/truncate operations
- batch cleanup side effects

## API/Status Surface

Read-only endpoints:

- `GET /data-lifecycle/meter-storage/cleanup/scaleup-readiness`
- `POST /data-lifecycle/meter-storage/cleanup/scaleup-readiness/rebuild`

Status projection:

- `/data-lifecycle/status.meter_storage_v2.cleanup.scaleup_readiness_status`
- `/data-lifecycle/status.meter_storage_v2.cleanup.scaleup_ready`
- `/data-lifecycle/status.meter_storage_v2.cleanup.cleanup_scope_expansion_started=false`

## Entry Criteria (Readiness Evaluation)

Scale-up readiness rebuild must block when any of the following is true:

1. stability-window missing or not passed
2. parity mismatch (`critical_mismatch_count > 0`)
3. restore/readback not passed
4. rollback drill not passed
5. backup export artifacts missing/invalid

Even when all checks pass, RES-025 keeps execution blocked by policy:

- `ready_for_scaleup` remains `false` or requires explicit operator decision
- no automatic transition to scale-up execution

## Prohibitions

RES-025 must not introduce:

- `/execute` endpoint for cleanup scale-up
- `/delete`, `/move`, `/compress`, `/truncate`, `/batch` cleanup endpoint
- any hidden side-effect route that mutates source files

## Approval Contract

Readiness report must include explicit operator gating metadata:

- `required_operator_decision` (non-empty when expansion is considered)
- decision scope must include candidate boundary and max batch size
- absence of decision keeps readiness blocked

## Rollback Requirements

Readiness output must state rollback requirements before any future expansion can be proposed:

- rollback artifact/record availability
- readback verification requirement
- checksum/verifiability requirement
- operator rollback drill requirement

## Allowed Next Step Semantics

`allowed_next_step` is descriptive and constrained in RES-025:

- allowed values may describe only readiness-related follow-up
- it must not authorize cleanup execution
- it must preserve `cleanup_scope_expansion_started=false`

## Acceptance for RES-025 (Design/Readiness Only)

RES-025 readiness design is acceptable when:

1. artifact contract and API/status contract are defined as read-only
2. blocking criteria and prohibitions are explicit
3. approval and rollback requirements are explicit
4. wording remains: `cleanup scope expansion not started`
