# OmniMemora — Product Definition (Single Source of Truth)

## 1. What it is

OmniMemora is a **Memory Control Plane for AI Agents**.

It operates as an **optional context optimization layer** on top of existing AI systems.

### Product Vision

> Keep it on, or things get worse.

---

## 2. What it does

OmniMemora improves how context is constructed before entering the model by:

- selecting relevant memory
- compressing redundant information
- optimizing token usage
- keeping only minimal necessary results for LLM input

---

## 3. What it does NOT do

OmniMemora does NOT:

- own or replace memory systems
- act as a required execution path
- function as an orchestration layer
- control agent behavior
- store primary user memory
- expose strategy/candidate set/scoring/control-plane metadata to LLM

---

## 4. Position in the system

```
Agent (ChatGPT / Codex / OpenClaw)
↓ (optional call)
OmniMemora (Control Plane)
↓
Optimized Context
↓
LLM
```

---

## 5. Control definition

OmniMemora does NOT control memory.

It **optimizes what is selected into context**.

Context for LLM is the **result**, not the decision process.

---

## 6. Core value

- improve context quality
- reduce token usage
- enable cross-session consistency (when used)

---

## 7. Design principles

- Local-first
- Weakly intrusive
- Replaceable
- Observable
- Policy-driven

---

## 8. One-line definition

OmniMemora = Control Plane that optimizes context, not memory.

---

## 9. Architecture: Unified Entry（统一入口）

### 9.1 核心原则：单一路路

> **产品路径必须唯一，不可分裂。**

OmniMemora 只有一个产品入口，所有协议接入（MC

P/CLI/REST/Wrapper）最终都收敛到同一条核心路径：

```
Agent
  ↓
OmniMemora Unified Entry
  ↓
Context Compiler / Control Plane
  ↓
LLM
```

错误的多路径结构（禁止出现）：

```
Agent
  ↓
┌─→ Go Runtime (8765) ──→ ???
│
└─→ Python Adapter (18011) ──→ ???

（功能口径不一致，数据结构不一致，用户体验不一致）
```

### 9.2 多接口，单路径

统一入口不等于单一协议。对外兼容多种接入协议，但内部只允许一条产品路径：

```
  MCP ──┐
  CLI ──┼──→ Unified Interface Layer ──→ Core Compiler
  REST ─┤
  Wrap ─┘
```

- **MCP**：通用 Agent 生态标准接入面
- **CLI**：本地优先路径，低延迟
- **REST**：工具链 / CI/CD / 编排系统
- **Wrapper**：策略验证与实验

所有接口都是**协议适配层**，不是产品路径分支。协议可以替换，核心路径不分裂。

### 9.3 可选：能力模块，不是产品路径

OmniMemora 默认启用完整核心能力。用户可以关闭增强模块，但不关闭主路径：

```
Unified Entry
   ↓
[ module toggles ]
   ├─ token_optimization  on/off
   ├─ compression         on/off
   ├─ feedback            on/off
   └─ policy_mode         permissive/strict
```

关闭模块仍然走同一条主路径，只是该模块不生效。

这与"可选路径"的本质区别：

| 概念 | 正确 | 错误 |
|------|------|------|
| 可选 | 用户可关闭增强模块 | 用户可选择不走主路径 |
| 默认 | 默认启用完整能力 | 默认不启用，绕路走 |
| 路径 | 始终唯一 | 分裂为多条路径 |

### 9.4 统一入口的技术表达

无论从哪个端口/协议接入，最终执行的都是同一个 `Context Compiler`：

```
Port 8765 (Go Runtime MCP)
  ↓
  ┌─────────────────────────┐
  │  Protocol Adapter       │ ← 把 MCP JSON-RPC 转为内部调用
  └──────────┬──────────────┘
             ↓
Port 18011 (Python Adapter REST)
  ↓
  ┌─────────────────────────┐
  │  Protocol Adapter       │ ← 把 REST JSON 转为内部调用
  └──────────┬──────────────┘
             ↓
  ┌──────────────────────────────────────┐
  │  Unified Interface Layer             │
  │  ┌────────────────────────────────┐ │
  │  │  Context Compiler (Core)      │ │
  │  │  engine.optimize_context()    │ │
  │  │  - filter                      │ │
  │  │  - route_score                 │ │
  │  │  - dedup                       │ │
  │  │  - select                      │ │
  │  │  - pack                        │ │
  │  │  - meter                       │ │
  │  └────────────────────────────────┘ │
  │  ┌────────────────────────────────┐ │
  │  │  Metering & Trace Store       │ │
  │  └────────────────────────────────┘ │
  └──────────────┬─────────────────────┘
                 ↓
           Structured JSON
           { saved_tokens, ratio,
             selected_memories, ... }
```

### 9.5 技术实现约束

1. **所有接入协议共享同一个 Context Compiler 实例**
2. **所有请求共享同一个 metering pipeline**
3. **所有响应返回同一个数据结构**（不可因接入协议不同而返回不同数据结构）
4. **Go Runtime (8765) 不得自行实现独立的 Context Assembly 逻辑**，必须调用统一 Context Compiler

---

## 10. 接口行为约束（来自 ADR-0003 修订版）

| 接口 | 协议 | 入口端口 | 是否直接调用 Core |
|------|------|---------|------------------|
| MCP | SSE + JSON-RPC | 18011 (Python Adapter) | 是，统一 Context Compiler |
| CLI | HTTP REST | 18011 (Python Adapter) | 是，统一 Context Compiler |
| REST | HTTP JSON | 18011 (Python Adapter) | 是，统一 Context Compiler |
| Wrapper | subprocess | 18011 (Python Adapter) | 是，统一 Context Compiler |

> **注意**：Go Runtime (8765) 仅作为 Local Memory Plane，不承载产品入口功能。
> 产品入口统一在 Python Adapter (18011)。

---

## 11. 非目标（必须明确）

OmniMemora 不做：

- AI Agent 本体
- 模型服务
- 数据存储平台
- 单一 memory server
- 云端承载主记忆
- 多条产品路径
- 协议相关功能（orchestration / tool system）
