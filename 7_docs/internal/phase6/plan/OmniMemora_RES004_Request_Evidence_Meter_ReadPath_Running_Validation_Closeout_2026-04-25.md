# OmniMemora RES-004 Request Evidence Meter Read-Path Running Validation Closeout (2026-04-25)

## Fixed Conclusion

`request_evidence meter read path switched to sqlite-first with legacy fallback; metrics and status read model remain legacy-authoritative`

## Scope

RES-004 narrow switch only:

- switched: `GET /debug/request_evidence`
- not switched: `build_context_diff_payload`, metrics read model, status read model authority

## Repo Reality

Implemented:

1. `application/request_evidence_meter_read_resolver.py`
   - mode: `legacy_only | sqlite_first_legacy_fallback`
   - default: `sqlite_first_legacy_fallback`
   - sqlite-first selection + legacy fallback
2. `application/status_read_model.py`
   - keeps `build_request_evidence_payload()` legacy-compatible
   - adds resolved request-evidence builder with shadow parity output:
     - `request_evidence_meter_read`
     - `request_evidence_meter_shadow`
3. `diagnostics_surface.py`
   - `/debug/request_evidence` uses resolved path only
   - response headers:
     - `x-omnimemora-request-evidence-meter-read-mode`
     - `x-omnimemora-request-evidence-meter-read-source`
     - `x-omnimemora-request-evidence-meter-shadow-status`
4. tests:
   - resolver tests
   - route/header + fallback + compatibility tests
   - status_read_model/request_evidence/meter parity/safety regression set

## Running Reality

Date:

- 2026-04-25

Promotion:

- `./tools/promotion/promotion.sh adapter+ui`
- result: `running_reality_promoted`
- adapter restart truth: `changed`

Validation evidence:

1. Non-Codex request generated via `/memory/query` (`agent=openclaw`)
   - `request_id=req-35c5c90f`
2. `/debug/request_evidence?request_id=req-35c5c90f` sqlite-hit check:
   - HTTP `200`
   - `x-omnimemora-request-evidence-meter-read-mode=sqlite_first_legacy_fallback`
   - `x-omnimemora-request-evidence-meter-read-source=sqlite`
   - `x-omnimemora-request-evidence-meter-shadow-status=passed`
   - core fields present: identity/access_plan/actual_enforcement/context/status
3. Fallback simulation (delete only this request row from sqlite mirror; legacy JSON untouched):
   - `/debug/request_evidence?request_id=req-35c5c90f` HTTP `200`
   - `x-omnimemora-request-evidence-meter-read-source=legacy_fallback`
   - `x-omnimemora-request-evidence-meter-shadow-status=degraded`
   - response body shape remains compatible
4. Parity restore:
   - `POST /data-lifecycle/meter-storage/parity/rebuild` -> `critical_mismatch_count=0`
   - `GET /data-lifecycle/meter-storage/parity` -> `critical_mismatch_count=0`
5. Smoke:
   - `/requests/req-35c5c90f/meter` -> `200`
   - `/metrics/summary` -> `200`
   - `/metrics/summary_24h` -> `200`
   - `/metrics/core_capabilities` -> `200`
   - `/agents/control` -> `200`

## Boundary Confirmation

- metrics read path remains legacy-authoritative
- status read model authority remains legacy-authoritative
- `build_context_diff_payload` continues to use legacy meter getter path
- legacy meter files retained
- no legacy meter delete/move/compress/truncate path introduced
