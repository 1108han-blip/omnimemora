# OmniMemora RES-027C Meter Parity Contract Repair Closeout (2026-04-27)

## Fixed Conclusion

`meter parity contract separates semantic provenance drift from critical business drift; cleanup scope expansion not started`

## Scope

RES-027C fixes the parity judgment contract, not execution. The change separates provenance-only metadata differences from critical business field drift, so that `sharing_policy_source` differences (and nested `access_plan.sharing_policy_source`) no longer block the second pilot even when raw hashes disagree.

Explicitly excluded:
- second-file source move execution
- cleanup scope expansion
- RES-028

## Change Summary

### Parity Contract Change (`meter_storage_v2.py`)

Added a critical-business hash alongside the existing raw hash:
- `payload_hash_mismatch_count` — raw hash mismatch total (diagnostic, backward-compatible)
- `semantic_hash_mismatch_count` — raw mismatch where critical hashes agree (provenance-only)
- `critical_payload_hash_mismatch_count` — raw mismatch where critical hashes disagree (business drift)
- `critical_mismatch_count = missing_in_sqlite + missing_in_legacy + critical_payload_hash_mismatch_count`

Provenance-only fields excluded from critical hash:
- `sharing_policy_source` (top-level)
- `access_plan.sharing_policy_source` (nested)

`hash_mismatch_samples` entries gain:
- `classification`: `"critical"` or `"provenance_only"`
- `noncritical_field_paths`: list of provenance-only field paths that differ

Downstream gates (cleanup preview, scaleup readiness, second-file proposal) continue to use `critical_mismatch_count` only — `semantic_hash_mismatch_count > 0` does not auto-allow execution.

### Test Coverage

- `test_parity_detects_provenance_only_diff_status_passed`: raw mismatch > 0, semantic > 0, critical = 0, status passed — `request_id=8e1ddda147d6` as concrete sample
- `test_parity_detects_provenance_only_nested_diff_status_passed`: `access_plan.sharing_policy_source` nested case
- `test_parity_detects_business_field_diff_status_degraded`: business field diff blocks parity pass
- `test_parity_missing_in_sqlite_counts_critical`: missing in SQLite counts in critical mismatch
- `test_parity_missing_in_legacy_counts_critical`: missing in legacy counts in critical mismatch
- Regression: cleanup preview / scaleup readiness / second-file proposal all still use `critical_mismatch_count`

## Regression Verification

All downstream gates confirmed unchanged:
- `meter_cleanup_preview.build_preview()` reads `parity.get("critical_mismatch_count")` — unchanged
- `meter_cleanup_scaleup_readiness.build_scaleup_readiness_report()` blocks on `critical_mismatch_count != 0` — unchanged
- `meter_cleanup_second_file_pilot_proposal.build_proposal()` blocks on `critical_mismatch_count != 0` — unchanged

All 137 related tests pass.

## Final Boundary Check

- parity judgment contract repaired
- `sharing_policy_source` and `access_plan.sharing_policy_source` classified as provenance-only, not blocking
- cleanup scope expansion not started
- RES-028 not opened
- second-file execution not started
