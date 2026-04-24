# OmniMemora DLP Batch 2 Closeout - Non-Destructive Auto Maintenance and Summary Warming (2026-04-25)

## 1. Summary

Batch 2 implements non-destructive autonomous maintenance on top of DLP Batch 1:

- adapter startup now schedules a delayed `startup_warm` maintenance cycle
- low-frequency `interval_refresh` maintenance runs are enabled
- maintenance singleflight is enforced to prevent concurrent rebuild cycles
- maintenance budget overrun is recorded as failed ledger and does not block request path
- status read model remains schema-stable and now reads in order:
  - fresh summary
  - stale-but-usable summary
  - legacy fallback path

This batch does **not** introduce destructive maintenance. Raw evidence delete/archive/compact remains deferred.

---

## 2. Repo Reality (Implemented)

### 2.1 New module

- `5_connectors/adapter/data_lifecycle/scheduler.py`
  - startup delayed warm cycle
  - periodic interval refresh
  - async singleflight around scheduler-triggered runs
  - non-blocking execution via `asyncio.to_thread`

### 2.2 Existing modules updated

- `5_connectors/adapter/data_lifecycle/policy.py`
  - adds scheduler/budget/stale-window policy fields and env overrides
- `5_connectors/adapter/data_lifecycle/summary_store.py`
  - adds stale-but-usable summary read (`read_stale_usable_summary`)
- `5_connectors/adapter/data_lifecycle/maintenance_manager.py`
  - adds manager-level singleflight lock
  - adds budget guard (`maintenance_budget_seconds`) with failed-ledger record on exceed
- `5_connectors/adapter/application/status_read_model.py`
  - reads summary in order fresh -> stale usable -> legacy fallback
  - `/agents/control` response schema remains unchanged
- `5_connectors/adapter/main.py`
  - startup/shutdown hook for DLP scheduler lifecycle

### 2.3 Tests updated/added

- `5_connectors/adapter/tests/test_data_lifecycle_plane.py`
  - startup warm invocation
  - interval refresh invocation
  - manager singleflight behavior
  - budget exceed -> failed ledger
  - stale summary read behavior
  - summary-first + legacy fallback regressions kept

---

## 3. Validation

Executed repo tests only (no promotion/live validation in this batch):

```bash
python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_plane.py
python3 -m pytest -q 5_connectors/adapter/__tests__/test_status_read_model.py
python3 -m pytest -q 5_connectors/adapter/tests/test_agent_control_api.py
```

---

## 4. Boundary and Non-Goals Check

- No `/agents/control` response schema changes.
- No destructive raw evidence maintenance.
- No product core memory deletion/archival.
- No user-side memory read/write/cleanup.
- No 5173 control-plane expansion in this batch.
- No promotion and no running-reality declaration in this closeout.

---

## 5. Current Conclusion

DLP moves from callable skeleton to autonomous non-destructive maintenance operation in adapter runtime, while preserving existing API schema and keeping destructive lifecycle actions deferred to future gated batches.
