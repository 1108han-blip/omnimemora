---
doc_id: ADR-0003-INTERFACE-ACCESS-PATHS
title: OmniMemora Multi-Access Interface Architecture Principles
owner: platform-team
reviewers: [arch-lead]
status: active
version: 1.1.0
effective_date: 2026-04-13
depends_on: [ADR-0001-PRODUCT-BOUNDARY, ADR-0002-CLOUD-REFACTOR]
supersedes: []
last_verified_commit: ""
---

# ADR-0003: OmniMemora 多接入接口架构原则

**状态：** Active（已修订）
**日期：** 2026-04-13
**修订原因：** 原版本允许多路径并行（8765 / 18011），导致功能口径/数据结构/用户体验分裂。修订为**唯一产品路径**架构。

---

## 一、核心原则：多接口，单路径

> **产品路径必须唯一，不可分裂。**

OmniMemora 只有一条产品数据路径。所有协议接入（MCP/CLI/REST/Wrapper）最终都收敛到同一条核心路径。

### 错误结构（禁止出现）

```
Agent
  ↓
┌─→ Go Runtime (8765) ──→ ???
│
└─→ Python Adapter (18011) ──→ ???

问题：
- 功能口径不一致
- 数据结构不一致
- 用户体验不一致
- 哪个才是产品本体说不清
```

### 正确结构

```
  MCP ──┐
  CLI ──┼──→ Unified Interface Layer ──→ Core Compiler
  REST ─┤
  Wrap ─┘
```

多接口，单路径：
- MCP / CLI / REST / Wrapper 是**协议适配层**（可以替换）
- 统一接口层之下是**同一个 Core Compiler**（不可分裂）
- 所有接入返回**同一个数据结构**

补充原则：
- 产品端主要适配**协议族**，不主要适配**市场模型列表**
- 用户端已经存在的 `provider / base_url / auth / model` 是接入真相的第一来源
- Python Adapter 负责在不破坏该真相的前提下插入 compile / meter / trace

---

## 二、架构图

```
Agent
  ↓
┌─────────────────────────────────────────────────────────┐
│  Unified Interface Layer (Python Adapter :18011)        │
│                                                         │
│  MCP Protocol Adapter (SSE + JSON-RPC)                  │
│  REST Adapter                                           │
│  CLI Adapter                                            │
│  Wrapper Adapter                                        │
│                         ↓                               │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Context Compiler (Core Engine)                 │   │
│  │                                                 │   │
│  │  filter → route_score → dedup → select → pack  │   │
│  │                                                 │   │
│  │  Token Savings Meter                            │   │
│  │  Call Chain Trace                               │   │
│  │  Decision Log                                   │   │
│  └─────────────────────────────────────────────────┘   │
│                         ↓                               │
│  Structured JSON Response                               │
│  { saved_tokens, savings_ratio, selected_memories,      │
│    packed_context, task_type, context_bypass }          │
└─────────────────────────────────────────────────────────┘
  ↓
LLM
```

---

## 三、接口定义

| 接口 | 协议 | 入口端口 | 角色 |
|------|------|---------|------|
| MCP | SSE + JSON-RPC | :18011 | 通用 Agent 生态标准接入面 |
| CLI | HTTP REST | :18011 | 本地优先，低延迟 |
| REST | HTTP JSON | :18011 | 工具链 / CI/CD / 编排系统 |
| Wrapper | subprocess | :18011 | 策略验证与实验 |

補充口徑：

- `:5173` 是用戶控制與 advisory 入口，不承載產品數據路徑；但它可以展示產品數據路徑的狀態、結果、診斷投影與只讀聚合視圖
- `:18011` 是用戶開啟產品路由後的唯一產品數據入口
- `:8765` 是內部 Runtime / Memory Plane；其 integration carrier 能力（attach/detach/backup/restore/rescan）不等於 memory plane 本體，不回流成產品入口

### 关键约束

**所有接口统一从 Python Adapter (18011) 接入。**

同时要求：

- `18011` 接住请求后，优先透传用户端已配置的上游 truth
- 只有在用户端未提供足够上游信息时，才允许产品端使用 fallback/default
- 产品端不得把自己演化成一个持续维护外部模型生态的适配中心

Go Runtime (8765) 的定位重新明确：
- **仅作为 Local Memory Plane**（存储、检索、scope 治理）
- **不承载产品入口功能**
- **不实现独立的 Context Assembly / Token Savings 逻辑**
- **integration carrier（attach/detach/backup/restore/rescan）属于控制面能力，不等于 memory plane 本體**

