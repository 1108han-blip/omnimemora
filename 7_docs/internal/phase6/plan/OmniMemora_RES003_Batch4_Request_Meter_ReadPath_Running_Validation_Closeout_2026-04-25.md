# OmniMemora RES-003 Request Meter Read-Path Running Validation Closeout (2026-04-25)

## Fixed Conclusion

`request meter read path switched to sqlite-first with legacy fallback; request_evidence and metrics remain legacy-authoritative`

## Scope

RES-003 narrow switch only:

- switched: `GET /requests/{request_id}/meter`
- not switched: `request_evidence`, metrics, status read model

## Repo Reality

Implemented:

1. `application/request_meter_read_resolver.py`
   - mode: `legacy_only | sqlite_first_legacy_fallback`
   - default: `sqlite_first_legacy_fallback`
   - sqlite-first + legacy fallback with degraded ledger recording
2. `usage_surface.py`
   - `/requests/{request_id}/meter` uses resolver
   - response headers:
     - `x-omnimemora-meter-read-mode`
     - `x-omnimemora-meter-read-source`
3. `data_lifecycle/meter_storage_v2.py` + health projection
   - read-path flags exposed:
     - `request_meter_switch_enabled`
     - `request_evidence_switch_enabled`
     - `metrics_switch_enabled`
     - `legacy_fallback_enabled`
4. tests:
   - resolver unit tests
   - usage route tests
   - parity/status regression tests

## Running Reality

Date:

- 2026-04-25

Promotion:

- `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- restart truth: `changed`

Validation evidence:

1. `/data-lifecycle/status`:
   - `meter_storage_v2.read_path.request_meter_switch_enabled=true`
   - `request_evidence_switch_enabled=false`
   - `metrics_switch_enabled=false`
   - `legacy_fallback_enabled=true`
   - `request_meter_read_mode=sqlite_first_legacy_fallback`
2. Non-Codex request generated via `/memory/query` (`agent=openclaw`), request_id: `req-8fbc2991`
3. `/requests/req-8fbc2991/meter` first read:
   - HTTP 200
   - `x-omnimemora-meter-read-source: sqlite`
4. Forced sqlite-miss validation (single request row removed from sqlite mirror only, legacy untouched):
   - `/requests/req-8fbc2991/meter` HTTP 200
   - `x-omnimemora-meter-read-source: legacy_fallback`
   - response body shape unchanged
5. `/debug/request_evidence?request_id=req-8fbc2991`:
   - HTTP 200
6. parity:
   - `POST /data-lifecycle/meter-storage/parity/rebuild` -> `critical_mismatch_count=0`
   - `GET /data-lifecycle/meter-storage/parity` -> `critical_mismatch_count=0`
7. smoke:
   - `/agents/control` 200
   - `/metrics/summary` 200
   - `/metrics/summary_24h` 200
   - `/metrics/core_capabilities` 200

## Boundary Confirmation

- request_evidence remains legacy-authoritative
- metrics remain legacy-authoritative
- no implicit status read-model migration
- no legacy meter file delete/move/compress/truncate
