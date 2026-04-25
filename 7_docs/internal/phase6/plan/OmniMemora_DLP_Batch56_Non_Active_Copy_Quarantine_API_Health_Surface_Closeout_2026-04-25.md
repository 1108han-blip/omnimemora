# OmniMemora DLP Batch 56 - Non-Active Copy Quarantine API + Health Surface Closeout (2026-04-25)

## Scope

Batch 56 exposes the Batch 55 executor through the 18011 DLP diagnostics surface and adds a lifecycle health summary.

No UI surface was added.

## Repo Reality

- Commit: `6ed2de7 feat(dlp): expose non-active copy quarantine surface`
- Updated:
  - `5_connectors/adapter/data_lifecycle_api.py`
  - `5_connectors/adapter/data_lifecycle/health.py`
  - `5_connectors/adapter/tests/test_data_lifecycle_api.py`

## API Surface

Added:

- `GET /data-lifecycle/archive/non-active-quarantine/latest`
- `POST /data-lifecycle/archive/non-active-quarantine/move-one`

Explicitly absent:

- batch cleanup endpoint
- source move endpoint
- delete endpoint
- compress endpoint
- production read-path switch endpoint

## Health Surface

`GET /data-lifecycle/status` now includes `archive_non_active_quarantine` with:

- `status`
- `mode`
- `candidate_kind`
- `candidate_path`
- `quarantine_path`
- `checksum_match`
- `source_move_executed`
- `non_active_copy_move_executed`
- `delete_compress_executed`
- `production_read_path_unchanged`
- `blocking_count`

## Validation

- `python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_archive_non_active_quarantine.py 5_connectors/adapter/tests/test_data_lifecycle_api.py`
  - `66 passed`
- `git diff --check` passed before commit.

## Conclusion

Batch 56 is closed as repo reality. The single non-active copy movement is exposed through an explicit 18011 endpoint, while destructive and batch endpoints remain absent.
