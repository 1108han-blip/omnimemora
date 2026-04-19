---
doc_id: PLAN-PHASE5-OPENCLAW-FIRST-REAL-CLIENT-RECOVERY-2026-04-19
title: OmniMemora OpenClaw-first Real Client Recovery + Visual Validation 执行计划
owner: arch-lead
reviewers: [product-lead]
status: active
version: 1.0.0
effective_date: 2026-04-19
depends_on:
  - PLAN-PHASE5-DECOUPLING-2026-04-18
supersedes: []
last_verified_commit: ""
---

# OmniMemora OpenClaw-first Real Client Recovery + Visual Validation 执行计划

## 摘要

本阶段目标不是继续做结构拆分，而是把已经完成的内核/控制面收敛，转换成真实用户可见、可操作、可验收的产品行为。

本阶段固定顺序：

1. 先修复 `5173`，把它恢复成正式用户控制入口。
2. 再用 `OpenClaw` 做第一主验证面。
3. `Claude Code` 只做补充交叉验证。
4. `Codex` 明确排除出实例测试面。

## 当前基线

- `5173` / GUI = 用户控制入口
- `18011` = 产品数据入口与控制 API 来源
- `8765` = 内部 memory/runtime plane
- 本阶段不新增第二产品入口
- 本阶段不做 GUI 物理独立，只做契约独立 + 正式控制面恢复

## 执行轨道

### Track A: 验证对象与运行现实对齐

- 本阶段 UI 结论只绑定从当前 repo 显式启动的候选实例
- 不使用旧 `~/.omnimemora/service/current` 的在线 `18011` 作为 `5173` 结论依据
- 候选实例必须实际暴露 `/agents/control*`

### Track B: 5173 路由与装配修复

- 修 SPA 深链访问，`/agents` 不再 `404`
- 固定 overview / agents 两个产品入口路径
- 保持现有 Vite/React 工程，不另起新前端工程

### Track C: 正式控制卡落地

- `5173` 的 agents 页升级成正式控制卡
- 控制卡必须承载：
  - install / uninstall
  - enable route / disable route
  - installed / routing_enabled / detected / active
  - health_state / backup_available / message
  - 顶层 `system_status`

### Track D: 控制契约对位

- UI 只依赖当前 `/agents/control*` 正式契约
- 不混用观测面字段和控制面字段
- 错误态、禁用态、推荐动作必须落到正式控制语义

### Track E: OpenClaw-first 真实验证

- OpenClaw 作为第一主验证面完成完整闭环
- Claude Code 只做关键路径交叉验证
- Codex 不参与实例测试

## 验收标准

- `5173` 可直接访问 `/`、`/agents`、带 tenant 的对应路径
- 候选实例 `18011` 上 `/agents/control*` 全部可用
- `5173` 可执行 install / uninstall / enable / disable
- OpenClaw 完成一轮真实接入、路由、恢复、退出闭环
- UI 状态与真实接口、真实行为一致

## 明确后置

- `trial / internal admin surface`
- compile / strategy 大拆
- GUI 美化重设计
- GUI 物理独立工程化
