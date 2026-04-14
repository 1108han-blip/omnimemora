# RUNTIME_ARCHITECTURE.md

**Status:** FINAL (Phase 2c.5)
**Source of Truth:** Product Constitution / DECISION_LEDGER.md / Global Product Blueprint / Roadmap / Bootstrap / Memory Scope Model
**Role:** OmniMemora 本地 Runtime 的代码施工蓝图
**Last Updated:** 2026-04-09
**Phase 2c.5 Update:** `/memory/search` 最终形态，ctxAssembler 单一路径，cache 禁用

---

# 一、目标与定位

## 1.1 一句话定义

Local Runtime 是 OmniMemora 的默认 Memory Plane 实现，负责在用户本地执行记忆写入、检索、查询、scope 治理与计量事件产生。

## 1.2 非目标

- 不承担云端 billing
- 不承担 console UI
- 不作为 cloud-hosted memory service
- 不绑定单一 backend

## 1.3 架构位置

```
Connector → Local Runtime →（可选）Cloud Control Plane
```

---

# 二、设计原则

1. **Local First** — 默认在本地运行，不要求网络
2. **Cloud Optional** — 云端增强，不影响本地独立运行
3. **Default Isolated** — scope 默认隔离
4. **Explicit Sharing** — 共享必须显式配置
5. **Single Runtime** — 每个用户/workspace 一个实例
6. **All Components Replaceable** — store / engine / model 均可替换
7. **Full Traceability** — 每个请求必须具备完整 trace context

---

# 三、Runtime 职责边界

## 3.1 应该负责

- memory write / query / search / delete
- local store 管理
- scope governance（执行）
- local policy 执行（最小必要：dedup / compile / scope filtering）
- **metering event 产生**（核心职责）
- local config / lifecycle / health
- connector 注册与管理
- local metrics API

## 3.2 不应该负责

- 主云端托管
- billing 结算
- 多租户 SaaS console
- connector UI
- 云端 policy 存储
- 跨 tenant 的数据聚合

---

# 四、目录结构

```
runtime/
├── api/                    # HTTP server, routing, middleware
├── app/                    # Application core, use cases
├── config/                 # Config loading, validation, migration
├── scope/                  # Scope registry, scope enforcement logic
├── store/                  # Storage abstraction layer + default impl
├── policy/                 # Local policy: dedup, compile, scope filtering
├── metering/               # Metering event production, local aggregation
├── sync/                   # Optional cloud sync (metering events, policy pull)
├── lifecycle/              # Start, stop, restart, health, update, migration
├── connector/              # Connector registry, connector protocol
└── tests/                  # Unit + integration tests
```

## 逐目录职责说明

| 目录 | 职责 |
| --- | --- |
| `api/` | HTTP server、路由、中间件（request_id 注入、scope 注入、logging） |
| `app/` | Use case 编排，memory write/query/search/delete 的业务逻辑 |
| `config/` | 配置加载、校验、持久化、迁移 |
| `scope/` | Scope registry、scope enforcement、sharing_mode 校验 |
| `store/` | 存储抽象层 + file-based / SQLite 默认实现 |
| `policy/` | 本地 dedup、compile、scope-aware filtering |
| `metering/` | Metering event 产生、本地 metrics 聚合 |
| `sync/` | 可选云端同步（metering 上报、policy 下发） |
| `lifecycle/` | 启动/停止/重启/健康检查/升级/迁移 |
| `connector/` | Connector 注册表、connector 协议处理 |

---

# 五、核心数据模型

## 5.1 RuntimeConfig

```json
{
  "version": "1.0",
  "mode": "local",
  "local": {
    "endpoint": "http://127.0.0.1:8765",
    "data_path": "~/.omnimemora/runtime",
    "db_type": "sqlite",
    "log_level": "info"
  },
  "cloud": {
    "enabled": false,
    "base_url": null,
    "api_key": null,
    "sync_interval_seconds": 300
  },
  "scope": {
    "default": "agent",
    "default_workspace": "default",
    "default_sharing_mode": "isolated"
  },
  "cache": {
    "enabled": true,
    "max_entries": 10000,
    "ttl_seconds": 3600
  }
}
```

## 5.2 ScopeRef

```json
{
  "tenant_id": "t_xxxxx",
  "user_id": "u_xxxxx",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "scope": "workspace",
  "sharing_mode": "shared"
}
```

## 5.3 MemoryRecord

```json
{
  "memory_id": "mem_xxxxx",
  "content": "string",
  "content_hash": "sha256:xxxxx",
  "metadata": {
    "source": "claude_code",
    "tags": ["project", "backend"],
    "original_size": 1024,
    "compressed_size": 256
  },
  "scope_ref": {
    "tenant_id": "t_xxxxx",
    "user_id": "u_xxxxx",
    "workspace_id": "proj_alpha",
    "agent_id": "claude_code",
    "scope": "workspace",
    "sharing_mode": "shared"
  },
  "created_at": "2026-04-08T00:00:00Z",
  "updated_at": "2026-04-08T00:00:00Z",
  "last_accessed_at": "2026-04-08T00:00:00Z",
  "access_count": 0,
  "expires_at": null
}
```

