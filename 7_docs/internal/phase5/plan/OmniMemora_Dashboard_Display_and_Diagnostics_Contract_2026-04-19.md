---
doc_id: PLAN-PHASE5-DASHBOARD-DISPLAY-DIAGNOSTICS-CONTRACT-2026-04-19
title: OmniMemora Dashboard Display and Diagnostics Contract
owner: product-arch
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-19
depends_on:
  - ADR-0005-AGENT-IDENTITY
  - RECORD-PHASE5-VALIDATION-OBJECTS-2026-04-18
supersedes: []
last_verified_commit: ""
---

# OmniMemora Dashboard Display and Diagnostics Contract

## 1. 文档定位

本文件固定 `:5173` dashboard 的**用户面展示边界**与 **diagnostics 边界**。

目的只有两个：

- 固定哪些字段可以进入默认用户路径
- 固定哪些 raw/internal 字段只能进入 diagnostics

本文件不负责：

- 定义产品数据入口
- 重新定义 agent identity
- 修复 promotion automation
- 调整 UI 托管策略

若本文件与产品边界或 identity 规范冲突，以：

1. [PRODUCT_DEFINITION.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_DEFINITION.md)
2. [PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md)
3. [ADR-0005-agent-identity-fields.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/9_adr/ADR-0005-agent-identity-fields.md)
4. 本文件

的优先顺序解释。

## 2. 总规则

### 2.1 控制入口规则

- `:5173` 是**控制入口**与**用户控制台**
- `:18011` 是**唯一产品数据入口**
- `:5173` 不承载产品数据真相，只消费标准 API 真相并做展示

### 2.2 身份展示规则

- 用户面默认显示 `canonical family` / `canonical_agent_id`
- raw/internal 身份字段不得直接进入默认用户路径
- `canonical_agent_id` 是 runtime 唯一合法 agent identity
- `session_id` 永远不是 `agent_id` 的一部分

### 2.3 透明语义规则

- dashboard 不得通过展示层重新定义 provider / model / auth / source 语义
- dashboard 只能消费已经 resolved 的产品 truth，不得在展示层静默改写用户 LLM 语义

### 2.4 diagnostics 隔离规则

- diagnostics 面可以保留 raw/internal truth
- 但 diagnostics 必须显式标成 diagnostics
- raw/internal truth 不得混进默认用户路径

## 3. 分块字段白名单

### 3.1 Agent 控制

| 类型 | 字段 |
|------|------|
| 必须显示 | `canonical_agent_id`, `installed`, `routing_enabled`, `active`, `last_seen_at` |
| 可归并后显示 | raw id -> canonical family |
| 只进 diagnostics | bootstrap / handshake 细节、raw transport 细节 |

要求：

- 控制卡默认使用 canonical identity
- 不允许把 session、bundle、transport 细节直接渲染成用户可见主身份

### 3.2 Agent Breakdown

| 类型 | 字段 |
|------|------|
| 必须显示 | canonical family、aggregated usage、token savings、状态摘要 |
| 可归并后显示 | raw agent id -> canonical family |
| 只进 diagnostics | raw agent id 明细、归并过程 |

要求：

- Breakdown 对外只显示 canonical family
- raw family / raw agent id 只能作为 diagnostics 追踪数据

### 3.3 Live Request Flow

| 类型 | 字段 |
|------|------|
| 必须显示 | request id、当前状态、compile 结果摘要、route 状态 |
| 可归并后显示 | internal step 名称 -> 用户标签 |
| 只进 diagnostics | transport / bundle / handshake / internal call-chain |

要求：

- 用户面实时流优先显示真实用户请求及其 compile/route 结果
- `session bootstrap context handshake` 这类 internal 事件不得主导默认时间线

### 3.4 Context Before / After

| 类型 | 字段 |
|------|------|
| 必须显示 | before/after 摘要、savings ratio、selected context summary |
| 可归并后显示 | 数值与文案标准化 |
| 只进 diagnostics | 原始 trace fragment、中间决策链 |

要求：

- 用户面只显示最终结果摘要
- 中间决策链和原始 trace fragment 只进 diagnostics

### 3.5 overview

| 类型 | 字段 |
|------|------|
| 必须显示 | 总 token savings、today/week/month、health summary |
| 可归并后显示 | 指标名归一 |
| 只进 diagnostics | 细粒度实现字段 |

要求：

- overview 应承载用户可解释的 KPI truth
- 细粒度实现字段不得直接渲染成用户面指标

### 3.6 Call Chain

| 类型 | 字段 |
|------|------|
| 必须显示 | 最终调用路径摘要 |
| 可归并后显示 | 节点名归并 |
| 只进 diagnostics | 中间节点、内部实现名 |

要求：

- 用户面只显示最终摘要链路
- 中间调用节点和内部实现名只进 diagnostics

## 4. Diagnostics-only 白名单

以下字段或字段族只允许进入 diagnostics：

- `raw_agent_id`
- `session_id`
- `integration_type`
- 未规整 trace fragment
- `openclaw-bundle-mcp` 这类内部原始标识
- bootstrap / handshake / transport / internal call-chain 中间节点
- 任何未映射完成的身份字段

补充治理规则：

- diagnostics 可以保留 raw/internal truth
- diagnostics 不得反向污染默认用户面
- raw/internal 字段只有在明确标记为 diagnostics 时才允许对外呈现

## 5. 权威依据

### 5.1 产品边界依据

- [README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/README.md)
  - `:5173` 是控制入口
  - `:18011` 是唯一产品数据入口
- [PRODUCT_DEFINITION.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_DEFINITION.md)
  - `5173` 管控制，`18011` 管数据路径，`8765` 是内部 memory plane
- [PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md)
  - 产品不应静默改写 provider / model / auth / source 语义

### 5.2 identity 依据

- [ADR-0005-agent-identity-fields.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/9_adr/ADR-0005-agent-identity-fields.md)
  - `canonical_agent_id = runtime 唯一合法 agent_id`
  - `session_id 永远不是 agent_id 的一部分`
  - raw identity 只能作为 metadata / debug / 映射追踪

### 5.3 console 指标依据

- [6_console/README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/6_console/README.md)
  - `Token Savings Meter` 是核心展示指标
  - console 通过标准 API 访问 backend

## 6. 与当前实现的对位要求

本契约落地后，后续 dashboard 验收至少要对位以下事实：

- family normalization 必须符合 canonical family
- `Agent Breakdown` 只显示 canonical family
- `Live Request Flow` 已过滤 internal handshake / bootstrap 噪音
- overview 与 `Agent 控制` 的 activity truth 一致
- `Agent 控制` 继续使用 canonical identity

若实现仍有字段越界：

- 先按本契约认定为展示层 drift
- 后续单开补丁批次修正
- 不在展示契约文档里即兴重写规则
