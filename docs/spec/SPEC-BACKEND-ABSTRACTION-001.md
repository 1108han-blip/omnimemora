---
doc_id: SPEC-BACKEND-ABSTRACTION-001
title: OmniMemora Backend Abstraction Layer Specification
owner: platform-team
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [ADR-0001-PRODUCT-BOUNDARY, ADR-0007-BACKEND-ABSTRACTION, ADR-0003-INTERFACE-ACCESS-PATHS]
supersedes: [
  "1_architecture/backend_abstraction/BACKEND_INTERFACE.md",
  "1_architecture/backend_abstraction/BACKEND_ADAPTER_PATTERN.md",
  "1_architecture/backend_abstraction/BACKEND_FACTORY.md",
  "1_architecture/backend_abstraction/MIGRATION_PLAN_1933.md"
]
last_verified_commit: ""
---

# SPEC-BACKEND-ABSTRACTION-001: Backend Abstraction Layer

> **状态：** active（Canonical Spec — 所有其他 Backend Abstraction 文档均派生自本文档）
> **接口版本：** 1.0
> **所属 ADR：** ADR-0007-BACKEND-ABSTRACTION

---

## 0. Summary

定义 OmniMemora 的 Memory Backend 抽象接口与适配器规范，使 Adapter 层（18011）能够在不修改代码的情况下切换不同的 Memory Backend 实现（1933 OpenViking / 8765 OmniMemora Runtime / 未来第三方）。

---

## 1. MemoryBackend 抽象接口

### 1.1 接口原则

| 原则 | 说明 |
|------|------|
| Backend-neutral | 接口不包含任何 backend 特有概念（viking/OpenViking/URI 路径） |
| Scope 语义 | 输入输出使用 memory record / scope / content 语义 |
| 职责单一 | 接口只定义"记忆能力"，不定义存储实现、权限判断、内容过滤 |

**禁止在接口中出现：**
- `viking`、`openviking`、`VIKING_URL`
- `/api/v1/` REST 路径（backend 私有协议）
- `viking://` URI 格式
- 文件系统路径（`/fs/`、`/resources/`）
- `temp_upload` / `commit` 两阶段概念

### 1.2 数据模型

```python
@dataclass
class MemorySearchRequest:
    query: str
    limit: int = 10
    scope: Optional[str] = None   # agent | workspace | user | tenant
    scope_ref: Optional[str] = None
    score_threshold: Optional[float] = None

@dataclass
class MemorySearchResult:
    memories: List[MemoryRecord]
    total: int

@dataclass
class MemoryWriteRequest:
    content: str
    scope: str                   # agent | workspace | user | tenant
    scope_ref: str
    metadata: Dict[str, Any]     # type, level, score, expire_at 等

@dataclass
class MemoryRecord:
    memory_id: str
    content: str
    scope: str
    scope_ref: str
    metadata: Dict[str, Any]
    created_at: Optional[int] = None
    score: Optional[float] = None

@dataclass
class BackendHealth:
    healthy: bool
    backend_type: str
    details: Optional[Dict[str, Any]] = None
```

### 1.3 必需方法

| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `search()` | `MemorySearchRequest` | `MemorySearchResult` | 搜索记忆 |
| `write()` | `MemoryWriteRequest` | `MemoryRecord` | 写入记忆 |
| `read()` | `memory_id: str` | `Optional[MemoryRecord]` | 按 ID 读取 |
| `delete()` | `memory_id: str` | `bool` | 删除记忆 |
| `health()` | — | `BackendHealth` | 健康检查 |

**任意 Backend Adapter 必须实现以上全部 5 个方法。**

### 1.4 Scope 模型

| Scope | 说明 | 示例 |
|-------|------|------|
| `agent` | Agent 级别隔离 | `agent=supervisor` |
| `workspace` | 工作空间级别 | `workspace=ws-main` |
| `user` | 用户级别 | `user=user-001` |
| `tenant` | 租户级别 | `tenant=trial-abc123` |

### 1.5 Metadata 标准字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | str | `general` \| `strategy` \| `failure_experience` \| `result` |
| `level` | str | `L0` - `L3`（重要性分级）|
| `score` | int | 重要性评分 |
| `expire_at` | int | 过期时间戳（`-1` = 永久）|
| `content_id` | str | 内容去重 ID |
| `agent` | str | 来源 agent |
| `created_by` | str | 创建者 |

---

## 2. Backend Adapter 模式

### 2.1 适配器继承结构

```
MemoryBackend (ABC, 抽象接口)
        ↑
        │
  ┌─────┴──────────┐
  │               │
OpenVikingBackend      OmniMemoraRuntimeBackend      FutureBackend
(1933)               (8765)                        (插件化)
```

**实现文件位置：**
- `5_connectors/adapter/backends/openviking_backend.py`
- `5_connectors/adapter/backends/runtime_backend.py`
- `5_connectors/adapter/backends/`（未来扩展）

### 2.2 OpenVikingBackend（1933）

**职责：** 将 MemoryBackend 抽象接口适配到 OpenViking REST 语义（`/api/v1/fs/*`、`/api/v1/resources/*`、`/api/v1/content/read`、`/api/v1/search/find`）。

**已知限制：** OpenViking 不支持 `delete()` 操作，该方法返回 `NotImplementedError`。

### 2.3 OmniMemoraRuntimeBackend（8765）

**职责：** 将 MemoryBackend 抽象接口适配到 OmniMemora Go Runtime MCP/REST 接口。

**状态：** 参照 `ADR-0003-INTERFACE-ACCESS-PATHS` 唯一产品路径架构。

---

## 3. BackendFactory 接线规则

### 3.1 配置模型

```python
class MemoryBackendConfig(BaseModel):
    backend_type: str = "omnimemora_runtime"  # openviking | omnimemora_runtime
    base_url: str = "http://127.0.0.1:8765"
    api_key: Optional[str] = None
    timeout_seconds: float = 30.0
    connect_timeout_seconds: float = 5.0
```

### 3.2 工厂创建规则

```
MemoryBackendFactory.create(config: MemoryBackendConfig) → MemoryBackend
```

- `backend_type == "openviking"` → `OpenVikingBackend(config)`
- `backend_type == "omnimemora_runtime"` → `OmniMemoraRuntimeBackend(config)`
- 未知类型 → `ValueError`

### 3.3 端口约定

| 端口 | 服务 | 说明 |
|------|------|------|
| 8765 | OmniMemora Runtime | Go Runtime HTTP server |
| 8766-8767, 8775 | Runtime Fallback | 端口探测备选 |
| 1933 | OpenViking | Legacy backend（已不推荐）|

---

## 4. 与宪法一致性

| 宪法原则 | 对应实现 |
|---------|---------|
| Backend-agnostic | 接口不依赖任何特定 backend |
| Control Plane / Memory Plane 分离 | Connector 只调接口，不知道 storage 实现 |
| 可替换性 | 任何满足接口的 backend 都可接入 |

---

## 5. 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0.0 | 2026-04-14 | 初始 canonical spec，整合 4 个分散文件 |