## 5.4 MeteringEvent

```json
{
  "event_id": "evt_xxxxx",
  "request_id": "req_xxxxx",
  "event_type": "memory_write | memory_query | memory_search",
  "user_id": "u_xxxxx",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "scope": "workspace",
  "sharing_mode": "shared",
  "input_tokens": 1000,
  "compressed_tokens": 250,
  "saved_tokens": 750,
  "query_count": 1,
  "recall_hits": 3,
  "recall_hit_rate": 0.75,
  "timestamp": "2026-04-08T00:00:00Z",
  "runtime_version": "1.0.0",
  "store_type": "sqlite",
  "raw_tokens": 0,
  "assembled_hits": 0
}
```

> **Phase 2b 更新**：`raw_tokens` 和 `assembled_hits` 仅在 `event_type=memory_search` 且 `assemble_context=true` 时有效，否则为 0。`saved_tokens` 在非 assembly 搜索时为 0（诚实口径，不伪造）。

## 5.5 QueryResult

```json
{
  "request_id": "req_xxxxx",
  "query": "string",
  "results": [
    {
      "memory_id": "mem_xxxxx",
      "content": "string",
      "score": 0.95,
      "scope": "workspace",
      "created_at": "2026-04-08T00:00:00Z",
      "metadata": {}
    }
  ],
  "total": 1,
  "scope_applied": "workspace",
  "took_ms": 12
}
```

## 5.6 RecallResult

```json
{
  "request_id": "req_xxxxx",
  "recall_type": "dedup",
  "hit": true,
  "matched_memory_id": "mem_xxxxx",
  "score": 0.98,
  "scope_applied": "agent",
  "took_ms": 3
}
```

---

# 六、Memory Scope & Sharing 模型落地

## 6.1 支持的 scope

| Scope | 说明 | 默认行为 |
| --- | --- | --- |
| `user` | 用户级记忆 | 跨 workspace 隔离，仅自身可写 |
| `workspace` | 项目/工作空间记忆 | 同 workspace 内共享读写 |
| `agent` | Agent 私有记忆 | 仅 agent 自身可读写 |
| `custom` | 自定义共享域 | 显式配置后共享 |

## 6.2 支持的 sharing_mode

| Mode | 说明 |
| --- | --- |
| `isolated` | 完全隔离，不可共享 |
| `shared` | 同 scope 内可读写共享 |
| `shared_read_only` | 同 scope 内仅可读 |
| `custom` | 按 custom_policy 规则共享 |

## 6.3 默认规则

- **默认 scope**：`agent`
- **默认 sharing_mode**：`isolated`
- **workspace 共享**：必须显式开启 `sharing_mode: "shared"`
- **custom scope**：必须命名并声明成员

## 6.4 典型场景

### 场景 A：单用户多 agent 隔离

```
用户 u_001
  ├── Agent claude_code (agent scope, isolated)
  │     └── 只能读写自己的 memory
  └── Agent codex (agent scope, isolated)
        └── 只能读写自己的 memory
```

### 场景 B：单用户同项目跨 agent 共享

```
用户 u_001 / workspace proj_alpha
  ├── Agent claude_code (workspace scope, shared)
  │     └── 可读写 proj_alpha 的 shared memory
  └── Agent codex (workspace scope, shared)
        └── 可读写 proj_alpha 的 shared memory
```

### 场景 C：Docker OpenClaw 独立隔离

```
Container openclaw_1 (user scope, isolated)
  └── 独立 user scope，不与其他 container 共享
```

### 场景 D：多用户共享 workspace

```
Workspace proj_alpha (workspace scope, shared_read_only)
  ├── User u_001 (read_only)
  │     └── 可读 proj_alpha 内所有 memory
  └── User u_002 (read_only)
        └── 可读 proj_alpha 内所有 memory
```

## 6.5 Dedup / Recall / Query 的 scope 边界

| 操作 | Scope 边界 |
| --- | --- |
| **Dedup（去重）** | 同 scope 内去重（`content_hash` 唯一性） |
| **Recall（记忆召回）** | 同 scope 内召回 |
| **Query（语义检索）** | 同 scope 内检索 |
| **Write** | 按 scope_ref 写入对应存储区域 |

---

# 七、Context Assembly Pipeline（FINAL Phase 2c.5）

## 7.1 定义

```text
Context Assembly = Strategy-driven selection + token-bounded compression
```

Context Assembly 是对已召回结果的轻量选择与压缩，**不做**：
- query understanding / intent classification
- task routing / orchestration
- multi-stage pipeline（recall → rerank → refine）
- adaptive learning / feedback loop

## 7.2 /memory/search 执行流程（FINAL）

