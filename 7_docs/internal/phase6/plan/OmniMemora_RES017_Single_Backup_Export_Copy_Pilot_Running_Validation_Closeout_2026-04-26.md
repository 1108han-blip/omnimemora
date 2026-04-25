# OmniMemora RES-017 Single Backup Export Copy Pilot Running Validation Closeout (2026-04-26)

## Fixed Conclusion

`single backup export copy pilot completed; source retained; cleanup execution not started`

## Scope

RES-017 single copy-only pilot:

- switched on: one-file copy-only backup export pilot executor + API + status projection
- not switched on: full backup export execution
- not switched on: cleanup execution
- not switched on: truncate/delete/move/compress execution
- not switched on: production read-path switch

## Repo Reality

Implemented:

1. `data_lifecycle/meter_backup_export_copy_pilot.py`
   - schema: `res-legacy-meter-backup-export-copy-pilot-v1`
   - mode: `single_copy_pilot_only`
   - deterministic candidate selection from RES-013 manifest (smallest bytes)
   - deterministic non-overwrite target naming under pilot root
   - source/target checksum verification
   - fixed invariants:
     - `source_retained=true`
     - `cleanup_started=false`
     - `read_path_unchanged=true`
   - gate requirement: RES-014 gate required; optional single-pilot override records `pilot_scope_override=true`
2. `data_lifecycle/policy.py`
   - adds copy-pilot root/record/override policy fields and env overrides
3. `data_lifecycle_api.py`
   - `POST /data-lifecycle/meter-storage/backup-export/copy-pilot/run-one`
   - `GET /data-lifecycle/meter-storage/backup-export/copy-pilot/latest`
   - no `/execute`, `/full-export`, `/cleanup`, `/delete`, `/move`, `/compress`, `/truncate` endpoint added
4. `data_lifecycle/meter_storage_v2.py`
   - `/data-lifecycle/status.meter_storage_v2.backup_export` adds:
     - `copy_pilot_status`
     - `copy_pilot_source_retained`
     - `copy_pilot_checksum_match`
     - `copy_pilot_cleanup_started=false`
     - `copy_pilot_read_path_unchanged=true`
5. tests:
   - `test_meter_backup_export_copy_pilot.py` added
   - API/status/governance invariant tests extended

## Running Reality

Date:

- 2026-04-26

Promotion:

- `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- adapter restart truth: `changed`
- running revision at promotion time: `583be04`
- log: `tools/verification/logs/promotion_20260426_024042.log`

Validation:

1. Governance rebuild chain:
   - cleanup preview/readiness/plan/package-manifest/approval-template/execution-gate/execution-proposal rebuild all `200`
2. Copy pilot execution:
   - first `POST /data-lifecycle/meter-storage/backup-export/copy-pilot/run-one` -> `status=success`
   - second `POST /data-lifecycle/meter-storage/backup-export/copy-pilot/run-one` -> `status=already_copied`
   - `GET /data-lifecycle/meter-storage/backup-export/copy-pilot/latest` confirms:
     - `source_retained=true`
     - `checksum_match=true`
     - `cleanup_started=false`
     - `read_path_unchanged=true`
3. Status projection:
   - `GET /data-lifecycle/status` -> `200`
   - `meter_storage_v2.backup_export.copy_pilot_status=already_copied`
   - `meter_storage_v2.backup_export.copy_pilot_source_retained=true`
   - `meter_storage_v2.backup_export.copy_pilot_checksum_match=true`
   - `meter_storage_v2.backup_export.copy_pilot_cleanup_started=false`
   - `meter_storage_v2.backup_export.copy_pilot_read_path_unchanged=true`
4. Safety checks:
   - selected legacy source file checksum unchanged before/after copy
   - selected legacy source file mtime unchanged before/after copy
   - copied target checksum equals source checksum
   - proposal remains non-executing: `execution_started=false`, `cleanup_started=false`
   - parity remains clean: `critical_mismatch_count=0`
5. Smoke:
   - `/requests/req-9d93e44e/meter` -> `200`
   - `/debug/request_evidence?request_id=req-9d93e44e` -> `200`
   - `/metrics/summary` -> `200`
   - `/agents/control` -> `200`

## Boundary Confirmation

- backup export copy pilot is single-file and copy-only
- source retained
- backup export execution not started
- cleanup execution not started
- read path unchanged
- no delete/move/compress/truncate execution introduced

## Next-Line Freeze

- RES-018 is frozen as `backup export restore/readback validation only`
- cleanup remains forbidden until restore/readback validation passes
