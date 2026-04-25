# OmniMemora DLP Batch 58 - Non-Active Copy Quarantine Running Validation Closeout (2026-04-25)

## Scope

Batch 58 validates the actual single-artifact non-active copy quarantine in running reality.

This is the first DLP movement of a non-active copy. It does not move source evidence.

## Promotion

- Command: `./tools/promotion/promotion.sh adapter+ui`
- Result: `running_reality_promoted`
- Running revision: `6ed2de7`
- Adapter restart truth: `changed`
- Promotion log:
  - `tools/verification/logs/promotion_20260425_161359.log`

## Running Sequence

1. `POST /data-lifecycle/archive/non-active-candidates/report/rebuild`
2. `POST /data-lifecycle/archive/non-active-quarantine/readiness/rebuild`
3. `POST /data-lifecycle/archive/non-active-quarantine/execution/gate/rebuild`
4. Local operator approval generated against current gate hashes.
5. `POST /data-lifecycle/archive/non-active-quarantine/execution/gate/rebuild`
6. `POST /data-lifecycle/archive/non-active-quarantine/move-one`
7. `POST /data-lifecycle/archive/restore/pilot/run`
8. `GET /data-lifecycle/status`

## Result

Selected candidate:

- kind: `archive_pilot_copy`
- pre-move path:
  - `/Users/sc/.omnimemora/adapter/data_lifecycle/archive/pilot/b78bd05bd3cf/compile_events.jsonl.81b50dd5f1bd.copy`
- quarantine path:
  - `/Users/sc/.omnimemora/adapter/data_lifecycle/quarantine/source/non_active/compile_events.jsonl.81b50dd5f1bd.copy.81b50dd5f1bd.quarantine`

Observed movement:

- `gate_after_approval_allowed=true`
- `move_record_status=success`
- `move_mode=single_non_active_copy_quarantine_only`
- `source_move_executed=false`
- `non_active_copy_move_executed=true`
- `delete_compress_executed=false`
- `move_checksum_match=true`

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

Batch 58 is closed as running reality.

Fixed conclusion:

`single non-active archive_pilot_copy quarantined; source evidence retained; restore pilot succeeded to staging`
