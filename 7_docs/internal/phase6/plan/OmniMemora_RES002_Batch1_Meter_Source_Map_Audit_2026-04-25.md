# OmniMemora RES-002 Batch 1 Meter Source Map Audit (2026-04-25)

## Scope

Read-only mapping for meter paths:

- writer
- legacy files
- readers
- hot paths
- risk

## Writer to File to Reader Map

| Writer | Legacy File | Reader / Consumer | Hot Path | Risk |
|---|---|---|---|---|
| `infrastructure/meter_store.py::store_meter()` (called by `main.py`, `compile_orchestrator.py`, `ingress/llm_proxy.py`) | `meters_index.json` | `get_meter()` -> `status_read_model.build_request_evidence_payload()` | `/requests/{id}/meter`, `request_evidence` build path | High: request-level evidence dependency |
| `infrastructure/meter_store.py::store_meter()` | `meters_*.json` | `get_tenant_usage()`, `metrics_service` legacy fallback collectors | `/metrics/summary*`, `/metrics/core_capabilities` fallback path | High: KPI fallback dependency |
| `infrastructure/meter_store.py::_flush_pending_persistence()` | `meters_index.json` + `meters_*.json` | `data_lifecycle/retention.py` inventory | DLP retention manifest chain | Medium-High: inventory truth coupling |
| legacy meter files (read-only in this line) | `meters_index.json` + `meters_*.json` | `archive_non_active_candidates.py`, `archive_quarantine.py`, related DLP safety modules | archive-readiness / quarantine candidate checks | Medium: governance chain dependency |

## Current Contract Conclusions

1. Legacy meter JSON is production authoritative for request-meter and request-evidence surfaces.
2. DLP and metrics have direct legacy meter dependency, so read-path switch must be decoupled and gated separately.
3. RES-002 should introduce mirror/parity first, without mutating legacy storage lifecycle.

## RES-002 Batch 1 Risks

- **Read-path coupling risk:** `request_evidence` and status read model depend on legacy meter truth.
- **Fallback KPI risk:** metrics fallback still scans in-memory aggregates loaded from legacy files.
- **Governance scan risk:** DLP retention/archive modules inventory legacy files directly.

## Batch 1 Decision

- Proceed with `meter_store_v2` mirror introduction in observe-only mode.
- Keep legacy source untouched.
- Defer production read-path switch until parity/running validation gates pass.
