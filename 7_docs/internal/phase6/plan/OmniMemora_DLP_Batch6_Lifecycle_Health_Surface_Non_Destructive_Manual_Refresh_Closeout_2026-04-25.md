# OmniMemora DLP Batch 6 Closeout - Lifecycle Health Surface + Non-Destructive Manual Refresh (2026-04-25)

## 1. Scope

Batch 6 implements DLP product observability and manual remedy inside `18011`:

- add lifecycle health surface with fixed state set:
  - `healthy / stale_usable / degraded / maintenance_failed / uninitialized`
- add non-destructive manual refresh API:
  - `POST /data-lifecycle/maintenance/refresh`
- keep `/agents/control` schema unchanged (`agents/count/system_status`)
- no `/agents/control` contract expansion
- no `5173` UI implementation in this batch
- no client-memory cleanup logic

---

## 2. Repo Reality (Code + Tests)

### 2.1 Implemented Modules

- `5_connectors/adapter/data_lifecycle/health.py`
  - lifecycle health aggregation
  - fixed output contract: `schema_version=dlp-lifecycle-health-v1`
- `5_connectors/adapter/data_lifecycle/state_store.py`
  - added read-only ledger query methods:
    - `read_recent_records(limit=..., trigger/status optional filter)`
    - `latest_record(trigger/status optional filter)`
  - ledger write format unchanged
- `5_connectors/adapter/data_lifecycle_api.py`
  - `GET /data-lifecycle/status`
  - `POST /data-lifecycle/maintenance/refresh`
- `5_connectors/adapter/application/control_snapshot_cache.py`
  - extracted `/agents/control` snapshot cache holder and invalidation
- `5_connectors/adapter/agent_control_api.py`
  - switched to cache module (module thinning)
- `5_connectors/adapter/main.py`
  - registered `data_lifecycle_api` under read-model/diagnostics surface registration

### 2.2 Repo Tests

Executed:

```bash
python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_api.py
python3 -m pytest -q 5_connectors/adapter/tests/test_data_lifecycle_plane.py
python3 -m pytest -q 5_connectors/adapter/tests/test_agent_control_api.py 5_connectors/adapter/__tests__/test_status_read_model.py
```

Results:

- `8 passed`
- `15 passed`
- `29 passed`

---

## 3. Running Reality (Promotion + Live Endpoint Validation)

### 3.1 Promotion

Executed:

```bash
./tools/promotion/promotion.sh adapter+ui
```

Observed:

- promotion result: `running_reality_promoted`
- log: `tools/verification/logs/promotion_20260425_101601.log`
- adapter restart truth: `changed`

### 3.2 Live Validation (`18011`)

Validated:

- `GET /data-lifecycle/status`
  - returns `schema_version=dlp-lifecycle-health-v1`
- `POST /data-lifecycle/maintenance/refresh`
  - returns `schema_version=dlp-manual-refresh-v1`
  - returned cycle record trigger/status:
    - `trigger=manual_refresh`
    - `status=success`
- post-refresh status shows latest maintenance signal:
  - `maintenance.last_status=success`
  - `maintenance.last_trigger=manual_refresh`
- `GET /agents/control`
  - top-level keys remain:
    - `agents`
    - `count`
    - `system_status`

### 3.3 `/agents/control` Sampling

- 80 samples
- timeout: `0/80`
- error: `0/80`
- latency:
  - `p50=3.94ms`
  - `p95=7.10ms`
  - `max=10.14ms`

---

## 4. Doc Reality

Updated:

- this closeout record
- `7_docs/internal/phase6/plan/README.md` index row for DLP Batch 6

Reality separation for this closeout:

- repo reality: implemented and test-validated
- running reality: promotion + live endpoints validated on `18011`
- doc reality: phase6 index and closeout synchronized

---

## 5. Boundary Confirmation

- implemented inside product boundary `18011`
- no `5173` state-logic definition added
- no ingress/protocol shape change to `/agents/control`
- no destructive maintenance behavior introduced
- no raw evidence deletion path introduced
