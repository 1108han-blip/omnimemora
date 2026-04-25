# OmniMemora DLP Batch 37 Closeout - Running Shadow Validation (2026-04-25)

## 1. Running Validation Steps

Executed:

```bash
./tools/promotion/promotion.sh adapter+ui
POST /data-lifecycle/archive/restore/readiness/rebuild
POST /data-lifecycle/archive/readthrough/report/rebuild
GET  /data-lifecycle/archive/readthrough/report
GET  /data-lifecycle/status
```

Promotion result:

- `running_reality_promoted`
- adapter restart truth: `changed`
- log: `tools/verification/logs/promotion_20260425_134926.log`

---

## 2. Drift Realignment Note

Initial shadow run exposed pre-existing Stage 9 drift:

- old pilot copy checksum no longer matched current source (`checksum_mismatch`)

Realignment sequence (non-destructive):

```bash
POST /data-lifecycle/retention/manifest/rebuild
POST /data-lifecycle/traceability/report/rebuild
POST /data-lifecycle/archive/plan/rebuild
POST /data-lifecycle/archive/transaction/preview/rebuild
POST /data-lifecycle/archive/pilot/copy-one
POST /data-lifecycle/archive/restore/readiness/rebuild
POST /data-lifecycle/archive/readthrough/report/rebuild
```

Final observed read-through state:

- `schema_version=dlp-archive-readthrough-report-v1`
- `mode=shadow_validation_only`
- `status=passed`
- `source_retained=true`
- `archive_copy_readable=true`
- `checksum_match=true`
- `read_path_unchanged=true`

Final pilot reference:

- `pilot_id=b78bd05bd3cf`
- source: `/Users/sc/.omnimemora/adapter/compile_events.jsonl`
- archive copy: `/Users/sc/.omnimemora/adapter/data_lifecycle/archive/pilot/b78bd05bd3cf/compile_events.jsonl.81b50dd5f1bd.copy`

---

## 3. Status and Request Evidence Cross-Check

`/data-lifecycle/status` snapshot:

- `archive_readthrough.status=passed`
- `archive_readthrough.source_retained=true`
- `archive_readthrough.archive_copy_readable=true`
- `archive_readthrough.checksum_match=true`
- `archive_readthrough.read_path_unchanged=true`
- `archive_readthrough.validated_at=2026-04-25T05:52:23.858604+00:00`

Shadow request mapping:

- `request_id_cross_check.status=mapped`
- sampled request id: `b25a0530854d`
- `/debug/request_evidence?request_id=b25a0530854d` readable

Conclusion:

- request evidence remained readable via source path; archive read-through stayed diagnostic-only.

---

## 4. Raw Evidence Mutation Check

Method:

- compare source evidence checksum before/after recheck chain for:
  - `compile_events`
  - `proxy_events`
  - `trace_events`
  - `meter_index`
  - all `meter_tenant`

Observed:

- `compile_events`: same
- `proxy_events`: same
- `meter_index`: same
- `meter_tenant`: same
- `trace_events`: changed (allowed)

Attribution:

- `trace_events.jsonl` change is from validation trace middleware
- no source cleanup/delete/move/compress/rewrite observed

---

## 5. Stage 10 Conclusion

- Batch 34/35/36 code commits are separated from Batch 37 docs-only running record
- archive read-through shadow validation reached `passed` in running reality
- fixed statement:
  - **archive read-through shadow validation passed; production read path remains unchanged; source cleanup not started**
