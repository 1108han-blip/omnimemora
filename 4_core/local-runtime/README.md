# OmniMemora Local Runtime - Phase 3.5

**Status:** ✅ v0.3.6 RELEASED (2026-04-09)
**Source:** Blueprint定义的本地 Memory Plane 实现
**Git Tags:** v0.3.5, v0.3.6

---

## 版本历史

| Tag | 日期 | 说明 |
|-----|------|------|
| v0.3.5 | 2026-04-09 | Phase 3.5: CLI, bootstrap, dashboard, connect, packaging |
| v0.3.6 | 2026-04-09 | Audit fix: context_strategy/context_mode 写入 metering |

---

## 产品定位

> **OmniMemora = Memory Augmentation Layer**

- 不替代 Agent memory
- 不接管推理
- 仅优化 context + token

**核心原则（来自 PRODUCT_CONSTITUTION.md）：**

1. **非接管原则**：不接管 Agent 的 memory ownership
2. **弱侵入原则**：Agent 可不接入 OmniMemora 正常运行
3. **单能力原则**：只解决提升 context 质量和降低 token 使用
4. **接口边界原则**：只通过 `/memory/search` 和 `/memory/write` 提供能力

---

## 目录结构

```
4_core/local-runtime/
├── go.mod                      # Go module definition
├── main.go                    # Entry point (runtime mode)
├── cmd/omnimemora/main.go     # CLI entry point
├── api/
│   ├── server.go              # HTTP server setup
│   ├── routes.go              # Route handlers + dashboard
│   └── middleware.go          # Request middleware (scope, logging, request ID)
├── app/
│   ├── types.go               # Core data types (ScopeRef, MemoryRecord, etc.)
│   ├── service.go             # Business logic service
│   ├── errors.go              # Error types
│   └── context/               # Phase 2c: Context strategy layer
│       ├── strategy.go        # Strategy interface + registry
│       ├── strategy_topk.go   # TopK Excerpt strategy
│       ├── strategy_recency.go # Recency Boost strategy
│       ├── strategy_diversity.go # Diversity strategy
│       ├── strategy_auto.go   # Auto strategy resolution
│       ├── assembler.go       # Context assembler
│       └── effectiveness.go  # Strategy effectiveness metrics
├── config/
│   ├── config.go               # Configuration structures
│   └── loader.go              # Configuration loading
├── scope/
│   ├── model.go               # Scope enforcement model
│   └── resolver.go           # Scope resolution (Header > Body > Config)
├── store/
│   ├── store.go              # Store interface abstraction
│   └── sqlite_store.go       # SQLite + FTS5 implementation
├── metering/
│   ├── event.go              # Metering event structures
│   └── collector.go          # Metering collection and aggregation
├── internal/
│   ├── cli/commands.go       # CLI commands (start/status/stop/dashboard)
│   ├── bootstrap/first_run.go # First-run initialization
│   ├── demo/seed.go          # Demo data seeding
│   ├── runtime/port_resolver.go # Port management
│   └── connect/             # Agent connect commands
├── scripts/release/          # Release build scripts
└── tests/                   # Test suite
    ├── e2e_phase35_test.go   # Phase 3.5 E2E tests
    ├── search_phase3_*.go     # Phase 3 deterministic + invariant tests
    └── legacy/phase2b/       # Deprecated Phase 2b tests

---

## 核心接口说明

### 端口约定（已修订 2026-04-13）

> 详细定义见 `9_adr/ADR-0003-interface-access-paths.md`（已同步修订）。

| 端口 | 角色 | 说明 |
|------|------|------|
| **:18011**（Python Adapter） | 统一产品入口 | Context Compiler + Token Savings + MCP/REST 协议接入 |
| **:8765**（Go Runtime） | Local Memory Plane | 仅存储/检索，**非产品入口** |

Go Runtime 的 MCP / REST / CLI 接口仅供 Python Adapter 内部调用，不对外部 Agent 直接暴露产品能力。

| 接口 | 协议 | 端口 | 状态 | 用途 |
|------|------|------|------|------|
| MCP（内部） | SSE + JSON-RPC | 8765 | ✅ | 供 Python Adapter 内部调用（存储层） |
| REST | HTTP JSON | 8765 | ✅ | 供 Python Adapter 内部调用（存储层） |
| CLI | HTTP REST | 8765 | ✅ | 供 Python Adapter 内部调用（存储层） |

外部 Agent 统一从 **:18011** 接入，详见 `9_adr/ADR-0003-interface-access-paths.md`。



### Store 接口 (store/store.go)

业务层只能通过 Store 接口访问存储，不允许直接 SQL：

```go
type Store interface {
    Write(ctx context.Context, record *MemoryRecord) error
    Query(ctx context.Context, req *QueryRequest) (*QueryResult, error)
    QueryByHash(ctx context.Context, contentHash string, scopeRef *ScopeRef) (string, error)
    Delete(ctx context.Context, memoryID string, scopeRef *ScopeRef) error
    Count(ctx context.Context) (int64, error)
    Close() error
}
```

### ScopeRef 结构 (app/types.go)

治理主体，包含完整的 identity 字段：

```go
type ScopeRef struct {
    TenantID     string      // 租户 ID
    UserID       string      // 用户 ID
    WorkspaceID  string      // 工作空间 ID
    AgentID     string      // Agent ID
    Scope       ScopeType   // agent | workspace | user | custom
    SharingMode SharingMode // isolated | shared | shared_read_only | custom
}
```

### Scope 解析优先级

Scope 解析遵循 **Header > Body > Config** 优先级：

| 来源 | 示例 Header | Body 字段 |
|------|-------------|-----------|
| Tenant | `X-OmniMemora-Tenant` | `tenant_id` |
| User | `X-OmniMemora-User` | `user_id` |
| Workspace | `X-OmniMemora-Workspace` | `workspace_id` |
| Agent | `X-OmniMemora-Agent` | `agent_id` |
| Scope | `X-OmniMemora-Scope` | `scope` |
| Sharing Mode | `X-OmniMemora-Sharing-Mode` | `sharing_mode` |

**关键行为：**
- workspace scope 默认 sharing_mode 为 `shared`（而非 `isolated`）
- agent/user scope 默认 sharing_mode 为 `isolated`
- tenant_id 贯穿 write/query/metering，确保租户隔离

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/metrics` | 本地 metering 聚合 |
| POST | `/memory/write` | 写入记忆 |
| POST | `/memory/query` | 查询记忆 |
| POST | `/connector/register` | 注册 connector |
| GET | `/connector/list` | 列出 connectors |

