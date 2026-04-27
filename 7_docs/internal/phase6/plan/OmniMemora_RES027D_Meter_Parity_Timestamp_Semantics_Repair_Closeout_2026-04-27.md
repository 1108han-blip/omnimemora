# OmniMemora RES-027D Meter Parity Timestamp Semantics Repair Closeout (2026-04-27)

## Fixed Conclusion

`meter parity timestamp semantics repaired; RES-028 remains blocked until running parity is clean; cleanup scope expansion not started`

## Scope

RES-027D repairs the parity contract exposed by RES-027C.1 and validates it in running reality.

Included:
- timestamp semantics repair for meter parity critical hash
- hash mismatch sample reporting repair
- repo tests for timestamp, provenance, business drift, missing records, and sample filtering
- promotion `adapter+ui`
- read-only running validation through `http://127.0.0.1:18011`
- proposal-only artifact refresh for repeatable protocol and second-file proposal

Explicitly excluded:
- RES-028 execution
- second-file pilot execution
- cleanup scope expansion
- cleanup move/delete/compress/truncate/batch execution
- `/data-lifecycle/meter-storage/parity/rebuild`

## Repository Reality

Code commit:
- `e45a136 fix(dlp): classify timestamp parity drift as semantic`

Changed contract:
- `timestamp` is excluded from critical business hash as temporal/provenance metadata.
- top-level `sharing_policy_source` remains excluded from critical business hash.
- nested `access_plan.sharing_policy_source` remains excluded through recursive critical payload stripping.
- raw `payload_hash_mismatch_count` remains diagnostic and is not suppressed.
- `hash_mismatch_samples` now only includes records where `raw_mismatch == true` or `critical_mismatch == true`.

Critical fields still covered by critical hash include:
- `request_id`
- token/count fields
- tenant/agent/family/client fields
- query and query-size fields
- task/context fields
- other business payload fields not explicitly classified as temporal/provenance metadata

## Repo Verification

Tests:
- `python3 -m pytest -q 5_connectors/adapter/tests/test_meter_storage_parity.py`
  - result: `11 passed`
- `python3 -m pytest -q 5_connectors/adapter/tests/test_meter_cleanup_preview.py 5_connectors/adapter/tests/test_meter_cleanup_scaleup_readiness.py 5_connectors/adapter/tests/test_meter_cleanup_second_file_pilot_proposal.py`
  - result: `11 passed`
- `python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_api.py 5_connectors/adapter/tests/test_data_lifecycle_safety_invariants.py`
  - result: `137 passed`
- `python3 -m py_compile 5_connectors/adapter/data_lifecycle/meter_storage_v2.py`
  - result: passed
- `git diff --check`
  - result: passed

Covered cases:
- timestamp-only diff:
  - raw mismatch > 0
  - semantic mismatch > 0
  - critical mismatch = 0
  - status passed
- timestamp + `sharing_policy_source` + `access_plan.sharing_policy_source`:
  - `classification=provenance_only`
  - `noncritical_field_paths` includes all three fields
- business field diff:
  - `classification=critical`
  - critical mismatch > 0
  - status degraded
- raw hash identical records:
  - excluded from `hash_mismatch_samples`
- missing in legacy/sqlite:
  - still counted as critical mismatch
- cleanup preview / scaleup readiness / second-file proposal:
  - still gate on `critical_mismatch_count`

## Promotion Alignment

Validation target:
- instance class: local product adapter + UI
- promotion target: `adapter+ui`
- command: `./tools/promotion/promotion.sh adapter+ui`

Result:
- log: `tools/verification/logs/promotion_20260427_191022.log`
- `repo_revision=e45a136`
- `running_reality_before: runtime=healthy adapter=healthy ui=healthy`
- `running_reality_after: runtime=healthy adapter=healthy ui=healthy`
- `final_status=running_reality_promoted`
- deployed marker: `/Users/sc/.omnimemora/service/current/.omnimemora_promotion_state.json`

## Running Reality

Read-only parity check:
- `GET /data-lifecycle/meter-storage/parity`
- `status=passed`
- `legacy_count=4952`
- `sqlite_count=4952`
- `payload_hash_mismatch_count=1`
- `semantic_hash_mismatch_count=1`
- `critical_payload_hash_mismatch_count=0`
- `critical_mismatch_count=0`
- `missing_in_sqlite_count=0`
- `missing_in_legacy_count=0`

Fixed sample:
- `request_id=8e1ddda147d6`
- `classification=provenance_only`
- `noncritical_field_paths`:
  - `sharing_policy_source`
  - `timestamp`
  - `access_plan.sharing_policy_source`

Proposal-only refresh:
- `POST /data-lifecycle/meter-storage/cleanup/repeatable-pilot-protocol/rebuild`
  - read-only proposal artifact refresh
  - no execution path called
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/rebuild`
  - read-only proposal artifact refresh
  - no execution path called

Second-file proposal read:
- `GET /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal`
- `mode=proposal_only`
- `status=blocked`
- `second_file_pilot_allowed=false`
- `execution_started=false`
- `cleanup_scope_expansion_started=false`
- blocking reasons:
  - `repeatable_protocol_blocked`
  - `no_eligible_candidate_after_res023_exclusion`
  - `res023_quarantined_source_excluded`

Forbidden endpoints:
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/execute` -> `404`
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/delete` -> `404`
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/move` -> `404`
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/compress` -> `404`
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/truncate` -> `404`
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/batch` -> `404`

Pilot latest:
- `GET /data-lifecycle/meter-storage/cleanup/pilot/latest`
- `pilot_id=aff9611a29f74657`
- `status=success`
- `source_move_executed=true` from RES-023 only
- `delete_executed=false`
- `compress_executed=false`
- `truncate_executed=false`
- `batch_cleanup_executed=false`

Smoke:
- `GET /metrics/summary` -> `200`
- `GET /agents/control` -> `200`
- `GET /requests/8e1ddda147d6/meter` -> `200`
- `GET /debug/request_evidence?request_id=8e1ddda147d6` -> `200`

## Gate Decision

RES-027D repairs and validates the timestamp parity semantics.

RES-028 remains unopened in this line. A future RES-028 discussion may only start from the updated running truth:
- parity is clean at `critical_mismatch_count=0`
- second-file proposal remains proposal-only and blocked by non-parity proposal conditions
- explicit operator approval is still required before any execution line

## Worktree Hygiene

`.claude/settings.local.json` remains a local environment drift and is excluded from RES-027D.

This RES-027D closeout does not claim global worktree clean while that file remains modified.

## Boundary Confirmation

- meter parity timestamp semantics repaired
- sample reporting repaired
- RES-028 not opened
- second-file pilot execution not started
- cleanup scope expansion not started
- no `/data-lifecycle/meter-storage/parity/rebuild` call was made
- no cleanup pilot/move/delete/compress/truncate/batch endpoint was called
