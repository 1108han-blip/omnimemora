---
doc_id: RUNBOOK-PHASE5-OPENCLAW-FIRST-REAL-CLIENT-RECOVERY-2026-04-19
title: OmniMemora OpenClaw-first Real Client Recovery + Visual Validation Runbook
owner: arch-lead
reviewers: [product-lead]
status: completed
version: 1.0.0
effective_date: 2026-04-19
depends_on:
  - PLAN-PHASE5-OPENCLAW-FIRST-REAL-CLIENT-RECOVERY-2026-04-19
supersedes: []
last_verified_commit: ""
---

# OmniMemora OpenClaw-first Real Client Recovery + Visual Validation Runbook

## 当前 Gate

- `Track A`: 已完成
- `Track B`: 已完成
- `Track C`: 已完成
- `Track D`: 已完成
- `Track E`: 已完成（OpenClaw 接入层 / 路由层主验证面）
- **阶段状态**：已收口（RECORD-B-065）

## 当前执行顺序（已全部完成）

1. 候选实例 `18041` 已对齐到当前仓库现实，并稳定暴露 `/agents/control*`
2. `5173` 深链与装配已修复，`/` 与 `/agents` 均可稳定访问
3. 正式控制卡已落地，`install/uninstall` 与 `enable/disable` 已进入正式用户控制入口
4. 控制契约已对齐，`/metrics/summary` 与 `/agents/control*` 不再依赖失效实现
5. OpenClaw-first 已完成一轮接入 / 路由 / 恢复 / 退出控制闭环，且可用性断点已完成定位
6. **Marker 存储修复**：marker 已从 `openclaw.json` 根键迁移到独立文件 `~/.openclaw/.omnimemora.attach.marker`，解决 CLI config schema 冲突
7. **Runtime 部署**：新代码已编译部署到 `~/.omnimemora/service/current/tools/omnimemora-runtime`
8. **真实请求验证**：真实 OpenClaw CLI 请求进入 `18011`，route off/on 语义分别对应 `agent_route_disabled` 和 `runtime_compile`

## 当前规则

- 本阶段 UI 结论只绑定候选实例
- `5173` 是正式用户控制入口，不再只做观测 dashboard
- `install/uninstall` = 接入层
- `enable/disable` = 路由层
- OpenClaw `installed=true` 必须同时满足：
  - `mcp.servers.omnimemora` 已建立
  - `main` 实际生效 provider 入口已指向 `18011`
- 对 OpenClaw 当前客户端，MCP attach 运行期优先使用 `/sse` 兼容入口；`/mcp` 仍可作为产品 HTTP JSON-RPC 入口，但不能再当作 OpenClaw 的唯一 SSE 真相
- OpenClaw attach 采用“分层保守”：
  - `openclaw.json` = 全局默认层
  - `agents/main/agent/models.json` = agent 覆盖层
  - install 只修改当前实际生效层
- `OpenClaw` 是主测试面
- `Claude Code` 是补充验证面
- `Codex` 不参与实例测试
- 不得把 install/uninstall + enable/disable 闭环直接写成“已可使用产品”
- `installed`、`routing_enabled`、`active` 必须分开陈述，不得混写成单一“可用”结论

## 当前阶段结论

- `Track A`：候选实例 `18041` 当前稳定暴露 `GET /agents/control`、`POST /agents/control/rescan`、`POST /agents/control/install`、`POST /agents/control/uninstall`、`POST /agents/control/enable`、`POST /agents/control/disable`
- `Track B`：`5173/` 与 `5173/agents?tenant=all` 已可稳定访问，不再出现 dev 深链 `404`
- `Track C`：`agents` 页已升级为正式控制卡，卡片承载 `installed / routing_enabled / backup_available / system_status` 以及接入层、路由层动作
- `Track D`：UI 已只依赖当前正式控制契约；候选实例上 `/metrics/summary` 与 `/agents/control*` 均返回当前仓库现实
- `Track E`：OpenClaw 真实客户端已完成 `uninstall -> install -> enable route -> disable route -> uninstall` 控制闭环；该结论只证明接入层与路由层可控，不等同于”已可使用产品”
- `仓库现实补充`：OpenClaw attach/detect 已升级为分层判定；`installed=true` 不再只看 MCP，而是同时要求 `main` 实际生效入口接入 `18011`
- `OpenClaw Usability Gap Localization` 已完成：真实 `openclaw agent --local --agent main` 运行期会将 `mcp.servers.omnimemora.url` 作为 SSE 入口消费；此前 `/mcp` 导致 `Invalid content type, expected “text/event-stream”`，仓库内 attach 已改为对 OpenClaw 写入 `/sse`
- `真实配置现实`：当前真实 OpenClaw 配置已满足新安装标准，具体为 `mcp.servers.omnimemora.url=http://127.0.0.1:18011/sse`，且 `main` 实际 provider 入口已指向 `http://127.0.0.1:18011/llm`
- **Marker 存储修复**：marker 已迁移到独立文件 `~/.openclaw/.omnimemora.attach.marker`，解决 OpenClaw CLI config schema 冲突；CLI 不再报 “Config invalid”
- **真实请求链路成立**：真实 OpenClaw 请求已进入 `18011`，`route off -> agent_route_disabled`，`route on -> runtime_compile`
- **外部运行实例对齐**：正式 `18011` 已更新到最新 repo reality，`openclaw.installed=True` 成立

## 当前后置项（已全部完成）

- OpenClaw marker 存储冲突：**已修复**
- Runtime 部署到 running reality：**已完成**
- 真实 OpenClaw 请求路径验证：**已完成**

## 下一阶段候选

- **`Control Activity Semantics`**（默认推荐）：修 `active / last_seen_at` 语义
- `Claude Code Cross Validation`：Claude Code 第二验证面交叉验证

明确排除：继续改 OpenClaw attach、GUI 物理独立、`trial / internal admin`、compile/strategy 大拆
- `Claude Code` 真实客户端交叉验证
- `trial / internal admin surface`
- compile / strategy 大拆
- GUI 物理独立
