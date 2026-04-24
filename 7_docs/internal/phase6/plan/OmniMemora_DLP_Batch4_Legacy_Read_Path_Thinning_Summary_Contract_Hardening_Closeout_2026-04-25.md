# OmniMemora DLP Batch 4 Closeout - Legacy Read-Path Thinning and Summary Contract Hardening (2026-04-25)

## 1. Summary

Batch 4 advances `/agents/control` read model from generic summary-first fallback into contract-first semantics:

- summary payload contract metadata is hardened
- read model path is explicit: `fresh summary` -> `stale summary` -> `legacy fallback (degraded)`
- legacy fallback usage is recorded as degraded path in DLP state ledger
- duplicated normalization / compile-summary / traffic-truth logic is reduced by reusing `data_lifecycle.summary_builder`

Batch boundary preserved:

- no destructive maintenance
- no UI changes
- no user-side memory access
- `/agents/control` response schema unchanged

---

## 2. Repo Changes

### 2.1 Summary contract hardening

Updated:

- `5_connectors/adapter/data_lifecycle/summary_builder.py`

Contract fields now include:

- `schema_version`
- `generated_at`
- `source_counts`
- `builder_version`
- `families`
- optional `degraded_reason`

Also exported shared contract logic:

- `normalize_agent_to_family(...)`
- `summarize_compile_rows_for_family(...)`
- `derive_traffic_truth_from_counts(...)`

### 2.2 Read-path thinning and degraded fallback recording

Updated:

- `5_connectors/adapter/application/status_read_model.py`

Key changes:

- summary contract validation gate before use
- explicit summary path classification:
  - fresh summary path
  - stale summary path
  - legacy fallback path
- legacy fallback path emits degraded record (throttled) to DLP state ledger via trigger `read_model_degraded`
- duplicated reason-set and traffic derivation logic moved to summary builder shared functions

### 2.3 Contract and equivalence tests

Updated:

- `5_connectors/adapter/tests/test_data_lifecycle_plane.py`

Added/extended tests:

- summary contract metadata presence and optional degraded_reason
- summary path vs legacy path key-field equivalence
- legacy fallback degraded reason recording

---

## 3. Validation

Executed:

```bash
python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_plane.py
python3 -m pytest -q 5_connectors/adapter/__tests__/test_status_read_model.py
python3 -m pytest -q 5_connectors/adapter/tests/test_agent_control_api.py
```

Results:

- `test_data_lifecycle_plane.py`: `13 passed`
- `test_status_read_model.py`: `21 passed`
- `test_agent_control_api.py`: `7 passed`

---

## 4. Acceptance Check

- `/agents/control` response schema unchanged: **PASS**
- `status_read_model.py` duplicated aggregation/normalization logic reduced: **PASS**
- summary contract independently expresses control-plane needed fields: **PASS**
- legacy fallback remains available but explicitly marked as degraded path: **PASS**
- destructive maintenance remains deferred: **PASS**

---

## 5. Conclusion

Batch 4 is closed as contract-hardening + read-path-thinning implementation, with degraded fallback made explicit and observable, while preserving existing control API schema and non-destructive lifecycle constraints.
