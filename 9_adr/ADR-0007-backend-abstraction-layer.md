---
doc_id: ADR-0007-BACKEND-ABSTRACTION
title: Backend Abstraction Layer for Memory Backend Agnosticism
owner: platform-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-12
depends_on: [ADR-0001-PRODUCT-BOUNDARY]
supersedes: []
last_verified_commit: ""
---

# ADR-0007-BACKEND-ABSTRACTION

**Status:** ACCEPTED
**Date:** 2026-04-12
**Deciders:** OmniMemora Product Team

---

## Title

Introduce Backend Abstraction Layer for Memory Backend Agnosticism

---

## Context

### 当前状态

- `5_connectors/adapter` (18011) 通过 `viking_request()` 硬编码调用 OpenViking (1933)
- 调用协议为 OpenViking 专用 REST 语义：
  - `/api/v1/fs/*` (文件系统操作)
  - `/api/v1/resources/*` (资源管理)
  - `/api/v1/content/read` (内容读取)
  - `/api/v1/search/find` (搜索)
- `8765` (OmniMemora Runtime) 提供独立的 MCP/REST 接口，与 1933 不兼容
- 产品宪法要求 Backend-agnostic，但工程实现违反

### 问题

1. **硬编码绑定**：18011 无法切换到 8765 或其他 backend
2. **违反宪法**：`viking://`、`/api/v1/` 等 OpenViking 概念扩散到 connector 层
3. **无法测试**：无法在不使用 1933 的情况下测试 connector 逻辑
4. **扩展性差**：新增 backend 需要修改 connector 核心代码

### 证据

```
$ grep -rn "viking_request\|/api/v1/" 5_connectors/adapter/main.py
849:            f"/api/v1/fs/ls?uri={encoded_uri}",
906:            "/api/v1/fs/mkdir",
1018:            f"/api/v1/fs/tree?uri={encoded_uri}",
1172:        f"/api/v1/content/read?uri={encoded_uri}",
1487:            "/api/v1/resources/temp_upload",
1525:            "/api/v1/resources",
1653:            "/api/v1/search/find",
1854:            f"/api/v1/fs?uri={encoded_uri}",
```

---

## Decision

### 核心决策

1. **引入 MemoryBackend 抽象接口**
   - 定义统一的 search/write/read/delete/health 接口
   - 使用 memory record / scope / content 语义
   - 不出现任何 backend 特有概念

2. **Connector 只依赖接口**
   - `5_connectors/adapter` 不得直接调用任何 backend 特有协议
   - 所有 backend 调用必须通过 `get_memory_backend()` 获取 backend 实例

3. **OpenViking 降级为 Adapter**
   - `OpenVikingBackend` 实现 MemoryBackend 接口
   - OpenViking 专用协议 (`viking://`, `/api/v1/`) 只存在于此 adapter 内

4. **新增 OmniMemoraRuntimeBackend**
   - 让 8765 可作为 backend 挂接
   - 实现与 MemoryBackend 接口的对齐

5. **引入 Backend Factory**
   - 通过配置选择 backend 类型
   - 支持 backend 热切换（测试场景）

---

## Consequences

### 正面

- **Backend 可替换**：可切换到 8765、SQLite 或未来其他 backend
- **测试友好**：可使用 MockBackend 进行单元测试
- **宪法一致**：真正实现 Backend-agnostic
- **架构清晰**：Connector / Interface / Adapter 三层分离

### 负面

- **增加一层复杂度**：需要维护 interface + factory
- **迁移成本**：需要重构现有 viking_request 调用
- **双重维护**：过渡期需要同时维护 OpenVikingBackend 和 OmniMemoraRuntimeBackend

### 中性

- OpenViking backend 保留，但地位从"默认"降级为"兼容选项"

---

## Implementation

### 目录结构

```
5_connectors/adapter/
├── backends/
│   ├── __init__.py           # factory 导出
│   ├── base.py               # MemoryBackend 接口定义
│   ├── factory.py            # create_backend()
│   ├── openviking_backend.py # OpenViking 实现
│   └── omnimemora_runtime_backend.py  # OmniMemora Runtime 实现
└── main.py                   # 改造：移除 viking_request，直接调用 backend 接口
```

