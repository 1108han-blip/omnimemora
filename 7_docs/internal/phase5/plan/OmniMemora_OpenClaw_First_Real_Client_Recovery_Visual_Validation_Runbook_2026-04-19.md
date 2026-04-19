---
doc_id: RUNBOOK-PHASE5-OPENCLAW-FIRST-REAL-CLIENT-RECOVERY-2026-04-19
title: OmniMemora OpenClaw-first Real Client Recovery + Visual Validation Runbook
owner: arch-lead
reviewers: [product-lead]
status: active
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
- `Next Gate`: `OpenClaw Usability Gap Localization`

## 当前执行顺序

1. 候选实例 `18041` 已对齐到当前仓库现实，并稳定暴露 `/agents/control*`
2. `5173` 深链与装配已修复，`/` 与 `/agents` 均可稳定访问
3. 正式控制卡已落地，`install/uninstall` 与 `enable/disable` 已进入正式用户控制入口
4. 控制契约已对齐，`/metrics/summary` 与 `/agents/control*` 不再依赖失效实现
5. OpenClaw-first 已完成一轮接入 / 路由 / 恢复 / 退出控制闭环，但真实使用路径仍待补证

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
- `Track E`：OpenClaw 真实客户端已完成 `uninstall -> install -> enable route -> disable route -> uninstall` 控制闭环；该结论只证明接入层与路由层可控，不等同于“已可使用产品”
- `仓库现实补充`：OpenClaw attach/detect 已升级为分层判定；`installed=true` 不再只看 MCP，而是同时要求 `main` 实际生效入口接入 `18011`
- `OpenClaw Usability Gap Localization` 已锁定一个明确缺口：真实 `openclaw agent --local --agent main` 运行期会把 `mcp.servers.omnimemora.url=/mcp` 当成 SSE 端点并报 `Invalid content type, expected text/event-stream`；仓库内 attach 已改为对 OpenClaw 写入 `/sse`
- `外部运行实例观察事实`：正式 `18011` 当前返回 `openclaw.installed=false`、`routing_enabled=true`、`active=false`；因此当前不能宣称 OpenClaw 已在使用产品
- `Next Gate`：`OpenClaw Usability Gap Localization`，用于锁定“已接入但不走产品”的断点位于客户端生效、路由一致性、产品路径进入还是请求后结果可见性

## 当前后置项

- 旧运行现实 `~/.omnimemora/service/current` 的 `18011` 仍未纳入本阶段结论范围
- `OpenClaw Usability Gap Localization`
- `Claude Code` 真实客户端交叉验证
- `trial / internal admin surface`
- compile / strategy 大拆
- GUI 物理独立