---

## 启动命令

### 前置条件
- Go 1.21+
- SQLite3

### 下载依赖
```bash
cd 4_core/local-runtime
go mod download
```

### 构建
```bash
go build -o omnimemora-runtime .
```

### 运行
```bash
# 默认配置运行（SQLite 存储在 ~/.omnimemora/runtime/）
./omnimemora-runtime

# 或指定配置
OMNIMEMORA_CONFIG=/path/to/config.json ./omnimemora-runtime
```

### Docker 运行
```bash
docker build -t omnimemora-runtime .
docker run -p 8765:8765 omnimemora-runtime
```

---

## 测试命令

### 运行所有测试
```bash
go test ./tests/... -v
```

### 运行单个测试文件
```bash
go test ./tests/health_test.go -v
go test ./tests/write_query_test.go -v
go test ./tests/scope_test.go -v
```

### 带覆盖率
```bash
go test ./tests/... -v -cover
```

---

## 已修复项 (2026-04-09)

| 问题 | 修复内容 |
|------|----------|
| scope 注入链路 | Middleware 真实解析 body JSON，Header > Body > Config 优先级生效 |
| X-OmniMemora-Scope | 支持通过 header 或 body 显式指定 scope |
| workspace shared 路径 | workspace scope 默认 sharing_mode=shared，打通 write/query 路径 |
| tenant_id 贯穿 | query/memory/metering 全部加 tenant_id 过滤 |
| /metrics 语义 | 拆分 product metrics (total_writes=COUNT write events, memory_count=COUNT memories) |
| connector 持久化 | connector registry 支持 SQLite 持久化 |

## 验收证据 (2026-04-09)

### SQL Scope Enforcement

```sql
-- Agent Scope
WHERE tenant_id = ? AND scope = 'agent' AND agent_id = ?

-- Workspace Scope
WHERE tenant_id = ? AND scope = 'workspace' AND workspace_id = ?
```

### 隔离验证结果

| 测试 | 操作 | 结果 |
|------|------|------|
| Agent A write → Agent A query | agent_id 相同 | ✅ 命中 |
| Agent A write → Agent B query | agent_id 不同 | ✅ 查不到 |
| Workspace shared write → other agent query | workspace_id 相同 | ✅ 命中 |
| Tenant A write → Tenant B query | tenant_id 不同 | ✅ 查不到 |

