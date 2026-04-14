# OmniMemora

**Memory Control Plane for AI Agents**

---

## 什么是 OmniMemora

OmniMemora is a **Memory Control Plane for AI Agents**.

It operates as an **optional context optimization layer** on top of existing AI systems.

---

## 它做什么

OmniMemora improves how context is constructed before entering the model by:

- selecting relevant memory
- compressing redundant information
- optimizing token usage

---

## 它不做什么

OmniMemora does NOT:

- own or replace memory systems
- act as a required execution path
- function as an orchestration layer
- control agent behavior
- store primary user memory

---

## 系统定位

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

## 核心价值

- improve context quality
- reduce token usage
- enable cross-session consistency (when used)

---

## 设计原则

- Local-first
- Weakly intrusive
- Replaceable
- Observable
- Policy-driven

---

## 一句话定义

OmniMemora = Control Plane that optimizes context, not memory.

---

## 文档体系（唯一权威）

所有工作必须从以下文件开始：

| 文件 | 角色 | 说明 |
|------|------|------|
| `0_blueprint/PRODUCT_CONSTITUTION.md` | 宪法 | 边界定义，不可动 |
| `0_blueprint/PRODUCT_DEFINITION.md` | 定义 | 唯一产品表达 |
| `0_blueprint/SYSTEM_ARCHITECTURE.md` | 结构 | 只描述结构 |
| `0_blueprint/EXECUTION_STRATEGY.md` | 策略 | 只描述如何优化 context |
| `0_blueprint/ROADMAP.md` | 路线 | 只描述阶段目标 |
| `0_blueprint/references/EXECUTION_GUARDRAILS.md` | 防火墙 | 所有实现行为的强制约束 |

**优先级顺序：**
EXECUTION_GUARDRAILS > CONSTITUTION > DEFINITION > ARCHITECTURE > STRATEGY > ROADMAP

---

## 目录结构

```
OmniMemora/
├── 0_blueprint/              # 全局产品蓝图（唯一权威来源）
│   ├── PRODUCT_CONSTITUTION.md
│   ├── PRODUCT_DEFINITION.md
│   ├── SYSTEM_ARCHITECTURE.md
│   ├── EXECUTION_STRATEGY.md
│   ├── ROADMAP.md
│   ├── references/
│   │   └── EXECUTION_GUARDRAILS.md  # 执行防火墙
│   └── archive/              # 历史文件归档
├── 1_architecture/           # 架构定义与接口契约
├── 2_product/               # 产品定义
├── 3_governance/            # 治理与边界
├── 4_core/                  # 核心逻辑
│   ├── adapter-raw/         # 旧版 adapter（v2.3）
│   └── local-runtime/        # Phase 1 本地 Runtime 实现（Go + SQLite）
├── 5_connectors/            # 连接器实现
├── 6_console/               # 用户控制台
├── 7_docs/                  # 对外文档
├── 8_migrations/            # 迁移记录
└── 9_adr/                   # 架构决策记录
```

---

## 各层职责

