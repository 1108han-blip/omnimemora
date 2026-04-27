# OmniMemora RES-027E Running Latency Diagnosis (2026-04-27)

## Fixed Conclusion

`running latency source diagnosed; RES-028 remains unopened; cleanup scope expansion not started`

## Scope

RES-027E is 18011 read-only latency diagnosis only.

Included:
- marker/worktree check
- 5-sample latency diagnosis per target endpoint
- parity/status/proposal safety field checks
- latency source classification

Explicitly excluded:
- code change
- promotion
- parity rebuild or repair
- RES-028 execution
- second-file pilot execution
- cleanup scope expansion
- cleanup move/delete/compress/truncate/batch execution

## Repository and Marker Reality

Current latest docs commit:
- `18eccf0 docs(res): record running stability resampling`

RES-027D functional running marker:
- path: `/Users/sc/.omnimemora/service/current/.omnimemora_promotion_state.json`
- `repo_revision=e45a136`
- `final_status=running_reality_promoted`
- `log_file=tools/verification/logs/promotion_20260427_191022.log`

Decision:
- marker matches the RES-027D functional commit.
- no promotion was run in RES-027E.

Worktree hygiene:
- `.claude/settings.local.json` remains modified as local environment drift.
- it is excluded from RES-027E.
- this record does not claim global worktree clean.

## Sampling Method

Validation target:
- instance class: local product adapter
- endpoint base: `http://127.0.0.1:18011`
- timeout: 10s per request
- samples: 5 per endpoint
- raw local scratch file: `/tmp/res027e_latency.tsv`

No `/data-lifecycle/meter-storage/parity/rebuild` call was made.
No cleanup move/execute endpoint was called.

## Latency Matrix

| Class | Endpoint | Count | p50 | Max | Errors | Timeouts |
|-------|----------|-------|-----|-----|--------|----------|
| Baseline | `/health` | 5 | `0.013458s` | `0.034044s` | 0 | 0 |
| Direct meter path | `/data-lifecycle/meter-storage/parity` | 5 | `3.492614s` | `3.687705s` | 0 | 0 |
| Aggregated status | `/data-lifecycle/status` | 5 | `1.176646s` | `1.360131s` | 0 | 0 |
| Cleanup-specific read | `/data-lifecycle/meter-storage/cleanup/stability-window` | 5 | `0.011571s` | `0.012578s` | 0 | 0 |
| Cleanup-specific read | `/data-lifecycle/meter-storage/cleanup/scaleup-readiness` | 5 | `0.009548s` | `0.012695s` | 0 | 0 |
| Cleanup-specific read | `/data-lifecycle/meter-storage/cleanup/second-file-pilot/proposal` | 5 | `0.014517s` | `0.014742s` | 0 | 0 |
| Smoke | `/metrics/summary` | 5 | `0.009279s` | `0.009566s` | 0 | 0 |
| Smoke | `/agents/control` | 5 | `0.009385s` | `0.150966s` | 0 | 0 |

## Safety Fields

Parity:
- `status=passed`
- `payload_hash_mismatch_count=1`
- `semantic_hash_mismatch_count=1`
- `critical_payload_hash_mismatch_count=0`
- `critical_mismatch_count=0`
- `request_id=8e1ddda147d6`
  - `classification=provenance_only`
  - `noncritical_field_paths=["sharing_policy_source", "timestamp", "access_plan.sharing_policy_source"]`

Status:
- `status=stale_usable`
- `meter_storage_v2.cleanup.second_file_pilot_allowed=false`
- `meter_storage_v2.cleanup.second_file_pilot_proposal_status=blocked`
- `meter_storage_v2.cleanup.cleanup_scope_expansion_started=false`
- `delete_executed=false`
- `compress_executed=false`
- `truncate_executed=false`
- `batch_cleanup_executed=false`

Proposal:
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

Pilot latest:
- `pilot_id=aff9611a29f74657`
- `status=success`
- `source_move_executed=true` from RES-023 only
- `delete_executed=false`
- `compress_executed=false`
- `truncate_executed=false`
- `batch_cleanup_executed=false`

## Diagnosis

Primary latency source:
- `meter parity scan/hash path`

Reasoning:
- `/health` is fast: p50 `0.013458s`, max `0.034044s`.
- cleanup-specific reads are fast: p50 approximately `0.009548s` to `0.014517s`.
- smoke endpoints are fast: `/metrics/summary` p50 `0.009279s`, `/agents/control` p50 `0.009385s`.
- `/data-lifecycle/status` is slower than baseline but still below parity: p50 `1.176646s`, max `1.360131s`.
- `/data-lifecycle/meter-storage/parity` is the only stable multi-second endpoint: p50 `3.492614s`, max `3.687705s`.

Secondary observation:
- status aggregation has measurable overhead, but it is not the primary latency source in this sampling window.

Rejected primary sources:
- `adapter event loop / process pressure`: rejected because `/health` is fast and no endpoint timed out.
- `cleanup artifact runtime cross-read path`: rejected because stability-window, scaleup-readiness, and proposal reads are fast.
- `transient runtime latency`: rejected because parity is consistently slower across all 5 samples while other endpoints remain fast.

## Decision

RES-027E diagnosis passed:
- primary latency source classified as `meter parity scan/hash path`
- parity remained readable with `critical_mismatch_count=0`
- status remained readable with `second_file_pilot_allowed=false`
- proposal remained `proposal_only` and blocked
- no execution flag appeared
- no second source move was observed

RES-028 remains unopened.

Recommended next line if optimization is required:
- RES-027F parity read optimization plan/implementation.

## Boundary Confirmation

- running latency source diagnosed
- RES-028 remains unopened
- no promotion run
- no code change
- no parity rebuild or repair
- no second-file pilot execution
- cleanup scope expansion not started