### 新增配置

```python
# config.py
class MemoryBackendConfig:
    backend_type: str = "omnimemora_runtime"  # openviking / omnimemora_runtime
    base_url: str = "http://127.0.0.1:8765"
    api_key: Optional[str] = None
```

---

## Alternatives Considered

### 1. 直接切换到 8765

**拒绝原因**：
- 8765 与 1933 API 不兼容，不能直接 URL 切换
- 需要适配层
- 无法保留 OpenViking 兼容性

### 2. 不做抽象层，直接重写 connector

**拒绝原因**：
- 迁移成本过高
- 风险过大
- 增量改造更安全

### 3. 继续使用 1933，不引入 8765

**拒绝原因**：
- 违反宪法 Backend-agnostic 要求
- 8765 是新架构的核心组件，必须接入

---

## Status History

| Date | Status | Notes |
|------|--------|-------|
| 2026-04-12 | ACCEPTED | Initial decision |
| 2026-04-12 | IMPLEMENTED | Backend abstraction layer deployed |

## Current Status (2026-04-12)

**Implementation:** COMPLETED (PARTIAL)

### 已完成

- `MemoryBackend` 接口定义 (`backends/base.py`)
- `BackendFactory` 实现 (`backends/factory.py`)
- `OpenVikingBackend` 实现 (`backends/openviking_backend.py`)
- `OmniMemoraRuntimeBackend` 实现 (`backends/omnimemora_runtime_backend.py`)
- `main.py` 核心 endpoint 通过 backend 接口调用
- `omnimemora_runtime` backend 验证通过 (`write/search/query`)

### 当前限制

| 功能 | 状态 | 说明 |
|------|------|------|
| Write | ✅ | `omnimemora_runtime` 已验证 |
| Search | ✅ | `omnimemora_runtime` 已验证 |
| Query (Engine) | ✅ | `/memory/query` 全链路通过 |
| Read | ⚠️ | not supported by `omnimemora_runtime` |
| Delete | ⚠️ | not supported by `omnimemora_runtime` |

### 架构约束验证

- ✅ `main.py` 核心 endpoint 不直接调用 `viking_request()`
- ✅ `main.py` 只依赖 `MemoryBackend` 接口
- ✅ OpenViking 协议细节只在 `backends/openviking_backend.py` 内
- ✅ `omnimemora_runtime` is the default query-path operational backend

### 遗留项

- `/memory/snapshot` 端点仍调用 OpenViking helpers（已标记为 legacy）
- `read/delete` are outside the supported capability surface of `omnimemora_runtime`

---

## Non-Goal / Compatibility Exception

### `/memory/snapshot` 接口身份声明

- `/memory/snapshot` **不是** backend-neutral 通用接口
- **不是**未来标准接口
- **是** OpenViking compatibility backend 的遗留能力
- 新功能**不得**依赖此接口
- 若未来需要 backend-neutral snapshot/export 能力，须重新设计为新的通用接口，不得复用此 endpoint

### Backend Capability Boundary

`omnimemora_runtime` is scoped to query-path operations (write / search / query).
`read` and `delete` remain outside its supported capability surface.
Full CRUD compatibility is currently provided by `openviking` (compatibility full-CRUD backend).

This is a backend capability boundary, not an incomplete product feature.

---

## References

- [BACKEND_INTERFACE.md](../1_architecture/backend_abstraction/BACKEND_INTERFACE.md)
- [BACKEND_ADAPTER_PATTERN.md](../1_architecture/backend_abstraction/BACKEND_ADAPTER_PATTERN.md)
- [BACKEND_FACTORY.md](../1_architecture/backend_abstraction/BACKEND_FACTORY.md)
- [MIGRATION_PLAN_1933.md](../1_architecture/backend_abstraction/MIGRATION_PLAN_1933.md)
- [PRODUCT_CONSTITUTION.md](../0_blueprint/PRODUCT_CONSTITUTION.md) - Backend-agnostic 原则
