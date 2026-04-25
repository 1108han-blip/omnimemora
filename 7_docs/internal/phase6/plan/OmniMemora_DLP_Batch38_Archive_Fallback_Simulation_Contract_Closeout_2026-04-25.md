# OmniMemora DLP Batch 38 Closeout - Archive Fallback Simulation Contract (2026-04-25)

## Conclusion

**Passed for repo reality.**

Batch 38 adds a diagnostic-only fallback simulation contract for archive read-through. It proves the product can explain how evidence would be resolved from an archive copy when source absence is simulated, without changing production read paths or mutating source evidence.

## Commit

- `b4ebce9 feat(dlp): add archive fallback simulation contract`

## Scope

Included:

- `archive_fallback_contract.py`
- policy path/env for `archive_fallback_simulation_report.json`
- `GET /data-lifecycle/archive/fallback/simulation`
- `POST /data-lifecycle/archive/fallback/simulation/rebuild`
- `/data-lifecycle/status.archive_fallback_simulation`
- fallback contract and API/health tests

Excluded:

- source deletion
- source move/quarantine
- compression
- production read-path switch
- Codex live validation
- user/client memory governance

## Contract

- `schema_version=dlp-archive-fallback-simulation-v1`
- `mode=diagnostic_fallback_only`
- `source_missing_simulated=true`
- `production_read_path_unchanged=true`
- fallback is allowed to pass only when archive copy is readable and checksum matches the expected source/archive hash.

## Repo Validation

Command:

```bash
python3 -m pytest -q \
  5_connectors/adapter/tests/test_data_lifecycle_archive_fallback_contract.py \
  5_connectors/adapter/tests/test_data_lifecycle_archive_readthrough.py \
  5_connectors/adapter/tests/test_data_lifecycle_archive_restore_contract.py \
  5_connectors/adapter/tests/test_data_lifecycle_archive_pilot.py \
  5_connectors/adapter/tests/test_data_lifecycle_archive_execution_gate.py \
  5_connectors/adapter/tests/test_data_lifecycle_api.py \
  5_connectors/adapter/__tests__/test_status_read_model.py
```

Result:

- `91 passed`

Additional checks:

- `py_compile` passed for touched Python modules.
- `git diff --check` passed before commit.

## Fixed Boundary

This batch does not make `/debug/request_evidence` read from archive. It only records a diagnostic fallback simulation that can be inspected independently.
