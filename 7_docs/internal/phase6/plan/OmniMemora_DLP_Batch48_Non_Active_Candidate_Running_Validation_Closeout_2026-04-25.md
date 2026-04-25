# OmniMemora DLP Batch 48 - Non-Active Candidate Running Validation Closeout

Date: 2026-04-25

## Scope

Batch 48 validates the non-active candidate selector in running reality.

The validation target is selector/report behavior only. It does not execute quarantine.

## Promotion

- Command: `./tools/promotion/promotion.sh adapter+ui`
- Log: `tools/verification/logs/promotion_20260425_152359.log`
- Result: `running_reality_promoted`
- Repo revision: `70568f2`
- Adapter restart truth: `changed`

## Running Validation

Executed against `http://127.0.0.1:18011`:

- `POST /data-lifecycle/archive/non-active-candidates/report/rebuild`
- `GET /data-lifecycle/archive/non-active-candidates/report`
- `GET /data-lifecycle/status`

## Result

- Report schema: `dlp-non-active-candidate-report-v1`
- Mode: `non_active_selection_report_only`
- Summary:
  - `total_scanned=36`
  - `forbidden_count=35`
  - `plausible_non_active_count=1`
  - `review_required_count=0`
  - `source_move_delete_compress_executed=false`
- `/data-lifecycle/status.archive_non_active_candidates` matched the report summary.

## Candidate Classification

Forbidden examples:

- `compile_events.jsonl`
- `proxy_events.jsonl`
- `trace_events.jsonl`
- `meters_index.json`
- DLP control/read-model artifacts

Plausible non-active candidate:

- `/Users/sc/.omnimemora/adapter/data_lifecycle/archive/pilot/b78bd05bd3cf/compile_events.jsonl.81b50dd5f1bd.copy`
- Candidate kind: `archive_pilot_copy`
- Origin source kind: `compile_events`
- Checksum lineage: matched
- Planned action remains `quarantine_non_active_preview_only`
- `would_move_source=false`

## Raw Evidence Mutation Check

- `compile_events.jsonl`: unchanged
- `proxy_events.jsonl`: unchanged
- `trace_events.jsonl`: changed only due validation request trace middleware

## Conclusion

Batch 48 is closed as passed for selector/report running validation. The next safe engineering step is to make future quarantine consume a selector-approved `archive_pilot_copy`, not an active production source.
