# TECHNICAL_ARCHITECTURE_MAP.md

**Status:** CURRENT
**Role:** 将 0_blueprint/SYSTEM_ARCHITECTURE.md 映射到代码层实现

---

**⚠️ This file must not introduce new structure, behavior, or product meaning beyond 0_blueprint/.**

---

# 一、本文件职责

只回答：
1. 每一层在仓库里对应哪里
2. 当前哪些已实现，哪些未实现
3. 哪些接口归属哪个目录

---

# 二、Blueprint → 代码目录映射

| Blueprint 层级 | 仓库目录 | 说明 |
|---------------|----------|------|
| Control Plane (Core Engine) | `4_core/logic/engine.py` | Python — 统一能力入口 |
| Control Plane (Local Runtime) | `4_core/local-runtime/` | Go + SQLite Phase 1 实现 |
| Connector Layer | `5_connectors/adapter/` | Python FastAPI — 运行时壳层 |
| Memory Plane | (外部) | 不属于产品，由用户/Agent 管理 |

---

# 三、分层边界（关键）

## 4_core/logic — 纯逻辑引擎

```
engine.py 是唯一产品能力入口
```

**职责：** 接收规则和候选数据，执行 filter → route → select → pack → meter 全流程

**严格约束：**
- ❌ 不得 import httpx / fastapi / requests
- ❌ 不得 import os / glob / open()
- ❌ 不得 import config
- ❌ 不得读写文件
- ✅ 所有数据/规则通过参数注入

**内部模块：**
| 文件 | 职责 |
|------|------|
| `rules.py` | FilterRules / RoutingRules 数据对象 |
| `filter.py` | 过滤判断 |
| `router.py` | 路由评分 |
| `v2_compute.py` | Token Savings 计算（无文件 I/O） |
| `dedup.py` | 写入去重 |
| `normalizer.py` | 归一化 |
| `engine.py` | 统一入口 |

## 5_connectors/adapter — 运行时壳层

**职责：** 请求接入、认证、数据获取、结果持久化

**边界：**
- ✅ 读取 config / 环境变量
- ✅ 调用 memory backend（通过 MemoryBackend 接口）
- ✅ 构造 OptimizationInput 并调用 engine
- ✅ 持久化 meter artifact
- ❌ 不实现产品决策逻辑
- ❌ 不直接调用任何 backend 特有协议（viking://, /api/v1/ 等）

**内部模块：**
| 文件 | 职责 |
|------|------|
| `main.py` | FastAPI 入口、请求处理 |
| `config.py` | 配置读取 |
| `access.py` | 认证与租户注册表 |
| `meter_store.py` | meter 持久化 + usage 聚合 |

---

# 四、调用链

```
HTTP Request
    ↓
5_connectors/adapter/main.py
    ├─ config.py 读取配置
    ├─ access.py 认证
    ├─ meter_store.get_tenant_current_usage() 获取配额
    ├─ get_memory_backend() → MemoryBackend 接口
    │       └─ OmniMemoraRuntimeBackend (8765) — active backend
    ├─ backend.search() / backend.write() — 统一 memory 操作
    ├─ 组装 OptimizationInput
    └→ 4_core/logic/engine.optimize_context()
            ↓
    OptimizationResult
            ↓
5_connectors/adapter/main.py
    ├─ store_meter() → meter_store.py
    └→ HTTP Response
```

---

# 五、接口落点

| 接口 | 归属 | 说明 |
|------|------|------|
| `/memory/query` (V2) | `5_connectors/adapter/main.py` | 统一查询入口，走 engine |
| `/memory/write` | `5_connectors/adapter/main.py` | 写入记忆 |
| `/usage/token-savings` | `5_connectors/adapter/main.py` | usage 聚合 |
| `engine.optimize_context()` | `4_core/logic/engine.py` | 唯一产品能力入口 |
| `FilterRules` / `RoutingRules` | `4_core/logic/rules.py` | 规则注入对象 |

