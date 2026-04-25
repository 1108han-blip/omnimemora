# OmniMemora DLP Batch 9 Closeout - Storage Pressure Readiness (Inventory-Only) (2026-04-25)

## 1. Scope

Batch 9 adds storage-pressure readiness signals to DLP health surface.

Implemented:

- `storage_pressure=normal/warning/critical`
- storage inventory exposure (tracked files + total bytes)
- recommendation signal for next non-destructive archive-manifest line

Not implemented in this batch:

- no deletion
- no compression
- no archive execution
- no raw evidence mutation

---

## 2. Repo Reality

Updated:

- `5_connectors/adapter/data_lifecycle/health.py`
  - storage inventory collection for DLP/evidence telemetry artifacts
  - pressure classification and recommendation
  - payload extensions:
    - `storage_pressure`
    - `storage.{total_bytes,recommendation,tracked_files,recent_maintenance_scanned_bytes_max}`

Test coverage:

- `5_connectors/adapter/tests/test_data_lifecycle_api.py`
  - verifies storage pressure surfacing
  - verifies inventory-only behavior (no cleanup side-effect)

---

## 3. Running Reality linkage

Batch 8 running validation confirms:

- `GET /data-lifecycle/status` is available in running reality
- current observed `storage_pressure=normal`

---

## 4. Decision for next line

Current output supports explicit go/no-go judgment for a future line:

- if pressure remains `normal`, keep inventory-only mode
- if `warning/critical` persists, open next batch for:
  - non-destructive archive manifest
  - checksum-ready artifact planning
  - still no deletion by default
