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

OmniMemora 只有一个产品入口。所有协议接入（MCP/CLI/REST/Wrapper）最终都收敛到同一条核心路径。

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

### 关键约束

**所有接口统一从 Python Adapter (18011) 接入。**

Go Runtime (8765) 的定位重新明确：
- **仅作为 Local Memory Plane**（存储、检索、scope 治理）
- **不承载产品入口功能**
- **不实现独立的 Context Assembly / Token Savings 逻辑**

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
```

### 6.3 端口约定

| 端口 | 角色 | 备注 |
|------|------|------|
| 8765 | Local Memory Plane（Go Runtime） | 仅存储/检索，**非产品入口** |
| 18011 | Unified Interface Layer（Python Adapter） | **唯一产品入口**，所有协议统一接入 |

---

## 七、决策记录

- **DECISION-0003-01**：OmniMemora 产品路径唯一，所有协议接入收敛到 Python Adapter (18011)
- **DECISION-0003-02**：Go Runtime (8765) 仅作为 Local Memory Plane，不承载产品入口
- **DECISION-0003-03**：所有响应返回统一数据结构，不得因协议不同而分化
- **DECISION-0003-04**：能力模块可配置（token_optimization / compression 等），但产品路径不可选

---

## 八、溯源

- 产品宪法：`0_blueprint/PRODUCT_CONSTITUTION.md`
- 产品定义：`0_blueprint/PRODUCT_DEFINITION.md`（已同步修订）
- 本文档替代：原 ADR-0003 多路径架构描述