---

# 六、最小暴露实现映射（仅映射，不新增产品定义）

- `4_core/logic/engine.py` 内部可维护候选、评分和路由中间信息（如 `_score`、`_final_score`），用于内部选择与计量。
- `packed_context` 作为注入 LLM 的 context 结果；候选集、评分过程、策略细节不应进入该字段。
- `5_connectors/adapter/main.py` 中 `meter_artifact` 与 `explanation` 属于控制面观测信息，不属于 LLM context 注入内容。

---

# 七、约束

本文件不定义产品，只反映 0_blueprint/ 的实现映射。

若与 0_blueprint/ 冲突，以 0_blueprint/ 为准。

---

# 八、多接入接口架构（已修订 2026-04-13）

> 详细定义见 `9_adr/ADR-0003-interface-access-paths.md`（已同步修订）。

## 架构原则：多接口，单路径

**产品路径唯一**，所有协议接入最终收敛到 Python Adapter（:18011）。

```
  MCP ──┐
  CLI ──┼──→ Python Adapter (:18011) ──→ Context Compiler ──→ LLM
  REST ─┤
  Wrap ─┘
```

## 端口约定

| 端口 | 角色 | 说明 |
|------|------|------|
| **:18011** | 统一产品入口 | Context Compiler + Token Savings + Metering |
| **:8765** | Local Memory Plane | Go Runtime，仅存储/检索，**非产品入口** |

## 接口定义

| 接口 | 协议 | 入口端口 |
|------|------|---------|
| MCP | HTTP/SSE + JSON-RPC | :18011 |
| CLI | HTTP REST | :18011 |
| REST | HTTP JSON | :18011 |
| Wrapper | subprocess | :18011 |

## 调用链（统一）

```
HTTP/SSE Request
    ↓
5_connectors/adapter/main.py（:18011）
    ├─ MCP Protocol Adapter（/mcp + /sse + /messages）
    ├─ REST Adapter（/memory/query 等）
    ├─ access.py 认证
    ├─ meter_store.get_tenant_current_usage() 获取配额
    ├─ backend.search() / backend.write()
    │       └─ OmniMemoraRuntimeBackend（:8765）— 仅作存储层
    ├─ 组装 OptimizationInput
    └→ 4_core/logic/engine.optimize_context()
            ↓
    OptimizationResult
            ↓
5_connectors/adapter/main.py
    ├─ store_meter() → meter_store.py
    └→ HTTP Response（统一数据结构）
```

---

# 九、Backend Abstraction（Current）

> **Status:** CURRENT
> **Reference:** `docs/spec/SPEC-BACKEND-ABSTRACTION-001.md`

## 9.1 Active contract

```
5_connectors/adapter/main.py
        ↓
    MemoryBackend Interface（统一抽象）
        ↓
    OmniMemoraRuntimeBackend (8765) — active backend
```

## 9.2 Active files

| 文件 | 职责 |
|------|------|
| `5_connectors/adapter/backends/base.py` | `MemoryBackend` ABC + 统一数据模型 |
| `5_connectors/adapter/backends/factory.py` | Backend 创建与 retired-type 拒绝 |
| `5_connectors/adapter/backends/omnimemora_runtime_backend.py` | Active runtime backend 实现 |

## 9.3 Active config surface

| 配置项 | 说明 |
|--------|------|
| `memory_backend.backend_type` | `omnimemora_runtime`（唯一 active 类型） |
| `MEMORY_BACKEND_URL` | Runtime backend 地址（默认 `http://127.0.0.1:8765`） |
| `MEMORY_BACKEND_API_KEY` | Runtime backend API key（可选） |

## 9.4 Legacy boundary

- Legacy backend abstraction docs are archive-only under `1_architecture/archive/legacy/backend_abstraction/`.
- Archive material is not a current implementation contract.