```text
1. SQL recall（scope enforcement 最前）
   ↓
2. Scoring（已有 Phase 2a 逻辑）
   ↓
3. Context Assembly（ctxAssembler 单一路径）
   ├─ Strategy selection
   ├─ Mode (precise/balanced/aggressive)
   └─ Token budget control
   ↓
4. Metering
```

**关键约束（DECISION 14）**：
- 所有 context assembly 必须通过 `ctxAssembler.AssembleContext()`
- 禁止多实现路径
- legacy `assembleContext()` 已完全移除

## 7.3 Strategy 列表

| Strategy | 说明 |
| --- | --- |
| `topk_excerpt` | 按 efficiency score 排序（score / normalized_tokens） |
| `recency_boost_select` | 增加 recency boost，再按 efficiency score 排序 |
| `diversity_select` | 按内容去重（FNV hash of first 200 chars） |
| `auto` | 自动选择策略（基于 query 特征）→ resolve 为上述三者之一 |

## 7.4 Context Mode

| Mode | TokenBudget | MaxItems | 说明 |
| --- | --- | --- | --- |
| `precise` | 300 | 3 | 精准模式，少量高质量 |
| `balanced`（默认） | 800 | 6 | 平衡模式 |
| `aggressive` | 1500 | 10 | 激进模式，尽可能多 |

## 7.5 Efficiency Score 规范化（DECISION 12 补充）

```go
func normalizedTokenCost(tokens int) float64 {
    if tokens <= 0 {
        return 1.0
    }
    if tokens < 80 {
        return 80.0 // token floor to prevent short fragments from dominating
    }
    return float64(tokens)
}

func efficiencyScore(tokens int, score float64) float64 {
    return score / normalizedTokenCost(tokens)
}
```

## 7.6 Deterministic 输出

给定相同输入：
- 相同 query
- 相同 recall 结果
- 相同 strategy
- 相同 mode

→ **必须返回完全相同的 assembled context**

---

# 八、本地 API 设计

## 7.1 MVP 端点清单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 健康检查 |
| `GET` | `/metrics` | 本地 metrics |
| `POST` | `/memory/write` | 写入记忆 |
| `POST` | `/memory/query` | 语义查询 |
| `POST` | `/memory/search` | 关键词搜索 |
| `POST` | `/memory/delete` | 删除记忆 |
| `POST` | `/connector/register` | Connector 注册 |
| `POST` | `/connector/deregister` | Connector 注销 |
| `GET` | `/connector/list` | Connector 列表 |
| `GET` | `/scope/context` | 当前 scope 上下文 |
| `POST` | `/runtime/stop` | 停止 runtime |
| `POST` | `/runtime/restart` | 重启 runtime |

---

## 7.2 端点详细说明

### POST /memory/write

**输入：**

```json
{
  "content": "string (required)",
  "metadata": {} (optional),
  "scope": "agent | workspace | user | custom (optional, default: agent)",
  "agent_id": "string (optional, auto-detect)",
  "workspace_id": "string (optional)",
  "tags": [] (optional),
  "request_id": "string (optional, auto-generate)"
}
```

**ScopeRef 来源（按优先级）：**

1. 请求 body 显式传入
2. 请求 header `X-OmniMemora-Scope` 传入
3. Runtime config 默认值

**输出（201）：**

```json
{
  "memory_id": "mem_xxxxx",
  "status": "written",
  "scope": "agent",
  "sharing_mode": "isolated",
  "created_at": "2026-04-08T00:00:00Z",
  "request_id": "req_xxxxx"
}
```

**Scope enforcement 逻辑：**

1. 验证 `agent_id` 与 runtime 注册的 connector agent_id 匹配
2. 验证 `scope` 与 `sharing_mode` 组合有效
3. 执行本地 dedup（同 scope 内 content_hash 去重）
4. 写入 store
5. 产生 metering event

**Metering 记录：**

- `input_tokens`: content 的 token 数（估算）
- `compressed_tokens`: 压缩后 token 数
- `saved_tokens`: `input_tokens - compressed_tokens`
- `query_count`: 0（write 操作）
- `recall_hits`: 0

---

### POST /memory/query

**输入：**

```json
{
  "query": "string (required)",
  "scope": "agent | workspace | user | custom (optional, default: agent)",
  "agent_id": "string (optional)",
  "workspace_id": "string (optional)",
  "limit": 10 (optional, default: 10),
  "request_id": "string (optional)"
}
```

**输出（200）：**

```json
{
  "request_id": "req_xxxxx",
  "results": [...],
  "total": 1,
  "scope_applied": "agent",
  "took_ms": 12
}
```

**Scope enforcement 逻辑：**

1. 解析 scope context
2. 确定检索边界（同 scope 内）
3. 执行语义检索（vector similarity 或 keyword search）
4. 返回结果（自动过滤无权限的 memory）

**Metering 记录：**

