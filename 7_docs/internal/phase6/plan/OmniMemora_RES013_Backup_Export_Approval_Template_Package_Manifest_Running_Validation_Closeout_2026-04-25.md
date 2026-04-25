# OmniMemora RES-013 Backup Export Approval Template and Package Manifest Running Validation Closeout (2026-04-25)

## Fixed Conclusion

`backup export approval template and package manifest preview generated; backup export execution not started; cleanup execution not started`

## Scope

RES-013 approval-template and package-manifest preview only:

- switched on: approval template artifact + package manifest preview artifact + read-only APIs
- not switched on: real backup export/copy/archive execution
- not switched on: cleanup execution/delete/move/compress/truncate

## Repo Reality

Implemented:

1. `data_lifecycle/meter_backup_export_package_manifest.py`
   - schema: `res-legacy-meter-backup-export-package-manifest-v1`
   - mode: `package_manifest_preview_only`
   - derives from RES-012 plan `would_export_files`
   - records:
     - `package_id`
     - `source_plan_hash`
     - `source_readiness_hash`
     - `source_cleanup_preview_hash`
     - `total_bytes`
     - `destination_policy_snapshot`
   - fixed safety:
     - `backup_export_allowed=false`
     - `cleanup_allowed=false`
     - `execution_allowed=false`
2. `data_lifecycle/meter_backup_export_approval_template.py`
   - schema: `res-legacy-meter-backup-export-approval-template-v1`
   - mode: `approval_template_only`
   - fixed safety:
     - `approval_valid=false`
     - `backup_export_allowed=false`
     - `cleanup_allowed=false`
     - `execution_allowed=false`
   - template fields include:
     - `operator_id`
     - `approved_at`
     - `expires_at`
     - `approved_plan_hash`
     - `approved_readiness_hash`
     - `approved_cleanup_preview_hash`
     - `approved_package_manifest_hash`
     - `destination_path`
     - `reason`
3. `data_lifecycle_api.py`
   - `GET /data-lifecycle/meter-storage/backup-export/package-manifest`
   - `POST /data-lifecycle/meter-storage/backup-export/package-manifest/rebuild`
   - `GET /data-lifecycle/meter-storage/backup-export/approval-template`
   - `POST /data-lifecycle/meter-storage/backup-export/approval-template/rebuild`
4. `data_lifecycle/meter_storage_v2.py`
   - `/data-lifecycle/status.meter_storage_v2.backup_export` adds:
     - `approval_template_status`
     - `package_manifest_status`
     - `package_manifest_file_count`
     - `package_manifest_total_bytes`
     - `execution_allowed=false`
     - `cleanup_allowed=false`
5. tests:
   - `test_meter_backup_export_package_manifest.py`
   - `test_meter_backup_export_approval_template.py`
   - updated API/status/governance invariant tests

## Running Reality

Date:

- 2026-04-25

Promotion:

- `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- adapter restart truth: `changed`
- running revision: `2a25512`
- log: `tools/verification/logs/promotion_20260425_225733.log`

Validation:

1. Rebuild chain:
   - `POST /data-lifecycle/meter-storage/cleanup/preview/rebuild` -> `200`
   - `POST /data-lifecycle/meter-storage/backup-export/readiness/rebuild` -> `200`
   - `POST /data-lifecycle/meter-storage/backup-export/plan/rebuild` -> `200`
   - `POST /data-lifecycle/meter-storage/backup-export/package-manifest/rebuild` -> `200`
   - `POST /data-lifecycle/meter-storage/backup-export/approval-template/rebuild` -> `200`
2. Artifact schemas and modes:
   - `GET /data-lifecycle/meter-storage/backup-export/package-manifest`
     - `schema_version=res-legacy-meter-backup-export-package-manifest-v1`
     - `mode=package_manifest_preview_only`
   - `GET /data-lifecycle/meter-storage/backup-export/approval-template`
     - `schema_version=res-legacy-meter-backup-export-approval-template-v1`
     - `mode=approval_template_only`
   - all execution-related flags remain false
3. Status projection:
   - `GET /data-lifecycle/status` -> `200`
   - `meter_storage_v2.backup_export.approval_template_status=blocked`
   - `meter_storage_v2.backup_export.package_manifest_status=blocked`
   - `meter_storage_v2.backup_export.package_manifest_file_count=31`
   - `meter_storage_v2.backup_export.package_manifest_total_bytes=51034839`
   - `meter_storage_v2.backup_export.execution_allowed=false`
   - `meter_storage_v2.backup_export.cleanup_allowed=false`
4. Safety checks:
   - legacy meter files (`meters_index.json` + `meters_*.json`) checksum + mtime before/after rebuild unchanged
   - `GET /data-lifecycle/meter-storage/parity` -> `critical_mismatch_count=0`
5. Smoke:
   - `GET /requests/req-9d93e44e/meter` -> `200`
   - `GET /debug/request_evidence?request_id=req-9d93e44e` -> `200`
   - `GET /metrics/summary` -> `200`
   - `GET /agents/control` -> `200`

## Boundary Confirmation

- backup export execution not started
- cleanup execution not started
- no export/copy/archive execution endpoint introduced
- no delete/move/compress/truncate/cleanup execution endpoint introduced
- no legacy meter source mutation
- legacy fallback remains enabled

