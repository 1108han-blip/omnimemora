# OmniMemora DLP Batch 59 - Shadow Readthrough After Non-Active Quarantine Closeout (2026-04-25)

## Scope

Batch 59 validates that shadow readthrough and restore readiness remain explainable after the non-active copy is moved into quarantine.

This remains diagnostic/shadow-only. No production read path was switched.

## Promotion

- Command: `./tools/promotion/promotion.sh adapter+ui`
- Result: `running_reality_promoted`
- Running revision: `3d40414`
- Adapter restart truth: `changed`
- Promotion log:
  - `tools/verification/logs/promotion_20260425_161910.log`

## Running Sequence

1. `GET /data-lifecycle/archive/non-active-quarantine/latest`
2. `POST /data-lifecycle/archive/restore/readiness/rebuild`
3. `POST /data-lifecycle/archive/readthrough/report/rebuild`
4. `POST /data-lifecycle/archive/restore/pilot/run`
5. `GET /data-lifecycle/status`

All returned `200`.

## Result

Quarantine:

- `quarantine_status=success`
- `quarantine_mode=single_non_active_copy_quarantine_only`
- `quarantine_checksum_match=true`
- `quarantine_source_move_executed=false`
- `quarantine_non_active_copy_move_executed=true`

Restore readiness:

- `pilot_copy_status=verified`
- `archive_resolution_source=non_active_quarantine`
- `lineage_checksum_match=true`
- `current_source_checksum_match=false`

Readthrough:

- `status=passed`
- `archive_resolution_source=non_active_quarantine`
- `checksum_match=true`
- `lineage_checksum_match=true`
- `current_source_checksum_match=false`
- `source_retained=true`
- `read_path_unchanged=true`

Restore pilot:

- `restore_status=success`
- `restore_target_scope=staging`
- `restore_checksum_match=true`
- `production_source_overwrite=false`

Raw evidence mutation check:

- `compile_events.jsonl`: `same`
- `proxy_events.jsonl`: `same`
- `trace_events.jsonl`: `changed`

The `trace_events.jsonl` change is attributed to validation request trace middleware.

## Conclusion

Batch 59 is closed as running reality.

Fixed conclusion:

`quarantined non-active copy remains shadow-readable by lineage; production read path unchanged`
