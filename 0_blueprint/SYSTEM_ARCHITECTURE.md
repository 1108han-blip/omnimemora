# SYSTEM_ARCHITECTURE.md

**Status:** FINAL
**Role:** 系统架构描述 - 只描述结构，不讲策略

---

# 一、Runtime 架构

## 1.1 一句话定义

Local Runtime 是 OmniMemora 的默认 Memory Plane 实现，负责在用户本地执行记忆写入、检索、查询、scope 治理与计量事件产生。

## 1.2 架构位置

```
Connector → Local Runtime →（可选）Cloud Control Plane
```

## 1.3 目录结构

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

## 1.4 逐目录职责说明

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

# 二、Scope 模型

## 2.1 Scope 类型

| Scope | 说明 | 默认行为 |
|-------|------|---------|
| user | 用户级记忆 | 跨 workspace 隔离，仅自身可写 |
| workspace | 项目/工作空间记忆 | 同 workspace 内共享读写 |
| agent | Agent 私有记忆 | 仅 agent 自身可读写 |
| custom | 自定义共享域 | 显式配置后共享 |

## 2.2 Sharing Mode

| Mode | 说明 |
|------|------|
| `isolated` | 完全隔离，不可共享 |
| `shared` | 同 scope 内可读写共享 |
| `shared_read_only` | 同 scope 内仅可读 |
| `custom` | 按 custom_policy 规则共享 |

## 2.3 数据结构

### Memory Record（含 Scope）

```json
{
  "id": "mem_xxxxx",
  "user_id": "u_001",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "scope": "workspace",
  "sharing_mode": "shared",
  "content": "...",
  "created_at": "2026-04-08T00:00:00Z",
  "updated_at": "2026-04-08T00:00:00Z"
}
```

### Scope 上下文（请求时注入）

```json
{
  "user_id": "u_001",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "scope": "workspace"
}
```

## 2.4 访问规则

### Read

| 目标 Scope | 允许读取条件 |
|-----------|-------------|
| agent | agent_id 完全匹配 |
| workspace | workspace_id 完全匹配 |
| user | user_id 完全匹配 |
| custom | 显式共享配置包含请求方 |

### Write

| 目标 Scope | 允许写入条件 |
|-----------|-------------|
| agent | agent_id 完全匹配 |
| workspace | workspace_id 完全匹配 |
| user | user_id 完全匹配 |
| custom | 显式共享配置包含写入方 |

---

# 三、Bootstrap 关键结构

## 3.1 设计原则

1. **Local First** — 默认在本地运行，不要求网络
2. **Cloud Optional** — 云端增强，不影响本地独立运行
3. **Default Isolated** — scope 默认隔离
4. **Explicit Sharing** — 共享必须显式配置
5. **Single Runtime** — 每个用户/workspace 一个实例
6. **All Components Replaceable** — store / engine / model 均可替换
7. **Full Traceability** — 每个请求必须具备完整 trace context

## 3.2 Runtime 职责边界

### 应该负责

- memory write / query / search / delete
- local store 管理
- scope governance（执行）
- local policy 执行（最小必要：dedup / compile / scope filtering）
- **metering event 产生**（核心职责）
- local config / lifecycle / health
- connector 注册与管理
- local metrics API
- 对 LLM 只输出最小必要 context 结果（不输出策略/候选/评分/控制面元信息）

### 不应该负责

- 主云端托管
- billing 结算
- 多租户 SaaS console
- connector UI
- 云端 policy 存储
- 跨 tenant 的数据聚合

---

# 四、系统层级结构

```
Agent (ChatGPT / Codex / OpenClaw)
↓ (optional call)
OmniMemora (Control Plane)
↓
Optimized Context
↓
LLM
```

## 4.1 Context 输出边界

进入 LLM 的 Context 必须是最终结果，不得包含：

- 策略参数与策略执行细节
- 候选集与筛除过程
- 评分过程与中间分数
- control plane 元信息
