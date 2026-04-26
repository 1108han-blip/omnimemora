# OmniMemora RES-020/021/022 Closeout (2026-04-26)

## Fixed Conclusion

`cleanup gate/transaction preview/rollback drill introduced; cleanup execution not started; delete/move/compress/truncate execution not started; RES-023 remains explicit approval required`

## Scope

This closeout covers RES-020 to RES-022 only.

- RES-020: cleanup execution gate contract and API/status/health projection
- RES-021: cleanup transaction preview contract and API/status projection
- RES-022: rollback/readback drill contract and API/status projection

Out of scope:

- cleanup execute/delete/move/compress/truncate execution
- production read-path switch
- any RES-023 pilot execution

## Repo Reality

Implemented files:

- `5_connectors/adapter/data_lifecycle/meter_cleanup_execution_gate.py`
- `5_connectors/adapter/data_lifecycle/meter_cleanup_transaction_preview.py`
- `5_connectors/adapter/data_lifecycle/meter_cleanup_rollback_drill.py`
- `5_connectors/adapter/data_lifecycle_api.py`
- `5_connectors/adapter/data_lifecycle/meter_storage_v2.py`
- `5_connectors/adapter/data_lifecycle/health.py`
- `5_connectors/adapter/data_lifecycle/policy.py`
- tests under `5_connectors/adapter/tests/` for gate/transaction/rollback and API surface

Key contract confirmations:

- no `/data-lifecycle/meter-storage/cleanup/execute|delete|move|compress|truncate` endpoint
- cleanup gate remains default deny (`cleanup_allowed=false`)
- transaction preview remains preview-only (`execution_allowed=false`)
- rollback drill remains validation-only and staging-only (`production_restore_started=false`, `cleanup_started=false`)

RES-020 high-priority adjustment:

- running revision is no longer env-only; gate now resolves in order:
  1. env (`OMNIMEMORA_RUNNING_REVISION` / `OMNIMEMORA_ADAPTER_RUNNING_REVISION`)
  2. promotion marker (`~/.omnimemora/service/current/.omnimemora_promotion_state.json`, or `OMNIMEMORA_PROMOTION_STATE_FILE` override)
- when both are unavailable, `running_revision_missing` is recorded as expected block (not interpreted as execution failure)

## Repo Gate Evidence

- `python3 -m pytest -q ...` (cleanup + backup export + API + governance/safety invariants): `183 passed`
- `python3 -m py_compile` on touched adapter/data_lifecycle + tests: passed
- `git diff --check`: passed

## Running Reality (adapter+ui promotion)

Running alignment repair note:

- prior marker was `repo_revision=b666c1e`, which did not prove that RES-020/021/022 committed HEAD had been promoted
- this repair batch re-promoted from clean committed HEAD and revalidated all running checks against that aligned marker

Promotion (alignment repair):

- command: `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- promotion log: `tools/verification/logs/promotion_20260426_123622.log`
- deployed marker repo revision: `845d9a5` (matches committed HEAD used for this revalidation)

Running validation chain:

1. `POST /data-lifecycle/meter-storage/cleanup/preview/rebuild`
   - `status=blocked`
   - `cleanup_allowed=false`
2. `POST /data-lifecycle/meter-storage/backup-export/restore-readback/rebuild`
   - `status=passed`
   - `production_restore_started=false`
   - `cleanup_started=false`
3. `POST /data-lifecycle/meter-storage/cleanup/gate/rebuild`
   - `cleanup_allowed=false`
   - `rollback_required=true`
4. `POST /data-lifecycle/meter-storage/cleanup/transaction-preview/rebuild`
   - `status=blocked`
   - `execution_allowed=false`
   - item operations remain within `retain|eligible_for_future_cleanup|blocked`
5. `POST /data-lifecycle/meter-storage/cleanup/rollback-drill/rebuild`
   - `status=passed`
   - `staging_restore_readable=true`
   - `checksum_match=true`
   - `source_retained=true`
   - `production_restore_started=false`
   - `cleanup_started=false`
6. `GET /data-lifecycle/meter-storage/parity`
   - `critical_mismatch_count=0`
7. `GET /data-lifecycle/status`
   - `meter_storage_v2.cleanup.execution_gate_allowed=false`
   - `meter_storage_v2.cleanup.transaction_execution_allowed=false`
   - `meter_storage_v2.cleanup.rollback_required=true`
8. forbidden cleanup execution endpoints remain absent
   - `/data-lifecycle/meter-storage/cleanup/execute|delete|move|compress|truncate` -> `404`
9. smoke (real request id `b25a0530854d`)
   - `GET /requests/{id}/meter` -> 200
   - `GET /debug/request_evidence?request_id={id}` -> 200
   - `GET /metrics/summary` -> 200
   - `GET /agents/control` -> 200

Status/health projection checks:

- `/data-lifecycle/status.meter_storage_v2.cleanup` shows:
  - `execution_gate_status=blocked`
  - `execution_gate_allowed=false`
  - `transaction_preview_status=blocked`
  - `transaction_execution_allowed=false`
  - `rollback_drill_status=passed`
  - `rollback_required=true`

## RES-023 Boundary

RES-023 remains frozen.

- Any single-file reversible cleanup pilot still requires explicit operator approval.
- This batch does not grant approval and does not start cleanup execution.

## Final Running Conclusion

`RES-020/021/022 running reality revalidated against committed HEAD; cleanup execution not started`
