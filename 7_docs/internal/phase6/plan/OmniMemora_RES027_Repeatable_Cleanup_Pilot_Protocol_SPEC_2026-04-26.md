# OmniMemora RES-027 SPEC - Repeatable Cleanup Pilot Protocol (Proposal-Only) (2026-04-26)

## Fixed Scope

RES-027 only designs a repeatable single-file pilot protocol and second-file proposal artifact.

Fixed boundary:

- `repeatable cleanup pilot protocol designed; second-file pilot execution not started; cleanup scope expansion not started`
- no second source move
- no delete/compress/truncate/batch cleanup
- no production read-path switch

## Protocol Artifact Contract

Artifact name:

- `repeatable_pilot_protocol`

Schema and mode:

- `schema_version=res-repeatable-cleanup-pilot-protocol-v1`
- `mode=proposal_only`

Required output fields:

- `required_per_pilot_checks`
- `one_time_mechanism_checks`
- `batch_summary_checks`
- `operator_approval_requirements`
- `stop_conditions`
- `allowed_next_step`

Required defaults in RES-027:

- `second_file_pilot_allowed=false`
- `execution_started=false`
- `cleanup_scope_expansion_started=false`

## Second-File Proposal Artifact Contract

Artifact name:

- `second_file_pilot_proposal`

Schema and mode:

- `schema_version=res-second-file-cleanup-pilot-proposal-v1`
- `mode=proposal_only`

Required behavior:

- select candidate only (no move)
- candidate source must come from cleanup preview plus transaction preview
- exclude the RES-023 quarantined source from candidate set
- include candidate risk and estimated reclaim bytes
- include backup/export references and rollback references
- include approval hash

Required defaults in RES-027:

- `second_file_pilot_allowed=false`
- `execution_started=false`
- `cleanup_scope_expansion_started=false`

## API and Status Surface

Read-only API only:

- `GET /data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol`
- `POST /data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/rebuild`
- `GET /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal`
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/rebuild`

Status projection:

- `meter_storage_v2.cleanup.repeatable_pilot_protocol_status`
- `meter_storage_v2.cleanup.second_file_pilot_proposal_status`
- `meter_storage_v2.cleanup.second_file_pilot_allowed=false`

## Blocking Rules

Proposal must remain blocked when any required running check is missing or failed:

- parity clean
- stability passed
- restore/readback passed
- rollback drill passed
- scaleup readiness blocked-as-expected

## Prohibitions

RES-027 must not add:

- `/execute` endpoint for second-file pilot
- `/delete`, `/move`, `/compress`, `/truncate`, `/batch` endpoints
- hidden side-effects that move or mutate legacy source files

## Next-Line Gate

Execution is not in RES-027.
Any second-file execution can only be considered in a separate RES-028 line with explicit operator approval.
