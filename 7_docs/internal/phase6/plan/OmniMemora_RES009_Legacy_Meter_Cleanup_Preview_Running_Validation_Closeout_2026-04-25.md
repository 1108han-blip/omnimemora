# OmniMemora RES-009 Legacy Meter Cleanup Preview Running Validation Closeout (2026-04-25)

## Fixed Conclusion

`legacy meter cleanup preview generated; cleanup execution not started`

## Scope

RES-009 preview-only:

- switched on: cleanup preview artifact + read-only preview APIs
- not switched on: cleanup execution/delete/move/compress/truncate

## Repo Reality

Implemented:

1. `data_lifecycle/meter_cleanup_preview.py`
   - preview schema: `res-legacy-meter-cleanup-preview-v1`
   - mode: `preview_only`
   - computes:
     - `would_cleanup_files`
     - `would_retain_files`
     - `estimated_reclaim_bytes`
     - `blocking_reasons`
   - fixed safety:
     - `cleanup_allowed=false`
     - `backup_export_required=true`
     - `operator_approval_required=true`
2. `data_lifecycle_api.py`
   - `GET /data-lifecycle/meter-storage/cleanup/preview`
   - `POST /data-lifecycle/meter-storage/cleanup/preview/rebuild`
3. `data_lifecycle/meter_storage_v2.py`
   - status projection:
     - `/data-lifecycle/status.meter_storage_v2.cleanup`
     - fields: `status/mode/cleanup_allowed/candidate_file_count/estimated_reclaim_bytes/blocking_reasons_count`
4. tests:
   - new preview module tests (`test_meter_cleanup_preview.py`)
   - API tests for missing/rebuild and forbidden cleanup execution endpoints
   - safety invariants and governance invariants updated to allow preview-only endpoints while still forbidding execute/delete/move/compress/truncate paths

## Running Reality

Date:

- 2026-04-25

Promotion:

- `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- adapter restart truth: `changed`
- running revision: `d8e300c`
- log: `tools/verification/logs/promotion_20260425_214736.log`

Validation:

1. `POST /data-lifecycle/meter-storage/cleanup/preview/rebuild`
   - schema: `res-legacy-meter-cleanup-preview-rebuild-v1`
2. `GET /data-lifecycle/meter-storage/cleanup/preview`
   - schema: `res-legacy-meter-cleanup-preview-v1`
   - `mode=preview_only`
   - `cleanup_allowed=false`
   - `backup_export_required=true`
   - `operator_approval_required=true`
   - `estimated_reclaim_bytes=51034839`
3. `GET /data-lifecycle/status`
   - `meter_storage_v2.cleanup.mode=preview_only`
   - `meter_storage_v2.cleanup.cleanup_allowed=false`
   - `meter_storage_v2.cleanup.candidate_file_count=31`
   - `meter_storage_v2.cleanup.estimated_reclaim_bytes=51034839`
   - `meter_storage_v2.cleanup.blocking_reasons_count=2`
4. `GET /data-lifecycle/meter-storage/parity`
   - `critical_mismatch_count=0`
5. legacy meter files mutation check
   - `meters_index.json` + `meters_*.json` fingerprint (sha256 + mtime_ns) before/after preview rebuild: unchanged
6. smoke:
   - `/requests/req-9d93e44e/meter` -> `200`
   - `/debug/request_evidence?request_id=req-9d93e44e` -> `200`
   - `/metrics/summary` -> `200`
   - `/agents/control` -> `200`

## Boundary Confirmation

- cleanup execution not started
- no delete/move/compress/truncate endpoint introduced
- no legacy meter file mutation by preview rebuild
- legacy fallback remains enabled
- no UI changes
- no Codex live validation expansion
