---
doc_id: PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18
title: OmniMemora Phase 5.5 Product Hardening 执行计划
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5-CONVERGENCE-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Product Hardening 执行计划

## 一、文档定位

本文件是 `phase5` 收口后的下一轮正式控制文档，负责 `Phase 5.5 / Product Hardening` 的顺序、gate 与完成定义。

当前 phase5 没有独立的 working-principles / SOP 文档；因此本阶段的控制基线固定为：

1. [云端小工程](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/云端小工程.md)
2. [OmniMemora 验证对象登记与验收记录](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)
3. 本文件

若表述冲突，以本文件的执行顺序和 gate 定义为准。

## 二、当前正式基线

- `5173` / GUI = 用户控制入口
- `18011` = 用户开启产品路由后的唯一产品数据入口
- `8765` = 内部 memory plane
- `Gateway + UI 双开关 + 弱侵入接入` = 当前产品主线

## 三、阶段目标

本阶段只做产品硬化，不扩新产品形态。

固定目标：

1. 让 `8765` 从“可能被误用的对外面”进一步收回到内部 plane
2. 把自动自愈 / 自动拉起从文档决策推进到真实工程方案
3. 为 `18011` 的纯接入编排层拆分建立可执行边界
4. 用候选实例补强关键行为和故障分支证据

## 四、总执行规则

### 4.1 固定顺序

1. `Track A: 8765 对外接口收口`
2. `Track B: 自动自愈 / 自动拉起状态机`
3. `Track C: 18011 纯接入编排层拆分准备`
4. `Track D: 候选实例补强验证`

`A/B` 未完成前，不进入真正的结构拆分实现。

### 4.2 Bounded Global Scan

每个 track 开始前必须执行一次 bounded global scan，并至少产出四栏：

- `可复用`
- `必须避开`
- `需要清理`
- `当前实现入口`

扫描范围只限于与该 track 强相关的：

- 当前主线实现
- V2 遗产
- phase3 残留
- adapter / runtime / dashboard / docs 的跨层分散点

scan 完成后，执行期只允许做定向核对，不再扩成全局重考古。

### 4.3 Worktree 与验证对象

- worktree 健康继续沿用 `workspace-governance` 阈值
- 行为验证继续沿用 [OmniMemora 验证对象登记与验收记录](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)
- 禁止混用 repo / candidate / running reality

## 五、Track 定义

### Track A: 8765 对外接口收口

目标：让 `8765` 回到纯内部 plane，不再承担正式产品对外职责。

实施重点：

- 盘点 `8765` 当前暴露的 HTTP 面、调用来源、误用面
- 区分“内部依赖面”和“对外误当产品面”
- 把正式产品文档、控制面、诊断面收敛到 `18011`
- 为仍需兼容的 `8765` 面建立退场清单

完成标准：

- 新文档与新实现不再把 `8765` 当正式产品接口
- 对外验收只绑定 `18011`
- `8765` 保留内部能力，但不再扩面

### Track B: 自动自愈 / 自动拉起状态机

目标：把“用户启用产品后，系统先自救，再决定如何降级”落成真实行为。

#### 入口层故障

入口层 = `18011`

- `18011` 不健康但可修复：自动修复，成功后继续原状态
- `18011` 不健康且不可修复：进入 `user-decision-required`

#### 能力层故障

能力层 = `8765` / compile / strategy / runtime bridge / 云端策略能力等内部产品效果层

- `18011` 健康但能力层可修复：自动修复，成功后继续产品增强路径
- `18011` 健康但能力层不可修复：自动降级为 `passthrough`，UI 静默提示，不弹出用户决策

#### 固定禁止项

- 自动化不得直接执行 `restore backup`
- 自动化不得直接执行 `uninstall/detach`
- `backup/restore` 只属于 install/uninstall 层
- 自动化上限只有：检测、修复、降级到 passthrough、或进入 `user-decision-required`

### Track C: 18011 纯接入编排层拆分准备

目标：先把责任边界做清，不直接大拆。

实施重点：

- 盘点 `18011` 当前承担的 ingress / compile / strategy / diagnostics / control 责任
- 建立目标分层：
  - `18011` ingress/orchestration
  - local compile module
  - local strategy module
- 先形成调用边界和迁移顺序

完成标准：

- 有责任边界图
- 有迁移顺序与禁止事项
- 本阶段不直接大规模搬迁逻辑

### Track D: 候选实例补强验证

目标：补足候选实例级证据，降低后续硬化回归风险。

实施重点：

- 继续使用隔离 `HOME` 和候选实例
- 继续绑定验证对象登记，禁止混验
- 覆盖关键 family、状态转换、故障场景

完成标准：

- 新硬化项都有候选实例闭环记录
- 故障、自愈、降级、用户决策分支均有明确验收记录

## 六、Agent 分配

主线程负责：

- phase / gate 裁决
- bounded global scan 结论合并
- worktree 健康控制
- 最终集成判断

低成本子 agent 负责：

- `Track A` 的对外接口扫描
- `Track B` 的故障/回退相关旧实现扫描
- 文档模板填充
- 接口对照表整理
- 只读验证入口盘点

## 七、验收

### 文档层

- phase5.5 执行计划与 runbook 存在并互链
- `workspace-governance` skill 已包含 bounded global scan 规则

### Track A

- `18011` 成为唯一正式产品对外验收入口
- `8765` 不再新增对外职责

### Track B

- 验证 `18011` 故障可自动修复路径
- 验证 `18011` 故障不可修复时进入用户决策状态
- 验证 `18011` 正常但能力层失败时自动降级为 passthrough
- 验证整个流程不自动 restore backup

### Track C

- 静态验证责任边界图
- 验证 `route=off` passthrough / `route=on` compile path 不被破坏

### Track D

- 所有结论写入验证对象登记文档
- 候选实例持续使用隔离环境，不影响真实用户配置

## 八、默认假设

- 本阶段优先级固定为：**产品硬化优先**
- 旧 `ROADMAP` 暂不作为顺序裁决依据，以当前 phase5 收口现实为准
- `backup/restore` 只属于 install/uninstall 层，不属于自动故障回退层
- UI 故障反馈允许分层：
  - 能力故障：静默提示
  - 入口故障不可恢复：要求用户决策