### /metrics 输出示例

```json
{
  "totals": {
    "memory_count": 3,
    "total_writes": 1,
    "total_queries": 1,
    "total_input_tokens": 6,
    "total_saved_tokens": 0
  },
  "runtime": {
    "version": "1.0.0",
    "mode": "local"
  }
}
```

## 未实现项

以下功能在 Phase 1 中未实现（将在后续阶段实现）：

| 功能 | 状态 | 说明 |
|------|------|------|
| custom scope | 501 | custom scope 暂返回 `501 Not Implemented` |
| `/memory/search` | TODO | FTS5 关键词搜索端点 |
| `/memory/delete` | TODO | 删除记忆端点 |
| `/runtime/stop` | TODO | 停止 runtime |
| `/runtime/restart` | TODO | 重启 runtime |
| 向量检索 | TODO | sqlite-vss 向量相似度搜索 |
| 云端同步 | TODO | 可选的 cloud.enabled 云端同步 |
| MCP connector | TODO | MCP Server 协议实现 |
| Token 精确计算 | TODO | MVP 使用粗估 (len/4) |
| Backup/Restore | TODO | 数据备份恢复机制 |

---

## 设计约束（遵守 Blueprint 边界）

### 必须遵守

1. **Store 抽象**：业务层只能通过 `Store` 接口操作存储
2. **Scope 隔离**：不同 agent 在 agent scope 下互不可见
3. **Metering 绑定 ScopeRef**：所有 metering event 携带完整 ScopeRef
4. **Scope 解析优先级**：Header > Body > Config
5. **默认 scope=agent, sharing_mode=isolated**
6. **本地模式无需 API key**

### 禁止事项

1. **不得**把 1933 backend 作为主依赖
2. **不得**跳过 Store 抽象直接在 service 层写 SQL
3. **不得**把 scope enforcement 放进 URI 路径判断
4. **不得**新增 Blueprint 中未定义的 identity 结构
5. **不得**实现 Cloud Control Plane / Billing / Console
6. **不得**为了"先跑通"绕过治理边界

---

## 验证命令

### 检查 Store 抽象是否被绕过
```bash
# service 层不应有 SQL
grep -rn "SELECT\|INSERT\|UPDATE\|DELETE" app/*.go | grep -v "_test.go"
# 应返回 0 行或仅在注释中

# store 层可以有 SQL
grep -n "SELECT\|INSERT" store/sqlite_store.go | wc -l
# 应有实际 SQL 查询
```

### 检查 Scope enforcement
```bash
# scope 判断不应出现在 URI 解析中
grep -rn "url.Path" app/*.go | grep scope
# 应返回空
```

### 检查无硬编码 1933
```bash
grep -rn "1933" . --include="*.go" | grep -v "_test.go"
# 应返回空
```

---

## 配置说明

默认配置 (`~/.omnimemora/runtime/config.json`)：

```json
{
  "version": "1.0",
  "mode": "local",
  "local": {
    "endpoint": "127.0.0.1",
    "data_path": "~/.omnimemora/runtime",
    "db_type": "sqlite",
    "log_level": "info"
  },
  "cloud": {
    "enabled": false
  },
  "scope": {
    "default": "agent",
    "default_workspace": "default",
    "default_sharing_mode": "isolated"
  }
}
```

---

## 溯源索引

| 要素 | Blueprint 溯源 |
|------|----------------|
| ScopeRef 字段 | RUNTIME_ARCHITECTURE.md 5.2 |
| MemoryRecord | RUNTIME_ARCHITECTURE.md 5.3 |
| MeteringEvent | RUNTIME_ARCHITECTURE.md 5.4, DECISION_LEDGER.md Decision 08 |
| Store 接口 | RUNTIME_ARCHITECTURE.md 第八节 |
| API 端点 | RUNTIME_ARCHITECTURE.md 第七节 |
| Scope 类型 | MEMORY_SCOPE_MODEL.md 第二节 |
| Sharing Mode | MEMORY_SCOPE_MODEL.md 第三节 |
| 默认规则 | RUNTIME_ARCHITECTURE.md 6.3 |

---

## 版本

- **Phase 1**: MVP 可运行版本，支持基础 write/query/health/metrics
- **未来**: 向量检索、MCP、云端同步、backup/restore
