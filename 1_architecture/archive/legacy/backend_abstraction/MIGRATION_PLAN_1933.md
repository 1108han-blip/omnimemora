---
doc_id: LEGACY-MIGRATION-1933-001
title: Migration Plan 1933 to Backend Abstraction (Legacy)
owner: platform-team
reviewers: [arch-lead]
status: deprecated
version: 1.0.0
effective_date: 2026-04-12
depends_on: [ADR-0007-BACKEND-ABSTRACTION]
supersedes: [SPEC-BACKEND-ABSTRACTION-001]
last_verified_commit: ""
---

# MIGRATION_PLAN_1933.md

**⚠️ 已废弃（Deprecated）**

> **替代文档：** `docs/spec/SPEC-BACKEND-ABSTRACTION-001.md`

---

## 1. 当前状态

### 1.1 问题定位

```
当前：Connector (18011) → viking_request() → 1933 (OpenViking)
问题：硬编码绑定，无抽象层，不可切换
```

### 1.2 调用清单

以下是在 `5_connectors/adapter/main.py` 中需要迁移的调用点：

| 函数 | 调用 | 目标接口 |
|------|------|---------|
| `list_directory_entries()` | `viking_request("GET", "/api/v1/fs/ls")` | namespace 检查 |
| `mkdir_uri()` | `viking_request("POST", "/api/v1/fs/mkdir")` | 创建目录 |
| `resolve_leaf_uri()` | `viking_request("GET", "/api/v1/fs/tree")` | URI 解析 |
| `read_clean_resource_content()` | `viking_request("GET", "/api/v1/content/read")` | 内容读取 |
| `write_memory()` | `viking_request("POST", "/api/v1/resources/temp_upload")` | 临时上传 |
| `write_memory()` | `viking_request("POST", "/api/v1/resources")` | 资源提交 |
| `search_memory()` | `viking_request("POST", "/api/v1/search/find")` | 搜索 |
| `delete_memory()` | `viking_request("DELETE", "/api/v1/fs")` | 删除 |

---

## 2. 执行步骤

### Phase A: 建立骨架（Step 1-3）

---

#### Step 1: 创建目录结构

```bash
mkdir -p 5_connectors/adapter/backends
touch 5_connectors/adapter/backends/__init__.py
```

创建文件：
- `5_connectors/adapter/backends/__init__.py`
- `5_connectors/adapter/backends/base.py`
- `5_connectors/adapter/backends/factory.py`
- `5_connectors/adapter/backends/openviking_backend.py`
- `5_connectors/adapter/backends/omnimemora_runtime_backend.py`

---

#### Step 2: 实现 base.py（MemoryBackend 接口）

从 `BACKEND_INTERFACE.md` 复制接口定义到 `base.py`。

关键类：
- `MemorySearchRequest`
- `MemorySearchResult`
- `MemoryWriteRequest`
- `MemoryRecord`
- `BackendHealth`
- `MemoryBackend` (ABC)

---

#### Step 3: 实现 factory.py

从 `BACKEND_FACTORY.md` 复制 factory 逻辑。

关键函数：
- `register_backend()`
- `create_backend()`
- `get_memory_backend()`

---

### Phase B: OpenVikingBackend 实现（Step 4-6）

---

#### Step 4: 实现 openviking_backend.py

将 `main.py` 中的 `viking_request()` 调用迁移到此文件。

```python
# openviking_backend.py

class OpenVikingBackend(MemoryBackend):
    """OpenViking Backend Adapter (1933)"""
    
    backend_type = "openviking"
    
    async def search(self, request: MemorySearchRequest) -> MemorySearchResult:
        # 实现 /api/v1/search/find 调用
        ...
    
    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        # 实现 temp_upload + commit 两阶段
        ...
    
    async def read(self, memory_id: str) -> Optional[MemoryRecord]:
        # 实现 /api/v1/content/read
        ...
    
    async def delete(self, memory_id: str) -> bool:
        # 实现 /api/v1/fs DELETE
        ...
    
    async def health(self) -> BackendHealth:
        # 实现 /health
        ...
```

**注意**：`viking://` URI 只在此文件内使用。

---

#### Step 5: 修改 main.py - 移除直接 viking_request 调用

找到所有 `viking_request()` 调用，替换为 backend 接口调用：

**Before:**
```python
async def search_memory(request: RetrieveRequest, http_request: Request):
    ...
    response = await viking_request(
        "POST",
        "/api/v1/search/find",
        ...
    )
```

**After:**
```python
async def search_memory(request: RetrieveRequest, http_request: Request):
    backend = get_memory_backend()
    ...
    result = await backend.search(MemorySearchRequest(...))
```

---

#### Step 6: 修改 main.py - 添加 backend 初始化

在 app 启动时初始化 backend：

```python
# main.py 顶部
from backends.factory import create_backend_from_config, get_memory_backend

# app 启动时
@app.on_event("startup")
async def startup():
    global _backend
    _backend = create_backend_from_config(config.memory_backend)
```

---

### Phase C: 配置改造（Step 7-8）

---

#### Step 7: 修改 config.py

添加 backend 配置：

```python
class MemoryBackendConfig(BaseModel):
    backend_type: str = "omnimemora_runtime"
    base_url: str = "http://127.0.0.1:8765"
    api_key: Optional[str] = None
    timeout_seconds: float = 30.0

class Config(BaseModel):
    # ... 其他配置 ...
    
    memory_backend: MemoryBackendConfig = MemoryBackendConfig()
    
    # Legacy deprecated
    viking_url: Optional[str] = None
    viking_api_key: Optional[str] = None
```