- `query_count`: 1
- `recall_hits`: 匹配的 memory 数量
- `input_tokens`: query 的 token 数
- `saved_tokens`: 0（query 不节省 token）

---

### POST /memory/search

**输入：**

```json
{
  "keyword": "string (required)",
  "scope": "string (optional)",
  "agent_id": "string (optional)",
  "workspace_id": "string (optional)",
  "limit": 10 (optional),
  "request_id": "string (optional)",
  "options": {
    "include_breakdown": false,
    "assemble_context": false,
    "context_limit": 4,
    "max_context_tokens": 800
  }
}
```

**options 字段说明（FINAL Phase 2c.5）：**

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `include_breakdown` | bool | false | 返回 score_breakdown |
| `assemble_context` | bool | false | 是否返回 context 块 |
| `context_limit` | int | 4 | 参与 assembly 的最大条数（1~5） |
| `max_context_tokens` | int | 800 | assembled context 的 token 上限 |
| `context_strategy` | string | "topk_excerpt" | 选择策略：topk_excerpt / recency_boost_select / diversity_select / auto |
| `context_mode` | string | "balanced" | 模式：precise / balanced / aggressive |

**输出（200）：**

```json
{
  "request_id": "req_xxxxx",
  "results": [...],
  "total": 1,
  "scope_applied": "workspace",
  "took_ms": 5,
  "context": {
    "assembled": true,
    "strategy": "topk_excerpt_merge",
    "items": [
      {
        "memory_id": "mem_xxxxx",
        "excerpt": "...",
        "score": 0.91,
        "token_estimate": 48
      }
    ],
    "combined_text": "【Memory mem_xxxxx】\n...",
    "raw_tokens": 640,
    "compressed_tokens": 220,
    "saved_tokens": 420
  }
}
```

> **context 字段说明**：`context` 仅在 `options.assemble_context=true` 时返回（Phase 2b）。`results` 结构保持不变，向后兼容。

**Metering 记录（FINAL Phase 2c.5）：**

| 场景 | raw_tokens | compressed_tokens | saved_tokens | assembled_hits |
| --- | --- | --- | --- | --- |
| `assemble_context=false` | 0 | 0 | 0 | 0 |
| `assemble_context=true` | sum(selected_items.tokens) | assembled_context.total_tokens | max(raw - compressed, 0) | len(selected_items) |

**关键约束（DECISION 10）：**
- 禁止使用 `raw_tokens = compressed * N` 反推
- `assemble_context=false` 时所有 token 字段必须全 0
- `context_strategy=auto` 时 response 和 metering 均记录 resolved strategy

**Cache 状态（DECISION 15）：**
- Cache 组件保留但**未启用**
- 原因：scope 安全优先
- 后续需独立 scope-isolation 审计才能上线

---

### POST /memory/delete

**输入：**

```json
{
  "memory_id": "string (required)",
  "scope": "string (optional)",
  "request_id": "string (optional)"
}
```

**Scope enforcement：**

- 仅 creator（相同 agent_id）或同 scope 管理者可删除

**输出（200）：**

```json
{
  "memory_id": "mem_xxxxx",
  "status": "deleted",
  "request_id": "req_xxxxx"
}
```

---

### GET /health

**输出（200）：**

```json
{
  "status": "ok",
  "version": "1.0.0",
  "mode": "local",
  "uptime_seconds": 3600,
  "store_type": "sqlite",
  "registered_connectors": 2,
  "memory_count": 1542
}
```

**错误（503）：**

```json
{
  "status": "unhealthy",
  "reason": "store_unavailable",
  "details": "SQLite database locked"
}
```

---

### GET /metrics

**输出（200）：**

```json
{
  "runtime": {
    "version": "1.0.0",
    "uptime_seconds": 3600,
    "mode": "local"
  },
  "totals": {
    "memory_count": 1542,
    "total_writes": 3200,
    "total_queries": 8900,
    "total_input_tokens": 1500000,
    "total_compressed_tokens": 380000,
    "total_saved_tokens": 1120000,
    "total_query_count": 8900,
    "total_recall_hits": 12000
  },
  "by_scope": {
    "agent": {
      "claude_code": {
        "memory_count": 520,
        "total_saved_tokens": 420000
      }
    },
    "workspace": {
      "proj_alpha": {
        "memory_count": 800,
        "total_saved_tokens": 600000
      }
    }
  },
  "by_day": [
    {"date": "2026-04-08", "saved_tokens": 120000, "query_count": 2100}
  ]
}
```

**说明：** `/metrics` 返回本地聚合数据，专供 Console 或本地调试使用。云端 billing 由 Control Plane 负责。

---

## 7.3 认证策略

### 本地模式（默认，cloud.enabled = false）

- **无需任何 token / API key**
- Connector 通过 localhost 连接 runtime
- Scope enforcement 通过 `X-OmniMemora-Agent` / `X-OmniMemora-User` header 验证身份

### 云增强模式（cloud.enabled = true）

