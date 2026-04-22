---
doc_id: LEGACY-BACKEND-ADAPTER-PATTERN-001
title: Backend Adapter Pattern (Legacy)
owner: platform-team
reviewers: [arch-lead]
status: deprecated
version: 1.0.0
effective_date: 2026-04-10
depends_on: [ADR-0007-BACKEND-ABSTRACTION]
supersedes: [SPEC-BACKEND-ABSTRACTION-001]
last_verified_commit: ""
---

# BACKEND_ADAPTER_PATTERN.md

**⚠️ 已废弃（Deprecated）**

> **替代文档：** `docs/spec/SPEC-BACKEND-ABSTRACTION-001.md`

---

## 1. Adapter 模式总览

```
MemoryBackend Interface (抽象)
        ↑
        │
   ┌────┴────┐
   │         │
OpenVikingBackend    OmniMemoraRuntimeBackend    FutureBackend
(1933)              (8765)                    (...)
```

---

## 2. OpenVikingBackend Adapter

### 2.1 文件位置

```
5_connectors/adapter/backends/openviking_backend.py
```

### 2.2 职责边界

| 职责 | 说明 |
|------|------|
| **负责** | 所有对 1933 的 HTTP 调用 |
| **负责** | OpenViking 专用协议的请求/响应映射 |
| **负责** | `viking://` URI 与 MemoryRecord 的双向转换 |
| **禁止** | 向外暴露 OpenViking 内部概念 |

### 2.3 接口映射

| MemoryBackend 接口 | OpenViking 实现 |
|-------------------|----------------|
| `search()` | → `POST /api/v1/search/find` |
| `write()` | → `POST /api/v1/resources/temp_upload` + `POST /api/v1/resources` |
| `read()` | → `GET /api/v1/content/read?uri=` |
| `delete()` | → `DELETE /api/v1/fs?uri=` |
| `health()` | → `GET /health` |

### 2.4 请求转换示例

```python
# MemorySearchRequest → OpenViking 格式
def _to_openviking_search(self, request: MemorySearchRequest) -> dict:
    return {
        "query": request.query,
        "limit": request.limit,
        "target_uri": self._scope_to_uri(request.scope, request.scope_ref),
        "score_threshold": request.score_threshold,
    }

# OpenViking 响应 → MemorySearchResult
def _from_openviking_search(self, response: dict) -> MemorySearchResult:
    memories = []
    for item in response.get("memories", []):
        memories.append(MemoryRecord(
            memory_id=item["uri"],
            content=self._extract_content(item),
            scope=request.scope,
            scope_ref=request.scope_ref,
            metadata=item.get("metadata", {}),
            created_at=item.get("created_at"),
            score=item.get("score"),
        ))
    return MemorySearchResult(memories=memories, total=len(memories))
```

### 2.5 Scope 到 URI 的转换

```python
def _scope_to_uri(self, scope: str, scope_ref: str) -> str:
    """将 scope 模型转换为 OpenViking URI"""
    if scope == "agent":
        return f"viking://resources/memory-adapter/{scope_ref}/short_term"
    elif scope == "workspace":
        return f"viking://resources/memory-adapter/{scope_ref}"
    elif scope == "tenant":
        return f"viking://resources/memory-adapter/{scope_ref}"
    return "viking://resources/memory-adapter"
```

---

## 3. OmniMemoraRuntimeBackend Adapter

### 3.1 文件位置

```
5_connectors/adapter/backends/omnimemora_runtime_backend.py
```

### 3.2 职责边界

| 职责 | 说明 |
|------|------|
| **负责** | 所有对 8765 的 HTTP/MCP 调用 |
| **负责** | OmniMemora Runtime 协议的请求/响应映射 |
| **负责** | Runtime Scope 与 MemoryRecord 的双向转换 |
| **禁止** | 向外暴露 Runtime 内部实现细节 |

### 3.3 接口映射

| MemoryBackend 接口 | OmniMemora Runtime 实现 |
|-------------------|----------------------|
| `search()` | → `POST /memory/search` |
| `write()` | → `POST /memory/write` |
| `read()` | → `GET /memory/read/{memory_id}` 或 `POST /memory/read` |
| `delete()` | → `DELETE /memory/delete/{memory_id}` |
| `health()` | → `GET /health` |

### 3.4 请求转换示例

