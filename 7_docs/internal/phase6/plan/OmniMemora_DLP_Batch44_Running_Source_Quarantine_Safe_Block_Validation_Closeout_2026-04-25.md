# OmniMemora DLP Batch 44 - Running Source Quarantine Safe Block Validation Closeout

Date: 2026-04-25

## Scope

Batch 44 validates Stage 12B in running reality. The expected valid outcome is safe block if the current candidate is an active source.

## Promotion

- Command: `./tools/promotion/promotion.sh adapter+ui`
- Log: `tools/verification/logs/promotion_20260425_150804.log`
- Result: `running_reality_promoted`
- Repo revision: `d92384a`
- Adapter restart truth: `changed`

## Running Validation Sequence

Executed against `http://127.0.0.1:18011`:

- `POST /data-lifecycle/archive/fallback/simulation/rebuild`
- `POST /data-lifecycle/archive/quarantine/readiness/rebuild`
- `POST /data-lifecycle/archive/quarantine/move-one`
- `GET /data-lifecycle/archive/quarantine/latest`
- `GET /data-lifecycle/status`

## Result

- Quarantine record schema: `dlp-source-quarantine-record-v1`
- Mode: `single_artifact_quarantine_only`
- Status: `blocked`
- Source kind: `compile_events`
- Source path: `/Users/sc/.omnimemora/adapter/compile_events.jsonl`
- Blocking reasons:
  - `quarantine_readiness_not_ready_for_approval`
  - `source_checksum_mismatch_with_pilot`
  - `candidate_is_active_hot_source`
- `source_move_executed=false`
- `source_retained=true`
- Planned quarantine target did not exist after validation.
- `/data-lifecycle/status.archive_quarantine` matched the blocked record summary.

## Raw Evidence Mutation Check

- `compile_events.jsonl`: unchanged
- `proxy_events.jsonl`: unchanged
- `trace_events.jsonl`: changed only due validation request trace middleware

## Conclusion

Batch 44 is closed as `safe blocked`. Stage 12B did not move source because the running candidate was active/hot and had drifted relative to the earlier pilot checksum.
