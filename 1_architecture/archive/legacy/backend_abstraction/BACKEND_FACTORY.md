---
doc_id: LEGACY-BACKEND-FACTORY-001
title: Backend Factory Wiring Rules (Legacy)
owner: platform-team
reviewers: [arch-lead]
status: deprecated
version: 1.0.0
effective_date: 2026-04-10
depends_on: [ADR-0007-BACKEND-ABSTRACTION]
supersedes: [SPEC-BACKEND-ABSTRACTION-001]
last_verified_commit: ""
---

# BACKEND_FACTORY.md

**⚠️ 已废弃（Deprecated）**

> **替代文档：** `docs/spec/SPEC-BACKEND-ABSTRACTION-001.md`

---

## 1. 配置结构

### 1.1 新配置项（backend-neutral）

```python
# config.py

class MemoryBackendConfig(BaseModel):
    """Memory Backend 配置"""
    backend_type: str = "omnimemora_runtime"  # openviking / omnimemora_runtime
    base_url: str = "http://127.0.0.1:8765"
    api_key: Optional[str] = None
    timeout_seconds: float = 30.0
    connect_timeout_seconds: float = 5.0
```

### 1.2 兼容配置（deprecated）

```python
# 兼容旧配置，但标记为 deprecated
class LegacyVikingConfig(BaseModel):
    """Legacy OpenViking 配置 - DEPRECATED"""
    viking_url: str = "http://host.docker.internal:1933"
    viking_api_key: str = ""
    
    class Config:
        deprecated = True
```

### 1.3 Config 整合

```python
class Config(BaseModel):
    # ... 其他配置 ...
    
    # Memory Backend 配置
    memory_backend: MemoryBackendConfig = MemoryBackendConfig()
    
    # Legacy 兼容（仅供 OpenVikingBackend 使用）
    # DEPRECATED: 请迁移到 memory_backend 配置
    viking_url: Optional[str] = None
    viking_api_key: Optional[str] = None
```

---

## 2. Backend Registry

```python
# backends/__init__.py

from typing import Type, Dict

# Backend 类型注册表
BACKEND_REGISTRY: Dict[str, Type[MemoryBackend]] = {}


def register_backend(backend_type: str):
    """Backend 注册装饰器"""
    def decorator(cls: Type[MemoryBackend]) -> Type[MemoryBackend]:
        BACKEND_REGISTRY[backend_type] = cls
        return cls
    return decorator


def get_backend_class(backend_type: str) -> Type[MemoryBackend]:
    """获取 backend 类型"""
    if backend_type not in BACKEND_REGISTRY:
        raise ValueError(
            f"Unknown backend type: {backend_type}. "
            f"Available: {list(BACKEND_REGISTRY.keys())}"
        )
    return BACKEND_REGISTRY[backend_type]
```

---

## 3. Backend Factory

```python
# backends/factory.py

from typing import Optional
from .base import MemoryBackend
from .openviking_backend import OpenVikingBackend
from .omnimemora_runtime_backend import OmniMemoraRuntimeBackend

# 注册 backend
register_backend("openviking")(OpenVikingBackend)
register_backend("omnimemora_runtime")(OmniMemoraRuntimeBackend)


def create_backend(config: MemoryBackendConfig) -> MemoryBackend:
    """
    创建 Memory Backend 实例
    
    Args:
        config: MemoryBackendConfig 配置对象
        
    Returns:
        MemoryBackend: 满足接口的 backend 实例
        
    Raises:
        ValueError: 未知的 backend 类型
    """
    backend_type = config.backend_type
    
    # 兼容旧配置
    if config.backend_type == "openviking":
        # 使用 legacy 配置
        pass
    
    backend_class = get_backend_class(backend_type)
    return backend_class(
        base_url=config.base_url,
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
        connect_timeout_seconds=config.connect_timeout_seconds,
    )


def create_backend_from_env() -> MemoryBackend:
    """从环境变量创建 backend（用于简单场景）"""
    import os
    
    backend_type = os.getenv("MEMORY_BACKEND_TYPE", "omnimemora_runtime")
    base_url = os.getenv("MEMORY_BACKEND_URL", "http://127.0.0.1:8765")
    api_key = os.getenv("MEMORY_BACKEND_API_KEY")
    
    config = MemoryBackendConfig(
        backend_type=backend_type,
        base_url=base_url,
        api_key=api_key,
    )
    
    return create_backend(config)
```

