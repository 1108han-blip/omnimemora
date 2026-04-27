# OmniMemora RES-027D.1 Running Stability Re-Sampling (2026-04-27)

## Fixed Conclusion

`running stability re-sampling passed; RES-028 remains unopened`

## Scope

RES-027D.1 is running read-only re-sampling only.

Included:
- marker check for RES-027D functional commit alignment
- read-only 18011 endpoint sampling with 10s timeout and latency
- parity/status/proposal/stability/scaleup readability record
- local worktree drift classification

Explicitly excluded:
- code change
- promotion
- parity rebuild or repair
- RES-028 execution
- second-file pilot execution
- cleanup scope expansion
- cleanup move/delete/compress/truncate/batch execution

## Repository and Marker Reality

Current RES-027D commits:
- `e45a136 fix(dlp): classify timestamp parity drift as semantic`
- `08c1f24 docs(res): close parity timestamp semantics repair`

Running marker:
- path: `/Users/sc/.omnimemora/service/current/.omnimemora_promotion_state.json`
- `repo_revision=e45a136`
- `final_status=running_reality_promoted`
- `log_file=tools/verification/logs/promotion_20260427_191022.log`

Decision:
- marker matches the RES-027D functional commit.
- no promotion was run in RES-027D.1.

Worktree hygiene:
- `.claude/settings.local.json` remains modified as local environment drift.
- it is excluded from RES-027D.1.
- this record does not claim global worktree clean.

## Running Sampling

Validation target:
- instance class: local product adapter
- endpoint base: `http://127.0.0.1:18011`
- timeout: 10s per sampled endpoint

| Endpoint | HTTP | Latency | Result |
|----------|------|---------|--------|
| `/health` | `200` | `6.920049s` | readable; payload status `degraded` / `degraded-capability` |
| `/data-lifecycle/meter-storage/parity` | `200` | `6.893941s` | passed |
| `/data-lifecycle/status` | `200` | `6.892526s` | readable; status `stale_usable` |
| `/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal` | `200` | `6.889802s` | proposal-only, blocked |
| `/data-lifecycle/meter-storage/cleanup/stability-window` | `200` | `2.477282s` | passed |
| `/data-lifecycle/meter-storage/cleanup/scaleup-readiness` | `200` | `2.433358s` | blocked as expected |

Parity sample:
- `status=passed`
- `legacy_count=4952`
- `sqlite_count=4952`
- `payload_hash_mismatch_count=1`
- `semantic_hash_mismatch_count=1`
- `critical_payload_hash_mismatch_count=0`
- `critical_mismatch_count=0`
- `missing_in_sqlite_count=0`
- `missing_in_legacy_count=0`
- `request_id=8e1ddda147d6`
  - `classification=provenance_only`
  - `noncritical_field_paths=["sharing_policy_source", "timestamp", "access_plan.sharing_policy_source"]`

Status sample:
- `meter_storage_v2.cleanup.second_file_pilot_proposal_status=blocked`
- `meter_storage_v2.cleanup.second_file_pilot_allowed=false`
- `meter_storage_v2.cleanup.cleanup_scope_expansion_started=false`
- `meter_storage_v2.cleanup.scaleup_ready=false`

Proposal sample:
- `schema_version=res-second-file-cleanup-pilot-proposal-v1`
- `mode=proposal_only`
- `status=blocked`
- `second_file_pilot_allowed=false`
- `execution_started=false`
- `cleanup_scope_expansion_started=false`
- blocking reasons:
  - `repeatable_protocol_blocked`
  - `no_eligible_candidate_after_res023_exclusion`
  - `res023_quarantined_source_excluded`

Stability-window sample:
- `schema_version=res-legacy-meter-cleanup-stability-window-v1`
- `status=passed`
- `observed_pilot_status=success`
- `cleanup_scope_expansion_started=false`
- `parity_summary.critical_mismatch_count=0`

Scaleup-readiness sample:
- `schema_version=res-legacy-meter-cleanup-scaleup-readiness-v1`
- `status=blocked`
- `ready_for_scaleup=false`
- `cleanup_scope_expansion_started=false`
- blocking reasons:
  - `restore_readback_source_not_retained`

Optional forbidden endpoint spot-check:
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/execute` -> `404` (`2.435327s`)
- `POST /data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal/move` -> `404` (`0.013010s`)

## Decision

RES-027D.1 passes the running stability re-sampling gate:
- `/health` returned HTTP `200`
- parity returned HTTP `200` within timeout and `critical_mismatch_count=0`
- status returned HTTP `200` within timeout and `second_file_pilot_allowed=false`
- proposal returned HTTP `200`, `mode=proposal_only`, and no execution flags
- stability-window and scaleup-readiness were readable
- spot-checked forbidden execution surfaces remained absent

RES-028 remains unopened. This record does not authorize cleanup execution.

## Boundary Confirmation

- running stability re-sampling passed
- RES-028 remains unopened
- no promotion run
- no code change
- no parity rebuild or repair
- no second-file pilot execution
- cleanup scope expansion not started
