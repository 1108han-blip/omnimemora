# Phase 5 Docs Index

## Active Docs

- [云端小工程](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/云端小工程.md)
- [OmniMemora OpenClaw-first Real Client Recovery + Visual Validation 执行计划](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_OpenClaw_First_Real_Client_Recovery_Visual_Validation_执行计划_2026-04-19.md)
- [OmniMemora OpenClaw-first Real Client Recovery + Visual Validation Runbook](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_OpenClaw_First_Real_Client_Recovery_Visual_Validation_Runbook_2026-04-19.md)
- [OmniMemora 验证对象登记与验收记录](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)
- [OmniMemora Decision Carrier / Control-Plane Decoupling Bounded Scan](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Decision_Carrier_Control_Plane_Decoupling_Bounded_Scan_2026-04-18.md)

## Current Phase Boundary

- 当前执行主线：`OpenClaw-first Real Client Recovery + Visual Validation`
- 阶段状态：**已收口**
- 当前阶段结论：
  - `Decision Carrier / Control-Plane Decoupling` 已阶段性完成并转为结构前置成果
  - `5173` 已恢复为正式用户控制入口
  - `OpenClaw` 已完成接入层 / 路由层控制闭环
  - OpenClaw 的”安装成立”标准已升级为：`MCP 接入 + main 实际生效请求入口接入 18011`
  - OpenClaw 的 MCP 运行期端点已定位为 `/sse`；`/mcp` 不再作为其唯一正确 attach 入口
  - OpenClaw marker 已迁移到独立文件 `~/.openclaw/.omnimemora.attach.marker`，解决 CLI schema 冲突
  - 真实 OpenClaw 请求已进入 `18011`
  - `route off -> agent_route_disabled` 语义成立
  - `route on -> runtime_compile` 语义成立
  - 当前阶段结论覆盖控制面、接入层、路由层与真实请求路径
  - 当前主线不拆 `trial / internal admin surface`
  - 当前主线不做 GUI 物理独立
  - `active / last_seen_at` 不一致是后续独立主线，不影响本阶段完成结论

## 下一阶段候选

- `Control Activity Semantics`（默认推荐）：修 `active / last_seen_at` 语义
- `Claude Code Cross Validation`：Claude Code 第二验证面交叉验证

明确排除：继续改 OpenClaw attach、GUI 物理独立、`trial / internal admin`、compile/strategy 大拆

## Supplemental Docs

- [OmniMemora V2遗产映射与后备优化清单](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_V2遗产映射与后备优化清单_2026-04-18.md)

## Archived Phase 5 Convergence Docs

- [Archive Folder](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/archive/2026-04-18-phase5-convergence)
- [Phase 5.5 Product Hardening Archive](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/archive/2026-04-18-phase5_5-product-hardening)

Only the files listed under `Active Docs` should be treated as current execution docs.
