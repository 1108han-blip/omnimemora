# OmniMemora

OmniMemora is a local LLM gateway with a UI-controlled agent integration model. `:5173` is the user control entry, and `http://127.0.0.1:18011` is the only product data entry when routing is enabled.

## Current Shape

| Surface | Role | Status |
|--------|------|--------|
| `:5173` | Dashboard | User control entry |
| `:18011` | Gateway | Only product data entry when routing is enabled |
| `:8765` | Go runtime | Internal memory plane |

```text
Agent -> Gateway (:18011) -> compile/recall/inject -> Upstream LLM
                               |
                               -> Runtime (:8765)
```

## Frozen Truth

- `:5173` is the only user control entry.
- `:18011` remains the only product data entry when routing is enabled.
- Runtime is internal only.
- `/metrics/summary` is the only KPI truth surface.
- Adapter-to-runtime contract changes must pass contract tests.
- Agent control lives in the UI at `:5173`, not in agent self-selection.
- Agent integration is two-layer:
  - `使用 OmniMemora`: high-frequency routing switch
  - `接入 OmniMemora`: low-frequency install/uninstall switch
- When routing is off, requests may still enter `:18011`, but the gateway must stay in transparent passthrough mode.
- Agent detection must not auto-attach or auto-enable routing.
- Parent cards are the control granularity; temporary subagents are runtime-visible but not independent control cards.
- Pure local mode keeps cloud updates and usage reporting off by default.
- Enabling cloud policy updates implies minimal telemetry upload for policy quality improvement.

Start here:

- [0_blueprint/PRODUCT_DEFINITION.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_DEFINITION.md)
- [0_blueprint/DEFAULT_IN_CONTROL_PLANE.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/DEFAULT_IN_CONTROL_PLANE.md)
- [9_adr/ADR-0003-interface-access-paths.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/9_adr/ADR-0003-interface-access-paths.md)
- [7_docs/internal/phase5/README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/README.md)

## Quick Start

```bash
./start.sh
```

Healthy startup means:

- gateway health passes on `:18011`
- startup does not print false `[OK]`
- timeout or child failure exits non-zero
- detected agents may appear in the UI, but default control state stays off until the user enables it

## Metrics Truth Surface

| Endpoint | Role |
|---------|------|
| `/metrics/summary` | KPI truth |
| `/proxy/status` | Diagnostics |
| `/compile/status` | Diagnostics |
| `/agents/live` | Diagnostics |
| `/agents/metrics` | Diagnostics |

If KPI and diagnostics disagree, trust `/metrics/summary` first.

## Repository Layout

| Path | Role |
|------|------|
| `5_connectors/adapter/` | Active gateway and adapter code |
| `4_core/local-runtime/` | Internal memory plane |
| `6_console/demo-dashboard/` | Dashboard |
| `docs/audit/2026-04-16_gateway_reconciliation/` | Current audit baseline |
| `7_docs/internal/archive/` | Historical plans and retired phase docs |
| `5_connectors/archive/` | Archived plugin experiments |
| `4_core/adapter-raw/` | Archived legacy Python adapter line |

## Non-Goals

- not a multi-entry product
- not a plugin-first product surface
- not a runtime-direct product
- not a second control plane beside the gateway
- not an auto-attach or silent-takeover product
