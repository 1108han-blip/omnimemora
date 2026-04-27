# OmniMemora RES-027F Parity Read Optimization Closeout (2026-04-27)

## Fixed Conclusion

`meter parity read path optimized; RES-028 remains unopened; cleanup scope expansion not started`

## Scope

RES-027F optimizes the 18011 meter parity read path from full scan/hash on every GET to snapshot-first.

Included:
- parity snapshot artifact implementation
- GET `/data-lifecycle/meter-storage/parity` snapshot-first behavior
- explicit full-scan path through POST `/data-lifecycle/meter-storage/parity/rebuild`
- focused repo tests and downstream cleanup gate regression tests
- adapter+ui promotion and running validation

Explicitly excluded:
- second-file pilot execution
- cleanup scope expansion
- cleanup move/delete/compress/truncate/batch execution
- production read-path switch outside the parity governance surface
- manual raw meter edits

## Repository Reality

Functional commit:
- `7abd9db feat(dlp): make meter parity reads snapshot-first`

Changed code surface:
- `5_connectors/adapter/data_lifecycle/meter_storage_v2.py`
- `5_connectors/adapter/data_lifecycle_api.py`
- `5_connectors/adapter/tests/test_meter_storage_parity.py`
- `5_connectors/adapter/tests/test_data_lifecycle_api.py`

Implemented contract:
- snapshot schema: `dlp-meter-storage-v2-parity-snapshot-v1`
- default snapshot path: `OMNIMEMORA_DLP_METER_PARITY_SNAPSHOT_FILE`, falling back to `OMNIMEMORA_DLP_DIR/meter_parity_snapshot.json`
- GET `/data-lifecycle/meter-storage/parity` reads snapshot first.
- missing snapshot returns `status=missing`, `missing_reason=snapshot_missing`, and does not full-scan.
- GET `/data-lifecycle/meter-storage/parity?fresh=true` keeps the explicit direct full-scan path.
- POST `/data-lifecycle/meter-storage/parity/rebuild` performs rebuild/full parity and atomically writes the snapshot.
- atomic snapshot write uses temp-file plus replace; replace failure preserves the previous snapshot.

Preserved parity fields:
- `payload_hash_mismatch_count`
- `semantic_hash_mismatch_count`
- `critical_payload_hash_mismatch_count`
- `critical_mismatch_count`
- downstream cleanup gates continue to gate on `critical_mismatch_count`.

## Worktree Hygiene

Pre-existing local environment drift:
- `.claude/settings.local.json`

Decision:
- excluded from RES-027F
- not staged
- not committed
- this record does not claim global worktree clean while that file remains modified

## Repo Validation

Commands:

```bash
python3 -m pytest -q 5_connectors/adapter/tests/test_meter_storage_parity.py
python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_api.py
python3 -m pytest -q 5_connectors/adapter/tests/test_meter_cleanup_preview.py 5_connectors/adapter/tests/test_meter_cleanup_scaleup_readiness.py 5_connectors/adapter/tests/test_meter_cleanup_second_file_pilot_proposal.py
python3 -m py_compile 5_connectors/adapter/data_lifecycle/meter_storage_v2.py 5_connectors/adapter/data_lifecycle_api.py
git diff --check
```

Results:
- meter parity tests: `14 passed`
- data lifecycle API tests: `115 passed`
- cleanup preview/scaleup/second-file proposal tests: `11 passed`
- py_compile: passed
- git diff check: passed

## Running Promotion

Validation target:
- instance class: local product adapter and UI
- endpoint base: `http://127.0.0.1:18011`
- promotion target: `adapter+ui`

Promotion result:
- `repo_revision=7abd9db`
- `final_status=running_reality_promoted`
- log: `tools/verification/logs/promotion_20260427_195025.log`

## Snapshot Generation

Allowed RES-027F action:
- POST `/data-lifecycle/meter-storage/parity/rebuild`

