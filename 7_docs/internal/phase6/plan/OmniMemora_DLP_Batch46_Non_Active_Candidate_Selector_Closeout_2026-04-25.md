# OmniMemora DLP Batch 46 - Non-Active Candidate Selector Closeout

Date: 2026-04-25

## Scope

Batch 46 adds a report-only selector that separates archive-eligible artifacts from quarantine-safe non-active candidates.

The selector does not move, delete, compress, or rewrite source evidence.

## Repo Reality

- Commit: `4b689b4 feat(dlp): add non-active archive candidate selector`
- Added:
  - `5_connectors/adapter/data_lifecycle/archive_non_active_candidates.py`
  - `5_connectors/adapter/tests/test_data_lifecycle_archive_non_active_candidates.py`
- Extended DLP policy with `archive_non_active_candidate_report_file`.

## Contract

- Schema: `dlp-non-active-candidate-report-v1`
- Mode: `non_active_selection_report_only`
- Candidate status values:
  - `forbidden`
  - `plausible_non_active`
  - `review_required`
- Explicitly blocks active/hot/control candidates by kind and basename.
- Allows archive pilot copies to appear as `archive_pilot_copy` only when checksum lineage is intact.
- Emits `source_move_delete_compress_executed=false` in the summary.

## Validation

- Selector test: `6 passed`
- Stage 14 regression set later passed with `121 passed`.

## Conclusion

Batch 46 is closed at repo reality. The product now has a second safety filter after archive eligibility and before any future quarantine action.
