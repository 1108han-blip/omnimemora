# OmniMemora RES-027C.1 Running Validation and Worktree Hygiene (2026-04-27)

## Fixed Conclusion

`RES-027C running validation attempted; parity remains degraded; RES-028 remains blocked; cleanup scope expansion not started`

## Scope

RES-027C.1 is running validation and worktree hygiene only.

Included:
- promotion alignment to RES-027C committed HEAD
- read-only product-interface validation through `http://127.0.0.1:18011`
- worktree hygiene classification for local environment drift
- failed/blocked running-validation record

Explicitly excluded:
- RES-028 execution
- second-file pilot execution
- cleanup scope expansion
- cleanup move/delete/compress/truncate/batch execution
- parity rebuild or repair
- code changes

## Repository Reality

RES-027C commits exist:
- `22f175d feat(dlp): classify meter parity semantic drift`
- `11cb412 docs(res): close meter parity contract repair`

RES-027C repository/doc direction:
- raw mismatch remains visible
- critical hash mismatch is separated from semantic/provenance mismatch
- `semantic_hash_mismatch_count` is present in the report contract
- `critical_payload_hash_mismatch_count` is present in the report contract
- RES-028 is not opened
- `cleanup scope expansion not started` remains the active boundary

Worktree hygiene:
- before RES-027C.1 docs edits, `git status --short` showed one local environment file:
  - `M .claude/settings.local.json`
- diff classification:
  - local Claude permission allowlist changes only
  - not a RES-027C code/doc/data file
  - not staged into RES-027C.1
  - not used for any worktree-clean claim
- conclusion:
  - repo reality for RES-027C code/docs is committed
  - global worktree is not clean while `.claude/settings.local.json` remains modified
  - `.claude/settings.local.json` is excluded from this RES line and should be handled in a separate local-environment line if needed

## Promotion Alignment

Validation target:
- instance class: local product adapter + UI
- promotion target: `adapter+ui`
- command: `./tools/promotion/promotion.sh adapter+ui`

Result:
- log: `tools/verification/logs/promotion_20260427_190412.log`
- `repo_revision=11cb412`
- `running_reality_before: runtime=healthy adapter=healthy ui=healthy`
- `running_reality_after: runtime=healthy adapter=healthy ui=healthy`
- `final_status=running_reality_promoted`
- deployed marker: `/Users/sc/.omnimemora/service/current/.omnimemora_promotion_state.json`

## Running Reality

Read-only parity check:
- `GET /data-lifecycle/meter-storage/parity`
- `status=degraded`
- `legacy_count=4952`
- `sqlite_count=4952`
- `matching_request_id_count=4952`
- `missing_in_sqlite_count=0`
- `missing_in_legacy_count=0`
- `payload_hash_mismatch_count=1`
- `semantic_hash_mismatch_count=0`
- `critical_payload_hash_mismatch_count=1`
- `critical_mismatch_count=1`

Read-only status/proposal checks:
- `GET /data-lifecycle/status`
  - `meter_storage_v2.cleanup.second_file_pilot_proposal_status=blocked`
  - `meter_storage_v2.cleanup.second_file_pilot_allowed=false`
  - `meter_storage_v2.cleanup.cleanup_scope_expansion_started=false`
- `GET /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal`
  - `mode=proposal_only`
  - `status=blocked`
  - `second_file_pilot_allowed=false`
  - `execution_started=false`
  - `cleanup_scope_expansion_started=false`
  - blocking reasons include `parity_not_clean`

## Failure Diagnosis

Local read-only payload comparison against the running data paths:
- legacy source: `/Users/sc/.omnimemora/service/current/5_connectors/data/meters_index.json`
- sqlite source: `/Users/sc/.omnimemora/adapter/meter_store_v2/meter_store.sqlite3`

Observed mismatch:
- raw mismatch count: `1`
- critical mismatch count: `1`
- semantic mismatch count: `0`
- request id: `8e1ddda147d6`

Differing fields:
- `timestamp`
- `sharing_policy_source`
- `access_plan.sharing_policy_source`

Reason RES-027C.1 failed:
- RES-027C excludes `sharing_policy_source` / `access_plan.sharing_policy_source` from critical hash.
- RES-027C does not exclude or normalize `timestamp`.
- Therefore `timestamp` keeps `request_id=8e1ddda147d6` classified as a critical payload mismatch.

Additional implementation signal:
- `hash_mismatch_samples` currently includes matching ids whose raw hashes are equal and classifies them as `provenance_only`.
- This is inconsistent with `payload_hash_mismatch_count=1`.
- This sample-reporting defect does not unblock RES-028 and should be repaired in a later code line.

## Gate Decision

RES-028 remains blocked.

Required next line:
- RES-027D or equivalent contract repair for timestamp semantics and parity sample reporting.

RES-027C.1 does not authorize:
- second-file pilot execution
- cleanup scope expansion
- cleanup pilot/move execution
- parity rebuild or repair

## Boundary Confirmation

- running validation attempted
- running validation did not pass
- `critical_mismatch_count=1`
- `second_file_pilot_allowed=false`
- second-file pilot execution not started
- cleanup scope expansion not started
- no parity rebuild or repair executed
- no cleanup pilot/move endpoint called