| 层 | 职责 | 关键规则 |
|----|------|----------|
| **0_blueprint/** | 产品级最高定义 | 任何变更必须先更新此层 |
| **1_architecture/** | 系统架构、技术选型、接口契约 | core 逻辑不能包含特定存储实现 |
| **3_governance/** | 仓库边界、命名规范、PR checklist | 必须通过 EXECUTION_GUARDRAILS 检查 |
| **4_core/** | 核心逻辑实现 | 包含 Phase 1 本地 Runtime |
| **5_connectors/** | 各终端 connector/skill/plugin | 必须完全隔离 |
| **6_console/** | Token Savings Meter 核心展示 | — |
| **8_migrations/** | 架构迁移、数据迁移 | — |

---

## 强制工作流

任何实现前必须：

1. **阅读 0_blueprint/** — 理解边界、定义、结构
2. **通过 EXECUTION_GUARDRAILS.md** — 6 项检查必须全部通过
3. **明确列出检查结果** — 若违反，停止并说明原因
4. **不允许"先做再补"**

**Violation = reject.**

---

## Phase 1 实现状态

### local-runtime (Go + SQLite)

**位置:** `4_core/local-runtime/`

**已实现：**
- `GET /health` — 健康检查
- `POST /memory/write` — 写入记忆
- `POST /memory/search` — 搜索记忆
- `POST /memory/query` — 查询记忆
- `GET /metrics` — 本地 metering 聚合
- `POST /connector/register` — Connector 注册
- `GET /connector/list` — Connector 列表

**核心特性：**
- 本地模式无需 API key
- Store 接口抽象（不绑定具体实现）
- ScopeRef 完整字段（tenant_id/user_id/workspace_id/agent_id/scope/sharing_mode）
- 默认 scope=agent, sharing_mode=isolated
- Scope 解析优先级：Header > Body > Config
- Metering event 绑定 ScopeRef
- 不同 agent 在 agent scope 下互不可见

**未实现：**
- `/memory/delete`
- `/runtime/stop` / `/runtime/restart`
- 向量检索 (sqlite-vss)
- MCP connector
- 云端同步
- backup/restore
- custom scope（返回 501）

**禁止事项：**
1. 不得把 1933 backend 作为主依赖
2. 不得跳过 Store 抽象直接在 service 写 SQL
3. 不得把 scope enforcement 放进 URI 路径判断
4. 不得新增 Blueprint 中未定义的 identity 结构
5. 不得实现 Cloud Control Plane / Billing / Console
6. 不得为了"先跑通"绕过治理边界

**启动命令：**
```bash
cd 4_core/local-runtime
go mod download
go build -o omnimemora-runtime .
./omnimemora-runtime
```

**测试命令：**
```bash
go test ./tests/... -v
```

### Python Engine (Control Plane)

**位置:** `4_core/logic/`

`4_core/logic/engine.py` is the single product capability entrypoint.

**职责：** 串联纯逻辑模块，执行一次完整的 context 优化决策

**调用链：**
```
filter → route/score → select top-k → pack context → token savings compute → quota check → meter artifact
```

**核心原则：**
- engine does not read config, does not touch filesystem, does not make HTTP calls
- all external dependencies injected via `OptimizationInput`
- 可独立单元测试（无需 mock HTTP 或文件）

**禁止事项：**
1. 不得 import httpx / fastapi / requests
2. 不得 import os / glob / open()
3. 不得 import config
4. 不得读写文件
5. 不得引用 `__file__`

**模块：**
| 文件 | 职责 |
|------|------|
| `engine.py` | 统一入口 — 唯一产品能力出口 |
| `rules.py` | FilterRules / RoutingRules 数据对象 |
| `filter.py` | 过滤判断 |
| `router.py` | 路由评分 |
| `v2_compute.py` | Token Savings 计算 |
| `dedup.py` | 写入去重 |
| `normalizer.py` | 归一化 |

**adapter 接入方式：**
```python
from 4_core.logic.engine import OptimizationInput, optimize_context
from 4_core.logic.rules import FilterRules, RoutingRules

input_data = OptimizationInput(
    query=query,
    candidate_memories=candidates,
    filter_rules=FilterRules(),
    routing_rules=RoutingRules(),
    current_usage=usage,
    monthly_quota=quota,
)
result = optimize_context(input_data)
```

---

## Backend Abstraction Layer

**状态:** 已落地 ✅
**完成日期:** 2026-04-12

### 架构

```
5_connectors/adapter/main.py
        ↓
    MemoryBackend Interface（统一抽象）
        ↓
    Backend Adapter
   ├─ OpenVikingBackend (1933) — compatibility full-CRUD backend
   └─ OmniMemoraRuntimeBackend (8765) — default query-path backend ✅
```

### 核心文件

| 文件 | 职责 |
|------|------|
| `5_connectors/adapter/backends/base.py` | `MemoryBackend` ABC + 统一数据模型 |
| `5_connectors/adapter/backends/factory.py` | Backend 注册与创建 |
| `5_connectors/adapter/backends/openviking_backend.py` | OpenViking (1933) 实现 |
| `5_connectors/adapter/backends/omnimemora_runtime_backend.py` | OmniMemora Runtime (8765) 实现 |

### 配置

```bash
MEMORY_BACKEND_TYPE=omnimemora_runtime   # 默认
MEMORY_BACKEND_URL=http://127.0.0.1:8765  # 内部后端（对外入口统一在 18011）
```

### 验证状态

| 功能 | 状态 | 说明 |
|------|------|------|
| Write | ✅ | `omnimemora_runtime` 已验证 |
| Search | ✅ | `omnimemora_runtime` 已验证 |
| Query (Engine) | ✅ | `/memory/query` 全链路通过 |
| Read | ⚠️ | not supported by `omnimemora_runtime` |
| Delete | ⚠️ | not supported by `omnimemora_runtime` |

### 架构约束

- `main.py` 只依赖 `MemoryBackend` 接口
- OpenViking 协议细节只存在于 `backends/openviking_backend.py`
- connector 层不直接调用任何 backend 特有协议

---

## 快速开始

1. **从 `0_blueprint/` 开始** — 理解产品愿景和架构决策
2. **阅读 `0_blueprint/references/EXECUTION_GUARDRAILS.md`** — 了解执行防火墙规则
3. **查看 `4_core/local-runtime/README.md`** — 了解 Phase 1 实现细节

---

## 核心锚点

We do not control memory.

We optimize what is selected into context.