---

## 四、统一响应数据结构

所有接口路径返回完全相同的响应结构：

```json
{
  "request_id": "req-xxxx",
  "packed_context": "...",
  "selected_memories": [...],
  "usage": {
    "saved_tokens_estimate": 847,
    "savings_ratio": 0.92,
    "actual_tokens_estimate": 153,
    "baseline_tokens_estimate": 1000
  },
  "task_type": "continuation",
  "context_bypass": false,
  "matched_keywords": ["project"]
}
```

不得因接入协议不同而返回不同的数据结构。

---

## 五、能力模块可选配置

OmniMemora 默认启用完整核心能力。可选关闭的是**增强模块**，不是产品路径：

```
Unified Entry
   ↓
[ module toggles ]
   ├─ token_optimization  on/off（默认 on）
   ├─ compression          on/off（默认 on）
   ├─ feedback            on/off（默认 off）
   └─ policy_mode         permissive/strict（默认 strict）
```

用户关闭模块仍然走同一条主路径，只是该模块不生效。

---

## 六、实现约束

### 6.1 Go Runtime 约束

```
禁止：Go Runtime 独立实现 Context Assembly / Token Savings
允许：Go Runtime 作为 Local Memory Plane 提供存储和检索
```

- Go Runtime `SearchMemory` 不做 context assembly
- Go Runtime `AssembleContext: true` 配置无效（忽略）
- 所有 token savings / metering 必须通过 Python Adapter 路径

### 6.2 Python Adapter 约束

```
必须：所有请求统一经过 engine.optimize_context()
必须：所有 metering 写入同一个 meter_store
必须：所有 trace 写入同一个 trace_store
必须：所有响应返回同一个数据结构
必须：保持同协议接入、同协议送回
必须：优先透传用户端 provider/base_url/auth/model truth
```

说明：

- 协议理解是为了实现 compile / meter / trace 所需的最小功能，不是为了替用户重定义接入方式
- 若产品端能直接使用用户端现有 upstream truth，就不应退回到产品内部模型映射优先

### 6.3 端口约定

| 端口 | 角色 | 备注 |
|------|------|------|
| 5173 | Dashboard / Control UI | **用户控制与 advisory 入口**，不承载产品数据路径，可展示数据路径状态与只读聚合视图 |
| 8765 | Local Memory Plane（Go Runtime） | 仅存储/检索，**非产品入口**；integration carrier 能力属于控制面，不等于 memory plane |
| 18011 | Unified Interface Layer（Python Adapter） | **唯一产品数据入口**，所有协议统一接入 |

### 6.4 内部三层结构

`18011` 内部明确分为三层：

- **ingress**：协议入口，passthrough / upstream forwarding，ingress trace/context attach（`llm_proxy.py`）
- **application**：compile 编排，truth resolution，control orchestration，read-model 聚合（`gateway_compile.py` + `application/status_read_model.py`）
- **infrastructure**：runtime/backend/store/cloud 访问（`meter_store.py` 等）

---

## 七、决策记录

- **DECISION-0003-01**：OmniMemora 产品数据路径唯一，所有协议接入收敛到 Python Adapter (18011)
- **DECISION-0003-02**：Go Runtime (8765) 仅作为 Local Memory Plane，不承载产品入口
- **DECISION-0003-03**：Dashboard (5173) 是用户控制入口，不参与产品数据路径
- **DECISION-0003-04**：所有响应返回统一数据结构，不得因协议不同而分化
- **DECISION-0003-05**：能力模块可配置（token_optimization / compression 等），但产品路径不可选
- **DECISION-0003-06**：`5173` 不承载产品数据路径，但可以展示产品数据路径的状态、结果、诊断投影与只读聚合视图
- **DECISION-0003-07**：`8765` 的 integration carrier（attach/detach/backup/restore/rescan）不等于 memory plane 本體，不回流成产品入口
- **DECISION-0003-08**：18011 内部明确三层结构：ingress（llm_proxy.py）/ application（gateway_compile.py + application/）/ infrastructure

---

## 八、溯源

- 控制面基线：`0_blueprint/DEFAULT_IN_CONTROL_PLANE.md`
- 产品定义：`0_blueprint/PRODUCT_DEFINITION.md`（已同步修订）
- 本文档替代：原 ADR-0003 多路径架构描述