- Runtime 持有云端 `cloud.api_key`
- Connector 持有用户云端 API key（用于 cloud Control Plane 身份验证）
- Runtime 访问云端时使用 `cloud.api_key`
- Metering events 上报云端时使用 `cloud.api_key`

### Header 约定

| Header | 说明 |
| --- | --- |
| `X-OmniMemora-Agent` | agent 标识 |
| `X-OmniMemora-User` | user 标识 |
| `X-OmniMemora-Workspace` | workspace 标识 |
| `X-OmniMemora-Request-Id` | 请求追踪 ID（可选，auto-generate） |

---

# 八、Store 抽象层

## 8.1 目标

Runtime 不绑定单一存储实现。所有 storage 操作通过抽象接口进行。

## 8.2 Store 接口

```go
type Store interface {
    // Write
    Write(ctx context.Context, record *MemoryRecord) error

    // Query (semantic search)
    Query(ctx context.Context, req *QueryRequest) (*QueryResult, error)

    // Search (keyword search)
    Search(ctx context.Context, req *SearchRequest) (*SearchResult, error)

    // Delete
    Delete(ctx context.Context, memoryID string, scopeRef *ScopeRef) error

    // Snapshot (backup)
    Snapshot(ctx context.Context, path string) error

    // Restore
    Restore(ctx context.Context, path string) error

    // Close
    Close() error
}

type QueryRequest struct {
    Query     string
    ScopeRef  *ScopeRef
    Limit     int
    RequestID string
}

type SearchRequest struct {
    Keyword   string
    ScopeRef  *ScopeRef
    Limit     int
    RequestID string
}
```

## 8.3 默认实现

**MVP 默认 store：SQLite + in-process vector**

| 组件 | 实现 | 说明 |
| --- | --- | --- |
| Memory records | SQLite | 行：memory_id, content, scope_ref, metadata, timestamps |
| Search index | SQLite FTS5 | 全文索引 |
| Vector similarity | sqlite-vss（扩展） | 向量检索（可选，MVP 可跳过） |
| Config | JSON file | `~/.omnimemora/runtime/config.json` |

**目录结构：**

```
~/.omnimemora/
├── config/
│   └── config.json
├── runtime/
│   ├── memory.db           # SQLite: memory records
│   ├── fts.db              # SQLite: FTS5 index
│   └── scope.db             # SQLite: scope registry
├── logs/
│   └── runtime.log
├── cache/
│   └── query_cache.db
├── backup/
│   └── memory_YYYYMMDD.db
└── bootstrap/
    └── bootstrap.lock
```

## 8.4 替换策略

未来可替换的 store 实现：

| Store 实现 | 适用场景 |
| --- | --- |
| `sqlite-store`（默认） | 单用户本地，MVP |
| `file-store` | 纯文件，无依赖 |
| `postgres-store` | 多 workspace，需要更强查询能力 |
| `chromadb-store` | 需要向量检索 |
| `cloud-store` | 作为可选增强（但不是主记忆存储） |

替换方式：实现 `Store` 接口，运行时通过 config 切换实现。

## 8.5 SQL Scope Enforcement 实现 (Phase 1)

**实现位置**: `store/sqlite_store.go` - `buildScopeFilter()` 函数

**SQL Scope Filter 模式**:

```sql
-- Agent Scope
SELECT ... WHERE tenant_id = ? AND scope = 'agent' AND agent_id = ?

-- Workspace Scope
SELECT ... WHERE tenant_id = ? AND scope = 'workspace' AND workspace_id = ?

-- User Scope
SELECT ... WHERE tenant_id = ? AND scope = 'user' AND user_id = ?
```

**关键约束**:

1. **tenant_id 必过滤**: 所有查询必须包含 `tenant_id = ?` 条件，无例外
2. **scope 精确匹配**: 使用字面量 `'agent'`/`'workspace'`/`'user'`，不使用变量
3. **workspace 不含 agent**: workspace scope 查询仅返回 `scope = 'workspace'` 的记录，不混入 agent scope

**tenant_id 过滤逻辑**:

```go
func buildScopeFilter(scopeRef *ScopeRef, query string) (string, []any) {
    // tenant_id 总是被过滤 - 无跨租户可见性
    if scopeRef.TenantID != "" {
        conditions = append(conditions, "tenant_id = ?")
        args = append(args, scopeRef.TenantID)
    } else {
        // 空 tenant_id 查询空租户（本地模式）
        conditions = append(conditions, "(tenant_id = '' OR tenant_id IS NULL)")
    }
    // ... scope 过滤
}
```

**验收通过的 SQL 模式**:

| 路径 | SQL Pattern | 状态 |
|------|-------------|------|
| Query | `WHERE tenant_id = ? AND scope = 'agent' AND agent_id = ?` | ✅ |
| QueryByHash | `WHERE tenant_id = ? AND scope = ? AND agent_id = ? AND workspace_id = ?` | ✅ |
| Delete | `WHERE tenant_id = ? AND scope = ? AND agent_id = ?` | ✅ (Phase 1.2) |