---

## 4. Backend 类型定义

### 4.1 支持的类型

| backend_type | 说明 | 状态 |
|--------------|------|------|
| `omnimemora_runtime` | OmniMemora Runtime (8765) | 推荐 |
| `openviking` | OpenViking (1933) | 兼容（deprecated） |

### 4.2 Future Backend（预留）

```python
# 未来可扩展
@register_backend("sqlite")
class SQLiteBackend(MemoryBackend):
    """本地 SQLite Backend - Future"""
    pass

@register_backend("postgres")
class PostgresBackend(MemoryBackend):
    """PostgreSQL Backend - Future"""
    pass
```

---

## 5. 配置加载优先级

### 5.1 优先级顺序

```
1. 显式传入的 config 对象（最高）
2. 环境变量（MEMORY_BACKEND_TYPE, MEMORY_BACKEND_URL, ...）
3. 默认值（最低）
```

### 5.2 环境变量映射

| 环境变量 | 配置字段 | 默认值 |
|----------|---------|--------|
| `MEMORY_BACKEND_TYPE` | `backend_type` | `omnimemora_runtime` |
| `MEMORY_BACKEND_URL` | `base_url` | `http://127.0.0.1:8765` |
| `MEMORY_BACKEND_API_KEY` | `api_key` | `None` |

---

## 6. 初始化入口

### 6.1 Connector 中的使用

```python
# 5_connectors/adapter/main.py

from backends.factory import create_backend_from_config

# 在 app 初始化时
backend = create_backend_from_config(config.memory_backend)

# 在需要的地方使用
result = await backend.search(MemorySearchRequest(...))
```

### 6.2 单例模式（可选）

```python
# 全局 backend 实例
_backend: Optional[MemoryBackend] = None


def get_memory_backend() -> MemoryBackend:
    """获取全局 backend 实例（单例）"""
    global _backend
    if _backend is None:
        _backend = create_backend_from_config(config.memory_backend)
    return _backend


def set_memory_backend(backend: MemoryBackend) -> None:
    """设置全局 backend 实例（用于测试）"""
    global _backend
    _backend = backend
```

---

## 7. 健康检查集成

### 7.1 Connector /health 输出

```python
@app.get("/health")
async def health():
    backend = get_memory_backend()
    backend_health = await backend.health()
    
    return {
        "status": "healthy" if backend_health.healthy else "degraded",
        "memory_backend": {
            "type": backend_health.backend_type,
            "healthy": backend_health.healthy,
            "details": backend_health.details,
        }
    }
```

### 7.2 输出对比

**Before（OpenViking 特有）：**
```json
{
  "viking_url": "http://host.docker.internal:1933",
  "viking_connected": true
}
```

**After（Backend Neutral）：**
```json
{
  "memory_backend": {
    "type": "omnimemora_runtime",
    "healthy": true,
    "details": null
  }
}
```

---

## 8. 错误处理

### 8.1 Backend 错误类型

```python
class BackendError(Exception):
    """Backend 相关错误"""
    
    BAD_REQUEST = "backend_bad_request"
    UNAUTHORIZED = "backend_unauthorized"
    FORBIDDEN = "backend_forbidden"
    NOT_FOUND = "backend_not_found"
    INTERNAL_ERROR = "backend_internal_error"
    BAD_GATEWAY = "backend_bad_gateway"
    SERVICE_UNAVAILABLE = "backend_service_unavailable"
    NOT_IMPLEMENTED = "backend_not_implemented"
    UNKNOWN = "backend_unknown"
    
    def __init__(self, error_type: str, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(f"[{error_type}] {message}")
```

### 8.2 Factory 错误处理

```python
def create_backend(config: MemoryBackendConfig) -> MemoryBackend:
    try:
        return _create_backend_impl(config)
    except ValueError as e:
        # 未知 backend 类型
        raise
    except Exception as e:
        # 其他错误包装
        raise BackendError(
            BackendError.INTERNAL_ERROR,
            f"Failed to create backend: {e}"
        )
```
