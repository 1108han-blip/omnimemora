# OmniMemora DLP Batch 33 Closeout - Running Pilot Validation (2026-04-25)

## 1. Running Validation Steps

Executed:

```bash
./tools/promotion/promotion.sh adapter+ui
POST /data-lifecycle/retention/manifest/rebuild
POST /data-lifecycle/traceability/report/rebuild
POST /data-lifecycle/archive/plan/rebuild
POST /data-lifecycle/archive/transaction/preview/rebuild
POST /data-lifecycle/archive/restore/readiness/rebuild
POST /data-lifecycle/archive/execution/gate/rebuild
POST /data-lifecycle/archive/pilot/copy-one
GET  /data-lifecycle/archive/pilot/latest
GET  /data-lifecycle/status
```

Promotion result:

- `running_reality_promoted`
- adapter restart truth: `changed`
- log: `tools/verification/logs/promotion_20260425_131949.log`

---

## 2. Gate and Pilot Execution Validation

Sequence A (no approval):

1. remove local approval artifact
2. rebuild execution gate

Observed:

- `allowed=false`
- `blocking_reasons=["missing_operator_approval"]`

Sequence B (matching approval):

1. create local approval with current gate `artifact_hashes`
2. rebuild gate

Observed:

- `allowed=true`
- `approval.status=valid`

Sequence C (single-artifact copy pilot):

1. call `POST /data-lifecycle/archive/pilot/copy-one`
2. read `GET /data-lifecycle/archive/pilot/latest`

Observed:

- pilot schema: `dlp-archive-pilot-record-v1`
- pilot mode: `copy_to_archive_only`
- exactly one pilot artifact:
  - `source_path=/Users/sc/.omnimemora/adapter/compile_events.jsonl`
  - `archive_path=/Users/sc/.omnimemora/adapter/data_lifecycle/archive/pilot/874b0a8d6f40/compile_events.jsonl.eb44fcbe2c17.copy`
- `checksum_match=true`
- `source_retained=true`
- `read_path_unchanged=true`

Sequence D (idempotency check):

1. call `POST /data-lifecycle/archive/pilot/copy-one` again

Observed:

- `status=already_copied`
- same `pilot_id` reused

---

## 3. Restore and Status Validation

Observed:

- `POST /data-lifecycle/archive/restore/readiness/rebuild` includes:
  - `pilot_copy_verification.status=verified`
  - source/archive checksum equal
  - `restore_key_match=true`
  - `source_retained=true`
  - `read_path_unchanged=true`
- `GET /data-lifecycle/status` includes:
  - `archive_pilot.status=present`
  - `pilot_id/source_kind/source_bytes/archive_bytes/checksum_match/source_retained/read_path_unchanged` aligned with pilot record

`request_evidence` continuity check:

- sampled `request_id=278c364c2078` (from pilot restore_key mapping)
- `GET /debug/request_evidence?request_id=278c364c2078` readable and valid
- no read-path switch to archive observed

---

## 4. Raw Evidence Mutation Check

Method:

- compare raw evidence checksums before/after second `copy-one` call for:
  - `compile_events`
  - `proxy_events`
  - `trace_events`
  - `meter_index`
  - all `meter_tenant`

Observed:

- `compile_events`: unchanged
- `proxy_events`: unchanged
- `meter_index`: unchanged
- `meter_tenant`: unchanged
- `trace_events`: changed (allowed)

Attribution:

- `trace_events` mutation is from validation request trace middleware
- no source evidence delete/move/compress/rewrite by pilot execution

---

## 5. Stage 9 Conclusion

- Batch 30/31/32 code commits are separated from Batch 33 docs-only running record
- single-artifact reversible archive pilot executed in running reality as copy-only
- source evidence remained retained and readable from original path
- fixed statement:
  - **archive execution pilot completed for one artifact; source cleanup not started**
