# OmniMemora DLP Batch 11 Closeout - Retention API + Health Integration (2026-04-25)

## 1. Scope

Batch 11 exposes retention manifest via product API and health surface.

API additions:

- `GET /data-lifecycle/retention/manifest`
  - returns latest manifest
  - returns `{schema_version, status:\"missing\"}` when absent
- `POST /data-lifecycle/retention/manifest/rebuild`
  - explicit rebuild only
  - writes ledger with `trigger=retention_manifest_rebuild`

Health addition (`GET /data-lifecycle/status`):

- `retention_manifest.status`
- `retention_manifest.generated_at`
- `retention_manifest.artifact_count`
- `retention_manifest.total_bytes`
- `retention_manifest.warnings_count`

---

## 2. Non-Goals Preserved

- no `/agents/control` schema changes
- no metrics endpoint schema changes
- no UI expansion into rule-definition layer
- no destructive retention endpoint

---

## 3. Repo Validation (Batch 11 + dependent tests)

Key tests passed:

- retention manifest API missing/read/rebuild behavior
- health surface retention summary projection
- existing DLP health/status tests
- metrics summary-first regression and read-model regression