---

# 九、Policy 执行边界

## 9.1 Runtime 内最小 policy

| Policy | 说明 | scope 边界 |
| --- | --- | --- |
| **Dedup** | 同 scope 内 content_hash 去重 | 同 scope |
| **Compile** | 记忆压缩/摘要 | 同 scope |
| **Scope filtering** | 按 scope_ref 过滤读写 | 全局 |

## 9.2 Dedup 逻辑

```
Write 请求
    ↓
提取 content_hash
    ↓
查询同 scope 内是否存在相同 hash
    ↓
存在 → 返回 existing memory_id（不写入）
不存在 → 写入新记录
    ↓
产生 metering event（dedup_hit: true/false）
```

## 9.3 Cloud Policy 的关系

```
Local Runtime（离线可运行）
    │
    │ 可选：cloud.enabled = true
    ↓
Cloud Control Plane（policy 下发）
    │
    │ 下发内容：
    │ - retention policy
    │ - dedup sensitivity
    │ - compression level
    │ - custom scope rules
    ↓
Local Runtime（本地执行，接收后立即执行，不依赖网络）
```

**关键：Cloud Policy 下发后本地执行，不要求 runtime 持续在线。**

---

# 十、Metering 与 Token Savings

## 10.1 Runtime 必须产出的事件

每个 memory write 产生一个 `MeteringEvent`：

| 字段 | 说明 |
| --- | --- |
| `event_id` | 事件唯一 ID |
| `request_id` | 请求追踪 ID |
| `event_type` | `memory_write` / `memory_query` / `memory_search` |
| `input_tokens` | 原始 content 的 token 数（估算值） |
| `compressed_tokens` | 压缩后 token 数 |
| `saved_tokens` | `input_tokens - compressed_tokens` |
| `query_count` | 本次 query/search 操作计数 |
| `recall_hits` | 召回命中数（write=0, query=匹配数, search=recall总数） |
| `scope` | 操作的 scope |
| `workspace_id` | workspace 标识 |
| `agent_id` | agent 标识 |
| `timestamp` | 事件时间 |
| `raw_tokens` | Phase 2b：assembled 条目的全文 token 估算之和 |
| `assembled_hits` | Phase 2b：实际进入 context assembly 的条数 |

## 10.2 Token Savings 计算来源

```
Token Savings = input_tokens - compressed_tokens

估算方式（MVP）：
- input_tokens = content_length / 4（粗估中文/英文平均）
- compressed_tokens = deduplicated_content_length / 4

未来优化方向：
- 接入 tokenizer 精确计算
- 引入 compression ratio 配置
```

## 10.3 本地 metrics

`GET /metrics` 返回本地聚合数据（见 7.2 节）。

用途：Console 本地展示、云端同步前的本地缓存、调试。

## 10.4 云同步（可选，cloud.enabled = true）

```
Local Runtime
    │
    │ 异步后台同步（不阻塞主流程）
    │ sync_interval: 300s（可配置）
    │
    ├── 上报：MeteringEvent[] → Cloud Control Plane
    ├── 下发：Policy updates ← Cloud Control Plane
    │
    ↓
Cloud Control Plane（聚合 + Billing）
```

**同步失败不影响本地主流程。**

---

# 十一、Connector 集成方式

## 11.1 核心原则

> **Connector 只连接 Local Runtime，不直接连接云端 memory backend。**

## 11.2 接入方式

### Claude Code（MCP Server）

```json
{
  "mcpServers": {
    "omni-memory": {
      "command": "omnimemora-connector",
      "args": [
        "--mode", "mcp",
        "--runtime", "http://127.0.0.1:8765",
        "--agent", "claude_code",
        "--user", "u_xxxxx",
        "--workspace", "proj_alpha"
      ]
    }
  }
}
```

### Codex（HTTP Client）

```python
import httpx

client = httpx.Client(base_url="http://127.0.0.1:8765", timeout=10.0)
client.headers["X-OmniMemora-Agent"] = "codex"
client.headers["X-OmniMemora-User"] = "u_xxxxx"
client.headers["X-OmniMemora-Workspace"] = "proj_alpha"

# Write
client.post("/memory/write", json={"content": "test memory"})

# Query
client.post("/memory/query", json={"query": "test", "limit": 5})
```

### OpenClaw Plugin

```json
{
  "plugins": {
    "omni-memory": {
      "runtime": "http://127.0.0.1:8765",
      "agent_id": "openclaw",
      "user_id": "u_xxxxx",
      "workspace": "default"
    }
  }
}
```

## 11.3 统一 connector core

所有 connector 共享同一个 client 实现：

```
connector-core/
├── client.go           # 统一 HTTP client
├── types.go            # 统一 request/response 类型
├── errors.go           # 统一错误类型
└── retry.go            # 重试逻辑
```