```python
# MemorySearchRequest → OmniMemora Runtime 格式
def _to_runtime_search(self, request: MemorySearchRequest) -> dict:
    return {
        "query": request.query,
        "limit": request.limit,
        "scope": request.scope,
        "scope_ref": request.scope_ref,
        "score_threshold": request.score_threshold,
    }

# Runtime 响应 → MemorySearchResult
def _from_runtime_search(self, response: dict) -> MemorySearchResult:
    memories = []
    for item in response.get("memories", []):
        memories.append(MemoryRecord(
            memory_id=item["id"],
            content=item["content"],
            scope=item.get("scope", request.scope),
            scope_ref=item.get("scope_ref", request.scope_ref),
            metadata=item.get("metadata", {}),
            created_at=item.get("created_at"),
            score=item.get("score"),
        ))
    return MemorySearchResult(memories=memories, total=len(memories))
```

### 3.5 Scope 模型直接映射

```python
def _to_runtime_scope(self, scope: str, scope_ref: str) -> dict:
    """OmniMemora Runtime 直接使用 scope 对象"""
    return {
        "scope": scope,
        "scope_ref": scope_ref,
    }
```

---

## 3.6 Backend Capability Matrix

> `query path` 指 `/memory/query -> backend search/write -> engine.optimize_context()` 所需的核心主链路能力，不等同于 backend full CRUD completeness。

| Backend | write | search | query path |                       read |                     delete |
| ------- | ----: | -----: | ---------: | --------------------------: | --------------------------: |
| `omnimemora_runtime` | ✅ | ✅ | ✅ | ⚠️ not supported | ⚠️ not supported |
| `openviking` | ✅ | ✅ | ✅ | ✅ | ✅ |

### Current Limitations

- `omnimemora_runtime` is scoped to query-path operations (write / search / query)
- `read` and `delete` are outside its supported capability surface
- `openviking` serves as the compatibility full-CRUD backend

---

## 4. Adapter 通用模式

### 4.1 初始化模式

```python
class BaseMemoryBackend(ABC):
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client = httpx.AsyncClient(timeout=self._default_timeout())
    
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
    
    def _default_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(30.0, connect=5.0)
```

### 4.2 错误处理模式

```python
async def _handle_error(self, response: httpx.Response, operation: str) -> None:
    """统一错误处理"""
    error_mapping = {
        400: BackendError.BAD_REQUEST,
        401: BackendError.UNAUTHORIZED,
        403: BackendError.FORBIDDEN,
        404: BackendError.NOT_FOUND,
        500: BackendError.INTERNAL_ERROR,
        502: BackendError.BAD_GATEWAY,
        503: BackendError.SERVICE_UNAVAILABLE,
    }
    error_type = error_mapping.get(response.status_code, BackendError.UNKNOWN)
    raise BackendError(error_type, f"{operation} failed: {response.status_code}")
```

### 4.3 健康检查模式

```python
async def health(self) -> BackendHealth:
    try:
        response = await self._client.get(f"{self.base_url}/health")
        if response.status_code == 200:
            return BackendHealth(healthy=True, backend_type=self.backend_type)
        return BackendHealth(healthy=False, backend_type=self.backend_type)
    except Exception as e:
        return BackendHealth(
            healthy=False,
            backend_type=self.backend_type,
            details={"error": str(e)}
        )
```

---

## 5. 适配器禁止事项

| 禁止 | 原因 |
|------|------|
| 在 adapter 内做业务逻辑判断 | adapter 只做协议转换 |
| 在 adapter 内修改 request/response 结构 | 只做映射，不做转换 |
| 在 adapter 内抛出非 BackendError 异常 | 统一错误类型 |
| 在 connector 层做 backend 类型判断 | 必须用 factory |

---

## 6. 测试模式

### 6.1 Mock Backend 实现

```python
class MockMemoryBackend(MemoryBackend):
    """用于测试的 Mock 实现"""
    
    def __init__(self):
        self.memories = {}
    
    async def search(self, request: MemorySearchRequest) -> MemorySearchResult:
        # 返回预设数据
        return MemorySearchResult(memories=[], total=0)
    
    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        memory_id = f"mock-{len(self.memories)}"
        record = MemoryRecord(memory_id=memory_id, ...)
        self.memories[memory_id] = record
        return record
```

### 6.2 集成测试模式

```python
async def test_backend_integration(backend: MemoryBackend):
    """通用 backend 集成测试"""
    # 1. health check
    health = await backend.health()
    assert health.healthy
    
    # 2. write
    record = await backend.write(MemoryWriteRequest(...))
    assert record.memory_id
    
    # 3. search
    result = await backend.search(MemorySearchRequest(...))
    assert len(result.memories) > 0
    
    # 4. delete
    success = await backend.delete(record.memory_id)
    assert success
```
