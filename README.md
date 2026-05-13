# OmniMemora

OmniMemora is a local LLM gateway with a desktop-GUI-controlled agent integration model. The current user control/display surface is the packaged OmniMemora Desktop app. `http://127.0.0.1:18011` is the only product data entry when routing is enabled. `:5173` is a legacy browser dashboard/dev surface and is not required by the desktop GUI.

## Current Shape

| Surface | Role | Status |
|--------|------|--------|
| OmniMemora Desktop app | GUI | Current user control/display entry |
| `:5173` | Legacy dashboard | Dev/legacy only; not required by current desktop GUI |
| `:18011` | Gateway | Only product data entry when routing is enabled |
| `:8765` | Go runtime | Internal memory plane |

```text
Agent -> Gateway (:18011) -> compile/recall/inject -> Upstream LLM
                               |
                               -> Runtime (:8765)
```

## Cloud Split (Current Product)

| Layer | Responsibility | Not Responsible |
|------|----------------|-----------------|
| Cloudflare (`doloclaw.com`) | External domain entry, control-plane API/auth/tenant/billing/policy-access, candidate fetch entry | Cloud memory plane, cloud compile engine, `/memory/*` primary write/read/delete |
| Railway | Recommendation candidate snapshot/state storage, lightweight async aggregation jobs | `/memory/*` primary path, main compile path |
| Local (`18011` + `8765`) | Active/fallback execution truth, promotion-controlled active policy | Remote override of local active |

## Frozen Truth

- OmniMemora Desktop app is the current user control/display entry.
- `:5173` is legacy/dev-only and must not be treated as a required desktop GUI dependency.
- `:18011` remains the only product data entry when routing is enabled.
- Runtime is internal only.
- `/metrics/core_capabilities` is the current MVP savings truth surface (`real_input_v1`); `/metrics/summary` may return degraded no-historical-scan status.
- Adapter-to-runtime contract changes must pass contract tests.
- Agent control lives in the desktop GUI, not in agent self-selection.
- Agent integration is two-layer:
  - `使用 OmniMemora`: high-frequency routing switch
  - `接入 OmniMemora`: low-frequency install/uninstall switch
- Codex `接入 OmniMemora` prepares an OmniMemora-managed profile/launcher and must not rewrite the official `~/.codex/config.toml`; legacy provider rewrites remain removable/restorable only for backward compatibility.
- When routing is off, requests may still enter `:18011`, but the gateway must stay in transparent passthrough mode.
- Agent detection must not auto-attach or auto-enable routing.
- Parent cards are the control granularity; temporary subagents are runtime-visible but not independent control cards.
- Pure local mode keeps cloud updates and usage reporting off by default.
- Enabling cloud policy updates implies minimal telemetry upload for policy quality improvement.

## Current Phase

正式 roadmap phase：**Phase 7（当前主线：Structured Compile MVP）**（见 `0_blueprint/ROADMAP.md`）

> **Phase 标签说明**：`7_docs/internal/phase6/` 为 **internal historical workstream**，已收口并保留为治理/发布历史索引。当前产品能力工程入口是 `7_docs/internal/structured_compile/README.md`。
> **下一正式阶段**：Phase 8（Token Intelligence Lite）已作为下一阶段固定在 roadmap，用于解释 token 花费、诊断浪费、推荐优化并证明实际节省。Phase 8 不得退化为普通 usage dashboard，也不得扩张为用户画像。

Start here:

- [0_blueprint/ROADMAP.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/ROADMAP.md) — 正式 roadmap SSOT
- [7_docs/internal/structured_compile/README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/structured_compile/README.md) — 当前结构化编译主线
- [7_docs/internal/token_intelligence/README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/token_intelligence/README.md) — 下一阶段 Token Intelligence Lite 主线
- [0_blueprint/PRODUCT_DEFINITION.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_DEFINITION.md)
- [0_blueprint/PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md)
- [9_adr/ADR-0003-interface-access-paths.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/9_adr/ADR-0003-interface-access-paths.md)
- [9_adr/ADR-0002-cloud-refactor.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/9_adr/ADR-0002-cloud-refactor.md)

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
| `/metrics/core_capabilities` | Current MVP savings truth (`real_input_v1`) |
| `/metrics/summary` | Legacy/aggregate summary; may be degraded when historical scans are intentionally skipped |
| `/proxy/status` | Diagnostics |
| `/compile/status` | Diagnostics |
| `/agents/live` | Diagnostics |
| `/agents/metrics` | Diagnostics |

If current MVP savings UI and historical summary disagree, trust `/metrics/core_capabilities` for real-input token savings.

## Repository Layout

| Path | Role |
|------|------|
| `5_connectors/adapter/` | Active gateway and adapter code |
| `4_core/local-runtime/` | Internal memory plane |
| `6_console/demo-dashboard/` | Dashboard |
| `7_docs/internal/structured_compile/` | Current structured compile mainline |
| `7_docs/internal/token_intelligence/` | Next Token Intelligence Lite mainline |
| `7_docs/internal/phase6/plan/` | Closed phase6 workstream and post-close governance records |
| `5_connectors/archive/` | Archived connector/plugin experiments |

## Non-Goals

- not a multi-entry product
- not a plugin-first product surface
- not a runtime-direct product
- not a second control plane beside the gateway
- not an auto-attach or silent-takeover product
- not a cloud-hosted primary memory plane

## Governance

- [3_governance/AUDIT_SCHEME.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/3_governance/AUDIT_SCHEME.md) — 审计触发规则、执行骨架、结论路由
- [7_docs/internal/phase6/plan/OmniMemora_Cloud_Local_Sync_Check_2026-04-30.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase6/plan/OmniMemora_Cloud_Local_Sync_Check_2026-04-30.md) — 云端-本地同步核对记录（2026-04-30）
- [docs/spec/OMNIMEMORA_MVP_PROMO_2026-04-30.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/docs/spec/OMNIMEMORA_MVP_PROMO_2026-04-30.md) — 闭源受控发布宣传文案草案（MVP）

> **Phase 标签说明**：内部执行阶段标签（如 `internal Phase 6 workstream`）只表示执行 workstream。正式产品阶段以 `0_blueprint/ROADMAP.md` 为准。