## 11.4 错误处理

| 错误场景 | Runtime 返回 | Connector 行为 |
| --- | --- | --- |
| `runtime unavailable` | `503 Service Unavailable` | 指数退避重试（max 3次） |
| `scope mismatch` | `400 Bad Request` + reason | 记录错误，不重试 |
| `config invalid` | `500 Internal Server Error` | 记录错误，提示用户检查 config |
| `store full` | `507 Insufficient Storage` | 记录错误，提示清理或扩容 |

---

# 十二、Lifecycle 设计

## 12.1 Start

```
1. 加载 config.json
2. 校验 config schema version，必要时 migrate
3. 初始化 store（打开 SQLite 连接）
4. 初始化 scope registry
5. 初始化 policy engine
6. 启动 HTTP server（http://127.0.0.1:8765）
7. 注册已配置的 connectors（从 registry 恢复）
8. 初始化 metering collector
9. 启动后台 sync goroutine（如果 cloud.enabled = true）
10. 验证 /health 端点
```

## 12.2 Stop

```
1. 停止接受新请求（HTTP server graceful shutdown，30s timeout）
2. 等待处理中的请求完成
3. flush pending writes（落盘）
4. 持久化 scope registry
5. 持久化 metering 本地缓存
6. 关闭 store 连接
7. 写入 stop log
```

## 12.3 Restart

```
1. 执行 Stop
2. 执行 Start（config 重新加载，store 数据保持）
3. 验证 /health 端点
```

## 12.4 Health

| 检查项 | 说明 |
| --- | --- |
| **Liveness** | HTTP server 响应 /health |
| **Readiness** | store 可读可写 + scope registry 可用 |

## 12.5 Update / Migration

```
1. 下载新版本 binary
2. 验证 checksum
3. 备份当前数据（~/.omnimemora/backup/）
4. 执行 Stop
5. 替换 binary
6. 执行 Start
7. 验证 /health
8. 如失败：回滚 binary + 执行 Start
```

**Config migration：**

- `config.version` 字段用于判断是否需要迁移
- 迁移脚本位于 `config/migrate/vX_to_vY.go`

---

# 十三、配置与本地目录结构

## 13.1 本地目录总览

```
~/.omnimemora/
├── config/
│   ├── config.json           # 主配置
│   └── scope_registry.json   # scope 注册表
├── runtime/
│   ├── memory.db             # SQLite: memory records
│   ├── fts.db                # SQLite: FTS5 index
│   └── scope.db              # SQLite: scope data
├── logs/
│   └── runtime_YYYYMMDD.log  # 日志（按天轮转）
├── cache/
│   └── query_cache.db        # 查询缓存
├── backup/
│   └── memory_YYYYMMDD.db    # 备份
├── connectors/
│   └── registry.json         # connector 注册表
└── bootstrap/
    └── bootstrap.lock         # 安装锁（防止重复安装）
```

## 13.2 配置文件职责

| 文件 | 职责 |
| --- | --- |
| `config/config.json` | 主配置：mode、endpoint、cloud、scope defaults |
| `config/scope_registry.json` | scope 规则：custom scopes、sharing configs |
| `runtime/memory.db` | 记忆数据 |
| `runtime/fts.db` | 全文检索索引 |
| `connectors/registry.json` | connector 注册状态 |
| `bootstrap/bootstrap.lock` | 安装锁，标记已完成安装 |

---

# 十四、错误模型与可观测性

## 14.1 错误分类

| Error Type | HTTP Status | 说明 |
| --- | --- | --- |
| `ConfigError` | 500 | 配置文件缺失或格式错误 |
| `ScopeError` | 400 | scope 参数无效或 enforcement 失败 |
| `StoreError` | 500 | 存储读写失败（磁盘满、锁冲突） |
| `PolicyError` | 500 | 本地 policy 执行失败 |
| `SyncError` | 200（后台） | 云端同步失败，不影响主流程 |
| `ConnectorError` | 400 | connector 注册/注销失败 |

## 14.2 Traceability

每个请求必须具备以下 context：

| 字段 | 来源 | 说明 |
| --- | --- | --- |
| `request_id` | Header `X-OmniMemora-Request-Id` 或 auto-generate | 全链路追踪 |
| `user_id` | Header `X-OmniMemora-User` | 用户身份 |
| `workspace_id` | Header `X-OmniMemora-Workspace` 或 config default | workspace 标识 |
| `agent_id` | Header `X-OmniMemora-Agent` | agent 标识 |
| `scope` | 请求 body / config default | 记忆边界 |
| `timestamp` | server clock | 事件时间 |

## 14.3 日志策略

| Level | 使用场景 |
| --- | --- |
| `DEBUG` | 请求参数、中间状态、store SQL |
| `INFO` | 请求处理成功、connector 注册/注销、lifecycle 事件 |
| `WARN` | 云端同步失败（后台）、scope enforcement 触发、dedup hit |
| `ERROR` | store 错误、config 错误、connector 异常 |

