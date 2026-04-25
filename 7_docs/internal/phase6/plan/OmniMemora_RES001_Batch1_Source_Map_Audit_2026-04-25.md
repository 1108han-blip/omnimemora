# OmniMemora RES-001 Batch 1 Source Map Audit (2026-04-25)

## Scope

Read-only mapping for raw evidence `writer -> file -> reader -> risk`, focused on:

- `llm_proxy.py`
- `trace_events.py`
- `meter_store.py`
- DLP retention / traceability / archive planning modules

## Source Map

| Writer | File | Primary Readers | Risk |
|---|---|---|---|
| compile event append | `5_connectors/adapter/infrastructure/compile_store.py` (`COMPILE_EVENTS_PATH`) | `status_api.compile_events`, `status_read_model` request evidence build path, `data_lifecycle/retention.py`, `data_lifecycle/traceability.py`, archive planning chain | High: hot evidence source, request evidence dependency |
| proxy event append | `5_connectors/adapter/infrastructure/proxy_store.py` (`EVENTS_PATH`) | `status_api.proxy_events`, `status_read_model` projections, `data_lifecycle/retention.py`, traceability/archive chain | Medium-High: control/KPI reads + lifecycle scans |
| trace event append | `5_connectors/adapter/trace_events.py` (`TRACE_EVENTS_PATH`) | `status_api.trace_events`, DLP retention + traceability + archive transaction/readthrough diagnostics | Medium: diagnostics and traceability chain dependency |
| meter writes | `5_connectors/adapter/infrastructure/meter_store.py` (`meters_index.json`, `meters_*.json`) | status/meter endpoints + DLP retention/archive candidate inventory | High: large-file growth + tenant/index coupling |

## DLP Consumer Map (Current)

| Module | Consumption Mode | Note |
|---|---|---|
| `data_lifecycle/retention.py` | direct file inventory scan | remains inventory-only |
| `data_lifecycle/traceability.py` | request-level sample verification from source evidence | no read-path switch |
| `data_lifecycle/archive_plan.py` | candidate planning from retention + traceability artifacts | dry-run / gate chain only |

## Conclusion

- RES-001 can safely start from raw evidence segmentation with observe-only mirror.
- Legacy source files remain authoritative production read inputs.
- Meter structural split is intentionally deferred to RES-002 due to high coupling/risk.
