---
doc_id: PLAN-PHASE5-V2-LEGACY-MAP-2026-04-18
title: OmniMemora V2遗产映射与后备优化清单
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora V2遗产映射与后备优化清单

## 一、文档定位

本文不是当前产品定义文档，也不是要求恢复 `V2` 主线的执行计划。

用途只有三个：

- 固定 `V2` 在当前仓库中的真实存在状态
- 说明当前主线哪些地方仍依赖 `V2` 遗产
- 把 `V2` 明确降级为“后备优化轨”，避免后续排障与重启优化时重新考古

若本文与当前 phase5.5 执行文档冲突，以：

1. [OmniMemora Decision Carrier / Control-Plane Decoupling 执行计划](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Decision_Carrier_Control_Plane_Decoupling_执行计划_2026-04-18.md)
2. [OmniMemora Decision Carrier / Control-Plane Decoupling Runbook](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Decision_Carrier_Control_Plane_Decoupling_Runbook_2026-04-18.md)
3. 本文

的优先顺序解释。

## 二、当前冻结结论

### 2.1 V2 不是当前产品真相

- 当前产品主线真相仍是 `Gateway + UI 双开关 + 弱侵入`
- 当前产品入口语义仍是：
  - `5173/GUI = 用户控制入口`
  - `18011 = 用户开启产品路由后的唯一产品数据入口`
  - `8765 = 内部 memory plane`
- 因此，`/memory/search V2`、`/memory/query V2`、旧 `Memory Adapter v2.x` 叙事，**不得**回流为当前产品定义

### 2.2 V2 仍然是当前代码现实的一部分

以下事实已经确认：

- [5_connectors/adapter/main.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/main.py) 仍自称 `Memory Adapter v2.2`
- [4_core/logic/v2_compute.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/v2_compute.py) 仍是当前主链 token savings / metering 纯逻辑层
- [4_core/logic/engine.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/engine.py) 仍直接依赖 `v2_compute`
- [5_connectors/adapter/meter_store.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/meter_store.py) 仍直接导入 `4_core.logic.v2_compute`

因此，更准确的判断是：

- `V2` 作为旧产品主线已退出
- `V2` 作为计算层、计量层、验证资产与历史设计遗产仍在主链中生效

### 2.3 后续排障不能假装 V2 从未存在

当前主线若完全忽略 `V2`，会带来两类风险：

- 修当前 bug 时，看不到底层依赖仍来自 `V2` 遗产
- 未来若重启 `V2` 优化轨，又要重复做历史梳理和兼容判断

所以 phase5 下必须明确：

- 调 bug 时要承认 `V2` 的事实存在
- 但不能让 `V2` 旧叙事重新定义当前产品

## 三、V2资产映射表

| V2资产 | 当前位置 | 当前主线是否仍依赖 | 当前角色 | 后续处置建议 |
|------|------|------|------|------|
| V2 计算层 | [4_core/logic/v2_compute.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/v2_compute.py) | 是 | 主链依赖 | 保留；视为“遗产核心模块”，后续只做兼容性整理，不做叙事回流 |
| 统一编排入口 | [4_core/logic/engine.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/engine.py) | 是 | 主链依赖 | 保留；后续如拆 compile/strategy，应记录其与 `v2_compute` 的耦合点 |
| Meter 持久化层 | [5_connectors/adapter/meter_store.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/meter_store.py) | 是 | 主链依赖 | 保留；后续若改计量口径，必须先声明是否影响 V2 meter artifact 兼容 |
| 旧 Adapter 主体 | [5_connectors/adapter/main.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/main.py) | 是 | 主链承载层 | 不否认其 V2 血缘；但文档口径必须按 phase5 产品定义解释 |
| `/memory/search V2` 设计稿 | [7_docs/internal/phase2/01_planning/archive/Search_V2_Phase_2a_plan.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase2/01_planning/archive/Search_V2_Phase_2a_plan.md), [Search_V2_Phase_2b_plan.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase2/01_planning/archive/Search_V2_Phase_2b_plan.md), [Search_V2_Phase_2c_plan.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase2/01_planning/archive/Search_V2_Phase_2c_plan.md) | 否，直接不依赖 | 历史设计资产 | 保留为后备优化轨参考，不作为当前产品验收标准 |
| V2 修复审计结论 | [7_docs/internal/phase2/02_enforcement/archive/Phase_2c5_AUDIT_V2_REPORT.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase2/02_enforcement/archive/Phase_2c5_AUDIT_V2_REPORT.md) | 否，直接不依赖 | 历史验证资产 | 可用作后续“遗产回归风险”参考，不外推为 phase5 行为证明 |
| Adapter Raw / 旧 `/memory/query` 叙事 | `4_core/adapter-raw/`（Cloud Reset Batch 1 已删除旧 archive 载体） | 否 | 纯历史残留 | 不得回流为当前产品路径 |

## 四、当前主线应如何对待 V2

### 4.1 可以继承的部分

- token savings 计算逻辑
- meter artifact 结构与聚合经验
- `filter -> score -> dedup -> pack -> meter` 这类纯逻辑分层
- V2 阶段形成的审计与验证思路

### 4.2 不可回流的部分

- 以 `/memory/search` 或 `/memory/query` 作为当前产品主入口
- 把 `8765` 重新抬升成对外产品接口
- 以 `Memory Adapter v2.x` 叙事替代 `Gateway + UI 双开关 + 弱侵入`
- 以 phase2/phase3 的旧宪法、旧审计结论替代 phase5 主基线

### 4.3 当前排障时的使用规则

- 若 bug 位于 [5_connectors/adapter/main.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/main.py)、[4_core/logic/engine.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/engine.py)、[4_core/logic/v2_compute.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/v2_compute.py)、[5_connectors/adapter/meter_store.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/meter_store.py)，必须先检查其 `V2` 历史依赖
- 若 bug 位于 `18011 gateway`、`/agents/control*`、attach/detach/restore，优先按 phase5 主线处理；只在确实追到 V2 计算层时，才向下追溯
- 不得因为“某逻辑来自 V2”就自动判定它属于当前产品真相

## 五、V2后备优化轨建议

`V2` 可以作为后续产品优化的备选工程继续做下去，但必须满足以下边界：

- 定位：`后备优化轨`，不是当前产品主线
- 目标：复用其中仍有价值的计算层、context assembly、metering 和 ranking 经验
- 前提：不得破坏 phase5 已确定的产品入口、控制面和弱侵入接入语义

建议后续若重启 `V2` 轨，按以下顺序：

1. 先做遗产依赖清点，而不是直接恢复实现
2. 只提炼可复用算法与结构，不恢复旧产品叙事
3. 所有新落地都必须重新经过 phase5/后续阶段的产品边界裁决

## 六、当前执行要求

从本文生效起：

- 当前主线 bug 修复允许引用 `V2` 作为历史依赖事实
- 当前主线验收不得引用 `V2` 旧文档作为产品验收标准
- 若后续发现新的主链依赖仍来自 `V2`，应补充到本清单，而不是口头记忆

## 七、下一步建议

本轮不重启 `V2` 实施工程。

本轮之后，若要降低后续返工风险，优先做：

- 在涉及 `engine / v2_compute / meter_store / adapter/main.py` 的 bug 记录里增加 “是否触发 V2 遗产依赖” 标记
- 等当前 Git 仓库完整性问题分级完成后，再决定是否为 `V2` 单独开一条优化 backlog
