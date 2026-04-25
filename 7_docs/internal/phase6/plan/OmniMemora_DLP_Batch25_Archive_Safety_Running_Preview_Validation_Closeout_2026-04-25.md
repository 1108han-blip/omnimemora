# OmniMemora DLP Batch 25 Closeout - Archive Safety Running Preview Validation (2026-04-25)

## 1. Running Validation Steps

Executed:

```bash
./tools/promotion/promotion.sh adapter+ui
POST /data-lifecycle/retention/manifest/rebuild
POST /data-lifecycle/traceability/report/rebuild
POST /data-lifecycle/archive/plan/rebuild
POST /data-lifecycle/archive/transaction/preview/rebuild
POST /data-lifecycle/archive/restore/readiness/rebuild
GET  /data-lifecycle/archive/plan
GET  /data-lifecycle/archive/transaction/preview
GET  /data-lifecycle/archive/restore/readiness
GET  /data-lifecycle/status
```

Promotion result:

- `running_reality_promoted`
- adapter restart truth: `changed`
- log: `tools/verification/logs/promotion_20260425_123204.log`

---

## 2. Endpoint and Artifact Validation

Rebuild schemas:

- retention: `dlp-retention-manifest-rebuild-v1`
- traceability: `dlp-traceability-report-rebuild-v1`
- archive plan: `dlp-archive-candidate-plan-rebuild-v1`
- archive transaction preview: `dlp-archive-transaction-preview-rebuild-v1`
- archive restore readiness: `dlp-archive-restore-readiness-rebuild-v1`

Ledger triggers:

- `archive_candidate_plan_rebuild`
- `archive_transaction_preview_rebuild`
- `archive_restore_readiness_rebuild`

Artifact schemas/modes:

- archive plan: `schema_version=dlp-archive-candidate-plan-v1`, `mode=dry_run_only`
- archive transaction preview: `schema_version=dlp-archive-transaction-preview-v1`, `mode=preview_only`
- archive restore readiness: `schema_version=dlp-archive-restore-readiness-v1`, `mode=readiness_only`

Candidate-to-preview check:

- `plan.eligible_count=31`
- `preview.eligible_input_count=31`
- `preview.preview_item_count=30`
- excluded counts:
  - `excluded_blocked_count=0`
  - `excluded_review_required_count=4`
- one eligible candidate failed precondition at preview time:
  - `blocked_precondition_count=1`

Status projection check:

- `status.archive_transaction_preview` present and matches preview summary counters
- `status.archive_restore_readiness` present and matches readiness summary counters

---

## 3. Raw Evidence Mutation Check

Method:

- compare raw evidence snapshots (`size + mtime + sha256`) before/after validation chain.

Observed delta:

- total changed files: `1`
- changed file: `trace_events.jsonl`
- blocked changes (`compile/proxy/meter`): `0`

Attribution:

- `trace_events.jsonl` change is caused by validation request trace middleware
- no raw evidence move/compress/delete/rewrite side effect observed

---

## 4. Stage 7 Conclusion

- Batch 22/23/24 code commits and Batch 25 docs-only record are separated
- safety rails in running reality are validated as preview/readiness only
- fixed statement:
  - **archive execution not started**
