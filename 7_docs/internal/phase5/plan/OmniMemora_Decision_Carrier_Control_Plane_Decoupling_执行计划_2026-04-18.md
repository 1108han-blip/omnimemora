---
doc_id: PLAN-DECISION-CARRIER-DECOUPLING-2026-04-18
title: OmniMemora Decision Carrier / Control-Plane Decoupling 执行计划
owner: arch-lead
reviewers: [product-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Decision Carrier / Control-Plane Decoupling 执行计划

## 一、文档定位

本文件是 `phase5.5 / Product Hardening` 之后的下一阶段正式控制文档。

本阶段不再继续扩写 `Track A/B/C` 的尾项，而是单独处理已经被识别为结构性限制的问题：

- `runtime` 同时承担 capability plane 与 decision carrier
- `runtime dead + uninstall` 当前无法安全成立
- 故障控制承载与 capability plane 物理混杂

本阶段同时执行激进文档净化：

- 每完成一个子阶段，立即归档或删除对应中间文档
- 活跃文档面只保留当前执行所需的最小集合

## 二、当前正式基线

- `5173` / GUI = 用户控制入口
- `18011` = 用户开启产品路由后的唯一产品数据入口
- `8765` = 内部 memory plane
- `Gateway + UI 双开关 + 弱侵入接入` = 当前产品主线

## 三、阶段目标

本阶段固定目标：

1. 将 `decision/status/action` 从 `runtime capability` 语义中逻辑解耦
2. 明确三层边界：
   - `18011 ingress/orchestration`
   - `runtime capability plane`
   - `decision/control carrier`
3. 在不新增第二产品入口的前提下，为 `runtime dead + uninstall` 提供正式解决方案
4. 随阶段推进同步净化文档面，防止旧控制文档继续污染下一阶段

## 四、总执行规则

### 4.1 固定顺序

1. `Track A: Decision/Control Bounded Scan`
2. `Track B: 逻辑解耦与接口边界`
3. `Track C: 最小 decision carrier 承载实现`
4. `Track D: 候选实例与极端故障验证`

未完成 `A/B` 前，不进入 `runtime dead + uninstall` 的实现。

### 4.2 文档净化规则

每个 track 结束后，立即执行：

- 保留：
  - 当前阶段唯一执行计划
  - 当前阶段唯一 runbook
  - 当前阶段唯一验证记录
  - 当前主线唯一专题文档
- 合并：
  - 同主题 bounded scan / 说明 / 边界文档能并就并
- 归档：
  - 已完成 track 的中间控制文档移入 archive
- 删除：
  - 无控制价值、无验证价值、无遗产索引价值的文档直接删除

### 4.3 Worktree 与验证对象

- worktree 健康继续沿用 `workspace-governance` 阈值
- 行为验证继续绑定 [OmniMemora 验证对象登记与验收记录](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)
- 禁止混用 repo / candidate / running reality

## 五、Track 定义

### Track A: Decision/Control Bounded Scan

目标：收敛当前 decision carrier / control-plane 的真实实现入口与历史残留。

完成标准：

- 输出唯一 bounded scan 文档
- 固定可复用、必须避开、需要清理、当前实现入口四栏
- 不再保留多份 phase5.5 遗留 track 文档处于活跃状态

### Track B: 逻辑解耦与接口边界

目标：明确 capability plane 与 decision/control carrier 的逻辑边界。

完成标准：

- `gateway/status`
- `gateway/decision/*`
- user-decision-required action carrier

以上职责被正式归类为 control carrier，而不是 runtime capability

### Track C: 最小 decision carrier 承载实现

目标：在不新增第二产品入口、不过早新服务化的前提下，让最小控制承载不依赖 runtime capability 健康。

完成标准：

- `runtime dead + uninstall` 有正式承载路径
- 用户仍可执行 `disable-route / uninstall`
- 不引入新的正式产品入口

### Track D: 候选实例与极端故障验证

目标：补齐新结构在候选实例下的关键极端故障证据。

完成标准：

- `runtime dead + uninstall`
- `runtime dead + disable-route`
- gateway / runtime 联合故障下的最小控制承载

以上均有候选实例级记录

## 六、明确不做的事

- 不修真实 OpenClaw / Claude Code
- 不恢复 `5173` 可视 UI
- 不拆 `trial / internal admin surface`
- 不做 compile / strategy 大拆分
- 不为了极端场景新增复杂常驻服务

## 七、验收

### 结构验收

- `runtime dead + uninstall` 有正式解决方案
- decision/control carrier 与 runtime capability plane 边界清晰
- 不新增第二产品入口
- 不破坏 `18011` 单入口定义

### 文档验收

- 活跃文档面显著变薄
- 当前阶段每类文档只有单一权威入口
- 已完成 track 的中间文档不再污染活跃入口
- 删除/归档后，不影响 AI 根据活跃文档继续执行

## 八、默认假设

- 本阶段继续由架构师视角主导，软件工程约束落地
- 文档主要服务于当前执行控制，不为长期人工浏览优化
- 当前阶段验证目标仍以逻辑级、候选实例级为主，不等同于真实用户端可用性证明
