# OmniMemora DLP Batch 7 Closeout - KPI Summary-First Hot-Read Detachment (2026-04-25)

## 1. Scope

Batch 7 moved KPI hot-read endpoints from raw-meter-first to DLP summary-first inside `18011`:

- `/metrics/summary`
- `/metrics/summary_24h`
- `/metrics/core_capabilities`

Boundaries kept:

- no `/agents/control` top-level schema change
- no 5173 data-definition change
- no ingress/user request protocol change

---

## 2. Repo Reality

### 2.1 Code changes

- `5_connectors/adapter/data_lifecycle/summary_builder.py`
  - added precomputed KPI fields in summary contract:
    - `metrics_summary_all`
    - `metrics_summary_24h`
    - `core_capabilities_24h`
  - `builder_version` default upgraded to `dlp-summary-builder-v3`
- `5_connectors/adapter/data_lifecycle/maintenance_manager.py`
  - passes `is_task_non_value` classifier into summary builder
- `5_connectors/adapter/metrics_service.py`
  - switched to summary-first for all three KPI endpoints
  - fallback only when summary is missing/expired/contract-invalid/read-error
  - fallback writes DLP ledger record with `trigger=metrics_read_degraded`

### 2.2 Repo tests

Executed:

```bash
python3 -m pytest -q 5_connectors/adapter/tests/test_metrics_service_summary_first.py
python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_plane.py
python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_api.py 5_connectors/adapter/tests/test_diagnostics_surface_smoke.py
python3 -m pytest -q 5_connectors/adapter/tests/test_agent_control_api.py 5_connectors/adapter/__tests__/test_status_read_model.py
python3 -m pytest -q 5_connectors/adapter/tests/test_main_assembly_smoke.py
```

Results:

- `3 passed`
- `15 passed`
- `11 passed`
- `29 passed`
- `2 passed`

---

## 3. Contract and Compatibility

- metrics endpoint response schema kept unchanged
- DLP summary contract expanded internally for KPI hot-read use
- legacy fallback retained for degraded compatibility only