Observation:
- client-side request timed out after 30s while waiting for the explicit full scan/rebuild response.
- server completed the rebuild path and wrote the parity snapshot.
- subsequent GET `/data-lifecycle/meter-storage/parity` returned the snapshot with `snapshot_missing=false`.

Generated snapshot:
- path: `/Users/sc/.omnimemora/adapter/data_lifecycle/meter_parity_snapshot.json`
- `snapshot_generated_at=2026-04-27T11:51:40.764008+00:00`
- `read_mode=snapshot_first`
- `status=passed`
- `critical_mismatch_count=0`

No second rebuild call was made.

## Running Latency Validation

Parity GET samples after snapshot generation:

| Endpoint | Count | Codes | p50 | Max | Status | Read mode |
|---|---:|---|---:|---:|---|---|
| `/data-lifecycle/meter-storage/parity` | 5 | `200,200,200,200,200` | `0.010241s` | `0.013336s` | `passed` | `snapshot_first` |

Sample latencies:
- `0.013336s`
- `0.008268s`
- `0.010241s`
- `0.007954s`
- `0.010443s`

Comparison to RES-027E:
- RES-027E parity p50: `3.492614s`
- RES-027F parity p50: `0.010241s`
- result: significantly below the required `<0.5s` target and below the fallback `<1s` threshold.

Parity safety fields:
- `critical_mismatch_count=0`
- `payload_hash_mismatch_count=0`
- `semantic_hash_mismatch_count=0`
- `snapshot_missing=false`

Note:
- RES-027D/RES-027E observed provenance-only mismatch before the rebuild.
- RES-027F rebuild synced the SQLite mirror from legacy before writing the snapshot, so the generated snapshot is fully clean.

## Running Safety Checks

Read endpoints:

| Endpoint | Code | Latency | Key result |
|---|---:|---:|---|
| `/health` | 200 | `0.009364s` | `status=healthy` |
| `/data-lifecycle/status` | 200 | `1.289422s` | readable; follow-up nested check showed meter storage healthy |
| `/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal` | 200 | `0.013877s` | `mode=proposal_only`, `status=blocked`, `second_file_pilot_allowed=false` |
| `/data-lifecycle/meter-storage/cleanup/stability-window` | 200 | `0.010361s` | `status=passed`, `cleanup_scope_expansion_started=false` |
| `/data-lifecycle/meter-storage/cleanup/scaleup-readiness` | 200 | `0.011977s` | `status=blocked`, `cleanup_scope_expansion_started=false` |
| `/metrics/summary` | 200 | `0.010552s` | smoke readable |
| `/agents/control` | 200 | `0.156394s` | smoke readable |

Status follow-up:
- `/data-lifecycle/status` returned `status=healthy`
- `meter_storage_v2.status=healthy`
- `meter_storage_v2.cleanup.second_file_pilot_allowed=false`
- `meter_storage_v2.cleanup.second_file_pilot_proposal_status=blocked`
- `meter_storage_v2.cleanup.cleanup_scope_expansion_started=false`

Forbidden spot checks:
- POST `/data-lifecycle/meter-storage/cleanup/pilot/execute` -> 404
- POST `/data-lifecycle/meter-storage/cleanup/second-file-pilot/execute` -> 404

## Decision

RES-027F passes:
- repository implementation and tests pass.
- running marker is promoted to the RES-027F functional commit.
- parity GET is snapshot-first.
- parity GET p50 is `0.010241s`, materially below RES-027E p50 `3.492614s`.
- running parity is clean with `critical_mismatch_count=0`.
- status and cleanup proposal remain readable and blocked.
- forbidden cleanup execution endpoints remain 404.

RES-028 remains unopened.

## Boundary Confirmation

- meter parity read path optimized
- RES-028 remains unopened
- second-file pilot execution not started
- cleanup scope expansion not started
- no cleanup move/delete/compress/truncate/batch execution
