# OmniMemora DLP Batch 47 - Non-Active Candidate API Health Surface Closeout

Date: 2026-04-25

## Scope

Batch 47 exposes the non-active candidate selector on the `18011` DLP read/diagnostic surface.

No UI control, execute endpoint, source move, delete, or compression path is added.

## Repo Reality

- Commit: `70568f2 feat(dlp): expose non-active candidate report surface`
- Added endpoints:
  - `GET /data-lifecycle/archive/non-active-candidates/report`
  - `POST /data-lifecycle/archive/non-active-candidates/report/rebuild`
- Added `/data-lifecycle/status.archive_non_active_candidates` summary.

## Guardrails

- The surface is report-only.
- Tests assert no `execute` or `move-one` endpoint exists for non-active candidates.
- The selector is advisory for later quarantine planning and does not authorize movement by itself.

## Validation

- API + selector tests: `57 passed`
- Stage 14 regression set: `121 passed`
- `git diff --check`: passed before commit.

## Conclusion

Batch 47 is closed at repo reality. The selector report can now be generated and inspected through `18011` without adding destructive capability.
