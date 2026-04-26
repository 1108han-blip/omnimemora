# OmniMemora RES-018A Restore/Readback Hash Contract Hardening (2026-04-26)

## Fixed Conclusion

`restore/readback hash contract hardened; backup export restore/readback validation still passed; cleanup execution not started`

## Scope

RES-018A is a safety hardening follow-up to RES-018.

- switched on: stricter restore/readback hash contract
- not switched on: production restore
- not switched on: cleanup execution
- not switched on: delete/move/compress/truncate/source mutation

## Repository Reality

Commit:

- `caa01f3 test(dlp): harden restore readback hash contract`

Changed files:

- `5_connectors/adapter/data_lifecycle/meter_backup_export_restore_readback.py`
- `5_connectors/adapter/tests/test_meter_backup_export_restore_readback.py`

Behavior change:

- `source_sha256` and `copied_sha256` recorded by the RES-017 copy-pilot record are now required for a passed restore/readback result.
- If either recorded hash is missing, restore/readback records:
  - `status=blocked`
  - `copy_pilot_hash_missing`
  - `copy_pilot_hash_mismatch`
  - `expected_hash_match=false`
- Current source/copy checksum equality alone is no longer sufficient for a passed result when recorded copy-pilot hashes are absent.

Repo validation:

- `python3 -m pytest -q 5_connectors/adapter/tests/test_meter_backup_export_restore_readback.py`
  - `6 passed`
- `python3 -m pytest -q 5_connectors/adapter/tests/test_meter_backup_export_*.py 5_connectors/adapter/tests/test_data_lifecycle_api.py -k "backup_export" 5_connectors/adapter/tests/test_meter_storage_parity.py 5_connectors/adapter/tests/test_res_storage_governance_invariants.py`
  - `71 passed, 76 deselected`
- `python3 -m py_compile ...`
  - passed
- `git diff --check`
  - passed

## Running Reality

Promotion:

- command: `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- repo revision: `caa01f3`
- restart truth: `changed`
- log: `tools/verification/logs/promotion_20260426_111139.log`

Running restore/readback revalidation:

- `POST /data-lifecycle/meter-storage/backup-export/restore-readback/rebuild` -> `200`
  - `status=passed`
  - `mode=restore_readback_validation_only`
  - `source_retained=true`
  - `backup_copy_readable=true`
  - `checksum_match=true`
  - `expected_hash_match=true`
  - `bytes_match=true`
  - `production_restore_started=false`
  - `cleanup_started=false`
  - `blocking_reasons=[]`
- `GET /data-lifecycle/status` -> `200`
  - `restore_readback_status=passed`
  - `restore_readback_source_retained=true`
  - `restore_readback_backup_copy_readable=true`
  - `restore_readback_checksum_match=true`
  - `restore_readback_production_restore_started=false`
  - `restore_readback_cleanup_started=false`
  - `cleanup_execution_started=false`
- `GET /data-lifecycle/meter-storage/parity` -> `200`
  - `status=passed`
  - `critical_mismatch_count=0`
  - `payload_hash_mismatch_count=0`

Smoke:

- `/agents/control` -> `200`
- `/metrics/summary` -> `200`

## Boundary Confirmation

- backup export restore/readback validation remains passed
- source remains retained
- cleanup execution not started
- production restore not started
- production read path unchanged
- no delete/move/compress/truncate execution introduced
- no source mutation introduced