---

#### Step 8: 修改 /health 端点

**Before:**
```python
return {
    "viking_url": config.viking_url,
    "viking_connected": viking_healthy,
}
```

**After:**
```python
backend = get_memory_backend()
health = await backend.health()
return {
    "memory_backend": {
        "type": health.backend_type,
        "healthy": health.healthy,
    }
}
```

---

### Phase D: OmniMemoraRuntimeBackend 实现（Step 9-10）

---

#### Step 9: 实现 omnimemora_runtime_backend.py

```python
# omnimemora_runtime_backend.py

class OmniMemoraRuntimeBackend(MemoryBackend):
    """OmniMemora Runtime Backend Adapter (8765)"""
    
    backend_type = "omnimemora_runtime"
    
    async def search(self, request: MemorySearchRequest) -> MemorySearchResult:
        # 调用 POST /memory/search
        ...
    
    async def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        # 调用 POST /memory/write
        ...
    
    async def read(self, memory_id: str) -> Optional[MemoryRecord]:
        # 调用 GET /memory/read/{memory_id}
        ...
    
    async def delete(self, memory_id: str) -> bool:
        # 调用 DELETE /memory/delete/{memory_id}
        ...
    
    async def health(self) -> BackendHealth:
        # 调用 GET /health
        ...
```

---

#### Step 10: 切换默认 backend（可选）

将默认 backend 从 `openviking` 改为 `omnimemora_runtime`：

```python
class MemoryBackendConfig(BaseModel):
    backend_type: str = "omnimemora_runtime"  # 改这里
    base_url: str = "http://127.0.0.1:8765"
    ...
```

---

## 3. 回归测试

### 3.1 OpenViking Backend 测试

```bash
# 设置环境
export MEMORY_BACKEND_TYPE=openviking
export VIKING_URL=http://host.docker.internal:1933

# 测试
curl -X POST http://localhost:18011/memory/write \
  -H "Content-Type: application/json" \
  -d '{"content": "test", "scope": "agent", "scope_ref": "test"}'

curl -X POST http://localhost:18011/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'
```

### 3.2 OmniMemora Runtime Backend 测试

```bash
# 设置环境
export MEMORY_BACKEND_TYPE=omnimemora_runtime
export MEMORY_BACKEND_URL=http://127.0.0.1:8765

# 测试（通过 Adapter:18011 → Runtime:8765）
curl -X POST http://localhost:18011/memory/write \
  -H "Content-Type: application/json" \
  -d '{"content": "test", "scope": "agent", "scope_ref": "test"}'

curl -X POST http://localhost:18011/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'
```

---

## 4. 污染清理检查

### 4.1 Grep 检查

在 `5_connectors/adapter/` 目录（不含 `backends/openviking_backend.py`）执行：

```bash
# 应返回 0 行
grep -rn "viking_request\|/api/v1/fs\|/api/v1/resources\|viking://" \
  --include="*.py" \
  --exclude="*openviking_backend.py" \
  5_connectors/adapter/
```

### 4.2 接口检查

确认 `backends/openviking_backend.py` 是唯一出现 OpenViking 语义的文件。

---

## 5. 风险与回滚

### 5.1 回滚计划

如果迁移后旧链路失效：

1. 将 `memory_backend.backend_type` 改回 `openviking`
2. 检查 `viking_url` 配置是否正确
3. 确认 1933 服务是否正常运行

### 5.2 增量提交

每次 Step 完成后提交：

```bash
git add 5_connectors/adapter/backends/
git commit -m "feat(adapter): add backend abstraction layer skeleton"
```

---

## 6. 验收标准

| 标准 | 状态 | 验证方式 |
|------|------|---------|
| `main.py` 无 `viking_request` | ✅ | grep 检查返回 0 行（核心 endpoint） |
| 所有 backend 调用走接口 | ✅ | 代码审查 |
| `/health` 输出不含 `viking_url` | ✅ | `memory_backend.type` 替代 |
| OpenViking backend 可用 | ✅ | backend 接口实现完成 |
| OmniMemora Runtime backend 可用 | ✅ | write/search/query 已验证 |

## 7. 当前限制

| 功能 | 状态 | 说明 |
|------|------|------|
| Write | ✅ | `omnimemora_runtime` 已验证 |
| Search | ✅ | `omnimemora_runtime` 已验证 |
| Query (Engine) | ✅ | `/memory/query` 全链路通过 |
| Read | ⚠️ | not supported by `omnimemora_runtime` |
| Delete | ⚠️ | not supported by `omnimemora_runtime` |
| Snapshot | ⚠️ | legacy — OpenViking compatibility only |

**说明：** `omnimemora_runtime` is scoped to query-path operations. `read/delete` are outside its supported capability surface. This is a backend capability boundary, not an incomplete product feature.

## 8. 步骤完成状态

| Step | 描述 | 状态 |
|------|------|------|
| Step 1 | 创建目录结构 | ✅ |
| Step 2 | base.py (MemoryBackend 接口) | ✅ |
| Step 3 | factory.py | ✅ |
| Step 4 | openviking_backend.py | ✅ |
| Step 5 | main.py 移除 viking_request | ✅ |
| Step 6 | main.py backend 初始化 | ✅ |
| Step 7 | config.py 配置 | ✅ |
| Step 8 | /health 端点 | ✅ |
| Step 9 | omnimemora_runtime_backend.py | ✅ |
| Step 10 | 切换默认 backend | ✅ |
