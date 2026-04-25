# OmniMemora RES-005 Metrics Residual Meter Read-Path Running Validation Closeout (2026-04-25)

## Fixed Conclusion

`metrics residual meter reads switched to sqlite-first with legacy fallback; status read model remains legacy-authoritative`

## Scope

RES-005 residual switch only:

- switched residual/degraded meter reads in metrics surfaces:
  - recent requests
  - tenant list
  - core capability trend
  - summary/core fallback meter reads
- not switched:
  - DLP summary-first hot path
  - status read model authority
  - request meter path
  - request_evidence path

## Repo Reality

Implemented:

1. `application/metrics_meter_read_resolver.py`
   - mode: `legacy_only | sqlite_first_legacy_fallback`
   - default: `sqlite_first_legacy_fallback`
   - sqlite-first + legacy fallback for residual metrics reads
2. `infrastructure/meter_store_v2.py`
   - query by tenant
   - query by timestamp window (`since_iso`)
   - bounded recent query
   - tenant listing
3. `metrics_service.py`
   - `_collect_meters` / `_collect_meters_24h` via resolver
   - `list_tenants` via resolver
   - `compute_core_capabilities_trend` uses windowed residual collection
   - summary-first hot path unchanged
4. `data_lifecycle/meter_storage_v2.py` + `health.py`
   - status read-path flags include:
     - `metrics_switch_enabled`
     - `metrics_read_mode`
     - `status_read_model_switch_enabled=false`
5. tests:
   - metrics resolver tests
   - meter_store_v2 query/tenant tests
   - metrics summary-first/fallback behavior tests
   - parity/status read-path regression tests

## Running Reality

Date:

- 2026-04-25

Promotion:

- `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- adapter restart truth: `changed`

Validation evidence:

1. Non-Codex request generated via `/memory/query` (`agent=openclaw`)
   - `tenant=res005tenant`
   - `request_id=req-bba632de`
2. `/data-lifecycle/status` read-path flags:
   - `metrics_switch_enabled=true`
   - `metrics_read_mode=sqlite_first_legacy_fallback`
   - `status_read_model_switch_enabled=false`
   - `legacy_fallback_enabled=true`
3. Endpoint checks:
   - `/metrics/summary` -> `200`
   - `/metrics/summary_24h` -> `200`
   - `/metrics/core_capabilities` -> `200`
   - `/metrics/recent_requests?tenant=res005tenant...` -> `200`
   - `/metrics/tenants` -> `200`
   - `/metrics/core_capabilities/trend?tenant=res005tenant&days=7` -> `200`
   - `/debug/request_evidence?request_id=req-bba632de` -> `200`
   - `/requests/req-bba632de/meter` -> `200`
4. SQLite-hit evidence (residual path):
   - `/metrics/recent_requests?tenant=res005tenant...` contains `request_id=req-bba632de`
5. Fallback simulation:
   - delete only this request row from sqlite mirror (`DELETE FROM meter_records WHERE request_id = 'req-bba632de'`)
   - `/metrics/recent_requests?tenant=res005tenant...` still contains `request_id=req-bba632de` (legacy fallback)
6. Parity restore:
   - `POST /data-lifecycle/meter-storage/parity/rebuild` -> `critical_mismatch_count=0`
   - `GET /data-lifecycle/meter-storage/parity` -> `critical_mismatch_count=0`

## Boundary Confirmation

- status read model remains legacy-authoritative
- request_evidence read path unchanged
- request meter read path unchanged
- legacy meter JSON retained
- no legacy meter delete/move/compress/truncate path introduced