---

# 十五、安全与隐私边界

## 15.1 本地优先

- **默认不把 memory 内容上传云端**
- Memory content 只存在于 `~/.omnimemora/runtime/` 目录
- 云端同步只同步 metering events 和 minimal metadata

## 15.2 云同步限制

当 `cloud.enabled = true` 时，上报内容：

| 内容 | 上报？ | 说明 |
| --- | --- | --- |
| Memory content | ❌ 不上报 | 始终本地存储 |
| Metering events | ✅ 上报 | input/compressed/saved tokens、counts |
| Scope metadata | ✅ 上报 | workspace_id、agent_id、scope 类型（无 content） |
| Config | ✅ 可选 | 仅当用户主动配置云端增强时 |

## 15.3 凭证管理

| 凭证 | 存储位置 | 说明 |
| --- | --- | --- |
| `cloud.api_key` | `config/config.json`（加密存储） | 云端 Control Plane 认证 |
| `cloud.base_url` | `config/config.json` | 云端 endpoint |
| 本地无凭证 | — | 本地模式无需任何凭证 |

---

# 十六、MVP 实施顺序

## Phase A：Runtime Skeleton

- [ ] 项目结构初始化（Go/Rust）
- [ ] Config 加载与校验
- [ ] Lifecycle（start/stop/health）
- [ ] 日志框架
- [ ] 基础错误模型

## Phase B：Memory API

- [ ] `POST /memory/write`（最小实现：直接落 SQLite）
- [ ] `POST /memory/query`（FTS5 关键词查询）
- [ ] `POST /memory/search`
- [ ] `POST /memory/delete`
- [ ] Dedup（content_hash 去重）

## Phase C：Scope Governance

- [ ] Scope registry
- [ ] `agent` scope 默认 isolated
- [ ] `workspace` scope + `shared` mode
- [ ] Scope enforcement（写入/读取/删除）
- [ ] Scope context header 解析

## Phase D：Metering

- [ ] MeteringEvent 数据模型
- [ ] `input_tokens` / `compressed_tokens` / `saved_tokens` 计算
- [ ] `GET /metrics` 本地聚合
- [ ] Metering 日志落盘

## Phase E：Connector Integration

- [ ] Connector registry
- [ ] `POST /connector/register`
- [ ] 统一 connector core（client lib）
- [ ] Claude Code MCP Server 接入
- [ ] Codex HTTP Client 接入
- [ ] OpenClaw Plugin 接入

## Phase F：Cloud Optional Hooks

- [ ] `cloud.enabled` 配置项
- [ ] Metering event 异步上报
- [ ] Policy 下发接收
- [ ] Cloud sync goroutine

---

# 十七、验收标准

| # | 标准 | 验证方式 |
| --- | --- | --- |
| 1 | 本地模式可独立运行（无网络） | 断网状态下 write/query 正常 |
| 2 | 无 API key 可使用 | 新安装无需任何 key，直接 write/query |
| 3 | agent scope 默认隔离 | 两个不同 agent 无法互读 memory |
| 4 | workspace scope 可显式共享 | 同一 workspace 的两个 agent 可共享 memory |
| 5 | Connector 能通过 localhost 调用 runtime | Claude Code / Codex / OpenClaw 均能连上 |
| 6 | Runtime 能产出 metering events | `GET /metrics` 返回正确的 totals |
| 7 | Token savings 可被后续 Console 消费 | MeteringEvent 格式正确，可被 Control Plane 聚合 |
| 8 | Scope enforcement 正确执行 | 跨 scope 读写被拒绝 |
| 9 | 本地 metrics 正确 | writes/queries/tokens 计数与实际操作一致 |
| 10 | Runtime 健康检查正常 | `GET /health` 返回 ok + 版本信息 |

---

# 十八、待确认项

以下项需要结合当前云端/代码现状校准，MVP 实施前必须明确：

| # | 待确认项 | 关联现状 |
| --- | --- | --- |
| 1 | **默认 store 实现** | 当前 artifact 中 adapter 用的是 Python + SQLite，还是纯 Go 实现？ |
| 2 | **Token 估算算法** | 当前是否有现成的 token 计算逻辑可以复用？ |
| 3 | **当前 connector 可复用部分** | `omni-openclaw-plugin` / `ov_enterprise_mcp_server.py` 如何对接本地 runtime？ |
| 4 | **Metering event 上报协议** | 当前云端 Control Plane 期望的 event 格式是什么？ |
| 5 | **Cloud policy 下发格式** | 当前是否有 policy 下发的 API 定义？ |
| 6 | **Vector similarity 实现** | MVP 是否需要向量检索，还是 FTS5 足够？ |
| 7 | **Backup/restore 策略** | 当前用户数据是否需要 backup 机制？ |
| 8 | **实现语言最终决策** | Go 还是 Rust？影响 Phase A 的技术选型 |

---

**文档结束**
