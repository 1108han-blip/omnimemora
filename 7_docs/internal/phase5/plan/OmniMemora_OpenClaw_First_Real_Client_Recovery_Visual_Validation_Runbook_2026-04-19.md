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
- `Track E`: 已完成（OpenClaw 主验证面）

## 当前执行顺序

1. 候选实例 `18041` 已对齐到当前仓库现实，并稳定暴露 `/agents/control*`
2. `5173` 深链与装配已修复，`/` 与 `/agents` 均可稳定访问
3. 正式控制卡已落地，`install/uninstall` 与 `enable/disable` 已进入正式用户控制入口
4. 控制契约已对齐，`/metrics/summary` 与 `/agents/control*` 不再依赖失效实现
5. OpenClaw-first 真实验证已完成一轮完整闭环

## 当前规则

- 本阶段 UI 结论只绑定候选实例
- `5173` 是正式用户控制入口，不再只做观测 dashboard
- `install/uninstall` = 接入层
- `enable/disable` = 路由层
- `OpenClaw` 是主测试面
- `Claude Code` 是补充验证面
- `Codex` 不参与实例测试

## 当前阶段结论

- `Track A`：候选实例 `18041` 当前稳定暴露 `GET /agents/control`、`POST /agents/control/rescan`、`POST /agents/control/install`、`POST /agents/control/uninstall`、`POST /agents/control/enable`、`POST /agents/control/disable`
- `Track B`：`5173/` 与 `5173/agents?tenant=all` 已可稳定访问，不再出现 dev 深链 `404`
- `Track C`：`agents` 页已升级为正式控制卡，卡片承载 `installed / routing_enabled / backup_available / system_status` 以及接入层、路由层动作
- `Track D`：UI 已只依赖当前正式控制契约；候选实例上 `/metrics/summary` 与 `/agents/control*` 均返回当前仓库现实
- `Track E`：OpenClaw 真实客户端已完成 `uninstall -> install -> enable route -> disable route -> uninstall` 闭环；当前以 OpenClaw 为正式主验证面，Claude Code 补充验证仍后置

## 当前后置项

- 旧运行现实 `~/.omnimemora/service/current` 的 `18011` 仍未纳入本阶段结论范围
- `Claude Code` 真实客户端交叉验证
- `trial / internal admin surface`
- compile / strategy 大拆
- GUI 物理独立
