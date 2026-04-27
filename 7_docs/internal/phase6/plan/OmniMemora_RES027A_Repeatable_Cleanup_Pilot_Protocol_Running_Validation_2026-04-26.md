# OmniMemora RES-027A Repeatable Cleanup Pilot Protocol Running Validation (2026-04-26)

## Fixed Conclusion

`repeatable cleanup pilot protocol running-validated; second-file pilot execution not started; cleanup scope expansion not started`

## Scope

RES-027A is running alignment and read-only validation only.

Included:
- promotion `adapter+ui` to align running marker with RES-027 committed HEAD
- read-only rebuild/read through `18011` product interfaces for repeatable protocol and second-file proposal
- read-only status/safety/smoke validation

Explicitly excluded:
- code change
- API expansion
- second-file source move execution
- delete/compress/truncate/batch cleanup

## Promotion Alignment Record

Validation date: 2026-04-27

Target HEAD:
- `repo_revision=8e0c722`

Promotion runs:
1. `promotion_20260427_125459.log`
   - result: `promotion_failed`
   - reason: adapter `[API reality]` failed
2. `promotion_20260427_125519.log`
   - result: `promotion_failed`
   - reason: adapter `[API reality]` failed
3. `promotion_20260427_125538.log`
   - result: `running_reality_promoted`

Marker after successful run:
- `~/.omnimemora/service/current/.omnimemora_promotion_state.json`
- `repo_revision=8e0c722` (matches RES-027 HEAD)
- `final_status=running_reality_promoted`
- `log_file=tools/verification/logs/promotion_20260427_125538.log`

## 18011 Running Evidence

### Repeatable protocol rebuild/read

- `POST /data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/rebuild` -> `200`
  - response schema: `res-repeatable-cleanup-pilot-protocol-rebuild-v1`
  - artifact schema: `res-repeatable-cleanup-pilot-protocol-v1`
  - mode: `proposal_only`
  - status: `blocked`
  - `second_file_pilot_allowed=false`
  - `execution_started=false`
  - `cleanup_scope_expansion_started=false`

- `GET /data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol` -> `200`
  - schema: `res-repeatable-cleanup-pilot-protocol-v1`
  - mode: `proposal_only`
  - status: `blocked`
  - `second_file_pilot_allowed=false`
  - `execution_started=false`
  - `cleanup_scope_expansion_started=false`

### Second-file proposal rebuild/read

- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/rebuild` -> `200`
  - response schema: `res-second-file-cleanup-pilot-proposal-rebuild-v1`
  - artifact schema: `res-second-file-cleanup-pilot-proposal-v1`
  - mode: `proposal_only`
  - status: `blocked`
  - `second_file_pilot_allowed=false`
  - `execution_started=false`
  - `cleanup_scope_expansion_started=false`

- `GET /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal` -> `200`
  - schema: `res-second-file-cleanup-pilot-proposal-v1`
  - mode: `proposal_only`
  - status: `blocked`
  - `second_file_pilot_allowed=false`
  - `execution_started=false`
  - `cleanup_scope_expansion_started=false`

### Status projection consistency

- `GET /data-lifecycle/status` -> `200`
- `meter_storage_v2.cleanup.repeatable_pilot_protocol_status=blocked`
- `meter_storage_v2.cleanup.second_file_pilot_proposal_status=blocked`
- `meter_storage_v2.cleanup.second_file_pilot_allowed=false`

Projection matches protocol/proposal artifact states (`blocked`, proposal-only, no execution).

## Pilot / Safety / Readability Checks

Pilot latest unchanged:
- `GET /data-lifecycle/meter-storage/cleanup/pilot/latest` -> `200`
- `schema_version=res-legacy-meter-cleanup-pilot-record-v1`
- `pilot_id=aff9611a29f74657`
- `source_move_executed=true`
- `delete_executed=false`
- `compress_executed=false`
- `truncate_executed=false`
- `batch_cleanup_executed=false`
- `original_path=/Users/sc/.omnimemora/service/current/5_connectors/data/meters_phase2-meter-dir.json`

Forbidden endpoints (all `404`):
- `/cleanup/repeatable-pilot-protocol/{execute|delete|move|compress|truncate|batch}`
- `/cleanup/second-file-pilot/proposal/{execute|delete|move|compress|truncate|batch}`

Readability (all `200`):
- `/data-lifecycle/meter-storage/parity` -> `status=degraded` (readable, no execution opened)
- `/data-lifecycle/meter-storage/cleanup/stability-window` -> `status=passed`
- `/data-lifecycle/meter-storage/backup-export/restore-readback` -> `status=passed`
- `/data-lifecycle/meter-storage/cleanup/rollback-drill` -> `status=passed`
- `/data-lifecycle/meter-storage/cleanup/scaleup-readiness` -> `status=blocked`

Smoke endpoints (all `200`, request_id=`b25a0530854d`):
- `/requests/{id}/meter`
- `/debug/request_evidence?request_id={id}`
- `/metrics/summary`
- `/agents/control`

## Final Boundary Check

- second-file pilot execution not started
- cleanup scope expansion not started
- no execute/delete/move/compress/truncate/batch endpoint introduced in running surface
- RES-028 not opened or authorized by RES-027A
