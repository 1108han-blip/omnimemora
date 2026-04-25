# OmniMemora DLP Batch 10 Closeout - Retention Manifest Skeleton (2026-04-25)

## 1. Scope

Batch 10 introduces a retention inventory manifest for evidence/telemetry only.

Implemented:

- retention module: `5_connectors/adapter/data_lifecycle/retention.py`
- manifest file path: `~/.omnimemora/adapter/data_lifecycle/retention_manifest.json`
- fixed schema: `dlp-retention-manifest-v1`
- mode fixed to `inventory_only`

No archive/compress/delete/move behavior was added.

---

## 2. Manifest Contract

Top-level fields:

- `schema_version`
- `manifest_id`
- `generated_at`
- `mode`
- `artifacts[]`
- `summary`
- `warnings[]`

Per artifact fields:

- `name`
- `kind`
- `path`
- `exists`
- `bytes`
- `sha256`
- `mtime`
- `line_count`
- `traceability_keys`
- `eligible_for_future_archive`

---

## 3. Inventory Coverage

Inventory targets are product evidence/telemetry only:

- compile events
- proxy events
- trace events
- meter index + tenant meter files
- DLP summary
- DLP ledger

Excluded:

- Product Memory content
- Client Memory
- user-side directories

---

## 4. Engineering Guarantees

- manifest write uses temp + rename (`write_manifest_atomic`)
- missing files are recorded with `exists=false` and warning entries
- invalid JSON/JSONL content does not fail manifest generation (line-count/hash path is tolerant)
