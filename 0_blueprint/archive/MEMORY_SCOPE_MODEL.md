# MEMORY_SCOPE_MODEL.md

**Status:** FINAL
**Source of Truth**: PRODUCT_CONSTITUTION + Global Product Blueprint
**Role**: OmniMemora 记忆边界治理的基础模型，所有 runtime / policy / routing / dedup / connector / billing 均引用此模型

---

# 一、设计原则

> 默认隔离，显式共享

---

# 二、Scope 类型

| Scope | 说明 | 默认行为 |
|-------|------|---------|
| user | 用户级记忆 | 跨 workspace 隔离，仅自身可写 |
| workspace | 项目/工作空间记忆 | 同 workspace 内共享读写 |
| agent | Agent 私有记忆 | 仅 agent 自身可读写 |
| custom | 自定义共享域 | 显式配置后共享 |

---

# 三、Sharing Mode

| Mode | 说明 |
|------|------|
| `isolated` | 完全隔离，不可共享 |
| `shared` | 同 scope 内可读写共享 |
| `shared_read_only` | 同 scope 内仅可读 |
| `custom` | 按 custom_policy 规则共享 |

---

# 四、数据结构

## Memory Record（含 Scope）

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

## Scope 上下文（请求时注入）

```json
{
  "user_id": "u_001",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "scope": "workspace"
}
```

---

# 五、访问规则

## Read

| 目标 Scope | 允许读取条件 |
|-----------|-------------|
| agent | agent_id 完全匹配 |
| workspace | workspace_id 完全匹配 |
| user | user_id 完全匹配 |
| custom | 显式共享配置包含请求方 |

## Write

| 目标 Scope | 允许写入条件 |
|-----------|-------------|
| agent | agent_id 完全匹配 |
| workspace | workspace_id 完全匹配 |
| user | user_id 完全匹配 |
| custom | 显式共享配置包含写入方 |

---

# 六、典型场景

## 场景 1：单用户多 Agent 隔离

```
用户 u_001
  ├── Agent claude_code (agent scope, isolated)
  │     └── 只能读写自己的 memory
  └── Agent codex (agent scope, isolated)
        └── 只能读写自己的 memory
```

**配置**：

```json
{
  "user_id": "u_001",
  "scope": "agent",
  "sharing_mode": "isolated"
}
```

---

## 场景 2：单用户项目共享

```
用户 u_001 / workspace proj_alpha
  ├── Agent claude_code (workspace scope)
  │     └── 可读写 proj_alpha 的 shared memory
  └── Agent codex (workspace scope)
        └── 可读写 proj_alpha 的 shared memory
```

**配置**：

```json
{
  "user_id": "u_001",
  "workspace_id": "proj_alpha",
  "scope": "workspace",
  "sharing_mode": "shared"
}
```

---

## 场景 3：多用户共享 workspace

```
Workspace proj_alpha (shared_read_only)
  ├── User u_001 (read_only)
  │     └── 可读 proj_alpha 内所有 memory
  └── User u_002 (read_only)
        └── 可读 proj_alpha 内所有 memory
```

**配置**：

```json
{
  "workspace_id": "proj_alpha",
  "scope": "workspace",
  "sharing_mode": "shared_read_only",
  "members": ["u_001", "u_002"]
}
```

---

## 场景 4：Docker OpenClaw 独立隔离

```
Container openclaw_1 (user scope, isolated)
  └── 独立 user scope，不与其他 container 共享

Container openclaw_2 (user scope, isolated)
  └── 独立 user scope，不与其他 container 共享
```

**配置**：

```json
{
  "user_id": "openclaw_1",
  "scope": "user",
  "sharing_mode": "isolated"
}
```

---

# 七、Policy 引用

Scope 影响以下 Policy 决策：

- **Dedup**：同 scope 内去重
- **Retention**：不同 scope 可配置不同保留策略
- **Compression**：按 scope 触发
- **Routing**：同 scope 路由到同一 Memory Plane

---

# 八、版本治理

本文档是 PRODUCT_CONSTITUTION 的实现细化，所有引用必须保持一致。

---

# 九、Phase 1 实现注解

**状态**: Phase 1 PASSED (2026-04-09)

## SQL Scope Enforcement

Phase 1 在 `store/sqlite_store.go` 中通过 `buildScopeFilter()` 函数实现 SQL 层面 scope 过滤：

```sql
-- Agent Scope
WHERE tenant_id = ? AND scope = 'agent' AND agent_id = ?

-- Workspace Scope
WHERE tenant_id = ? AND scope = 'workspace' AND workspace_id = ?
```

**关键特性**:

- `tenant_id` 作为第一过滤维度，无跨租户可见性
- `scope` 使用字面量字串（非动态变量）
- workspace 查询不混入 agent scope 数据
- 所有写/查/删路径均强制 tenant_id 过滤

## 验收通过的隔离测试

| 测试 | 条件 | 结果 |
|------|------|------|
| Agent A write → Agent A query | agent_id 相同 | ✅ 命中 |
| Agent A write → Agent B query | agent_id 不同 | ✅ 查不到 |
| Workspace shared write → other agent query | workspace_id 相同 | ✅ 命中 |
| Tenant A write → Tenant B query | tenant_id 不同 | ✅ 查不到 |

## 与 Blueprint 一致性

本文档定义的 scope/sharing_mode 规则与 Phase 1 实现完全一致。唯一扩展是 `tenant_id` 字段（ Blueprint RUNTIME_ARCHITECTURE.md 5.2 节已定义）。
