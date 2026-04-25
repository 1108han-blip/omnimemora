# OmniMemora DLP Batch 19 Closeout - Archive Candidate Plan Skeleton (2026-04-25)

## 1. Scope

Batch 19 delivers archive candidate planning skeleton only:

- add `archive_plan.py` and dry-run planner contract
- add policy default path for archive candidate plan
- add archive plan core tests

Boundary kept:

- `mode` fixed as `dry_run_only`
- no archive execute/delete/move/compress path added
- no change to `/agents/control` schema or ingress protocol

---

## 2. Repo Validation

Executed:

```bash
python3 -m pytest -q \
  5_connectors/adapter/tests/test_data_lifecycle_archive_plan.py \
  5_connectors/adapter/tests/test_data_lifecycle_retention_manifest.py \
  5_connectors/adapter/tests/test_data_lifecycle_traceability_report.py \
  5_connectors/adapter/tests/test_data_lifecycle_api.py \
  5_connectors/adapter/__tests__/test_status_read_model.py

git diff --check
```

Result:

- `58 passed`
- no whitespace/check conflict

Commit:

- `c5c004c feat(dlp): add archive candidate plan dry-run skeleton`

---

## 3. Batch 19 Conclusion

- repo reality: **passed**
- running reality: deferred to Batch 21
- fixed statement: **archive candidate plan generated; archive execution not started**
