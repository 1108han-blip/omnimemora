---
doc_id: LEGACY-BACKEND-INTERFACE-001
title: Backend Interface Definition (Legacy)
owner: platform-team
reviewers: [arch-lead]
status: deprecated
version: 1.0.0
effective_date: 2026-04-10
depends_on: [ADR-0007-BACKEND-ABSTRACTION]
supersedes: [SPEC-BACKEND-ABSTRACTION-001]
last_verified_commit: ""
---

# BACKEND_INTERFACE.md

**⚠️ 已废弃（Deprecated）**

> **替代文档：** `docs/spec/SPEC-BACKEND-ABSTRACTION-001.md`
> 本文件不再作为权威参考，所有新实现应引用 canonical spec。

---

## 1. 接口定义原则

### 1.1 必须遵守

- 接口只定义"记忆能力"，不定义"存储实现"
- 输入输出使用 memory record / scope / content 语义
- 不出现任何 backend 特有概念

### 1.2 禁止出现

- `viking` / `openviking` / `VIKING_URL`
- `mcp` / `MCP`
- `/api/v1/` REST 路径
- `viking://` URI 格式
- 文件系统路径（`/fs/`, `/resources/`）
- `temp_upload` / `commit` 两阶段概念

---

## 2. MemoryBackend 抽象接口

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class MemorySearchRequest:
    """搜索请求 - backend neutral"""
    query: str
    limit: int = 10
    scope: Optional[str] = None        # agent / workspace / user / tenant
    scope_ref: Optional[str] = None    # 具体的 scope 标识
    score_threshold: Optional[float] = None

@dataclass
class MemorySearchResult:
    """搜索结果 - backend neutral"""
    memories: List[MemoryRecord]
    total: int

@dataclass
class MemoryWriteRequest:
    """写入请求 - backend neutral"""
    content: str
    scope: str                          # agent / workspace / user / tenant
    scope_ref: str                     # 具体的 scope 标识
    metadata: Dict[str, Any]           # type, level, score, expire_at 等

@dataclass
class MemoryRecord:
    """记忆记录 - backend neutral"""
    memory_id: str
    content: str
    scope: str
    scope_ref: str
    metadata: Dict[str, Any]
    created_at: Optional[int] = None
    score: Optional[float] = None

@dataclass
class BackendHealth:
    """健康状态 - backend neutral"""
    healthy: bool
    backend_type: str
    details: Optional[Dict[str, Any]] = None


class MemoryBackend(ABC):
    """
    Memory Backend 抽象接口
    
    职责：存储、索引、搜索、快照
    不负责：内容过滤、ScopeRef 解析、权限判断
    
    所有 backend 实现必须满足此接口。
    """

    @abstractmethod
    async def search(
        self,
        request: MemorySearchRequest,
    ) -> MemorySearchResult:
        """
        搜索记忆
        
        Args:
            request: MemorySearchRequest
            
        Returns:
            MemorySearchResult: 匹配的 MemoryRecord 列表
        """
        pass

    @abstractmethod
    async def write(
        self,
        request: MemoryWriteRequest,
    ) -> MemoryRecord:
        """
        写入记忆
        
        Args:
            request: MemoryWriteRequest
            
        Returns:
            MemoryRecord: 写入后的记忆记录（含 memory_id）
        """
        pass

    @abstractmethod
    async def read(
        self,
        memory_id: str,
    ) -> Optional[MemoryRecord]:
        """
        按 ID 读取单条记忆
        
        Args:
            memory_id: 记忆 ID
            
        Returns:
            MemoryRecord 或 None
        """
        pass

    @abstractmethod
    async def delete(
        self,
        memory_id: str,
    ) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆 ID
            
        Returns:
            bool: 删除是否成功
        """
        pass

    @abstractmethod
    async def health(self) -> BackendHealth:
        """
        健康检查
        
        Returns:
            BackendHealth: 后端健康状态
        """
        pass
```

---

## 3. 接口语义约定

### 3.1 Scope 模型

| Scope | 说明 | 示例 |
|-------|------|------|
| `agent` | Agent 级别隔离 | `agent=supervisor` |
| `workspace` | 工作空间级别 | `workspace=ws-main` |
| `user` | 用户级别 | `user=user-001` |
| `tenant` | 租户级别 | `tenant=trial-abc123` |

### 3.2 Metadata 标准字段

```python
METADATA_FIELDS = {
    "type": str,           # general / strategy / failure_experience / result
    "level": str,          # L0 / L1 / L2 / L3
    "score": int,          # 重要性评分
    "expire_at": int,      # 过期时间戳，-1 表示永久
    "content_id": str,     # 内容去重 ID
    "agent": str,          # 来源 agent
    "created_by": str,      # 创建者
}
```

---

## 4. 验收标准

### 4.1 接口纯度检查

以下命令在 `BACKEND_INTERFACE.md` 外的核心文件中执行，应返回 0 行：

```bash
# 接口文件不应出现 backend 特有概念
grep -rn "viking\|openviking\|/api/v1/\|viking://" \
  --include="*.py" \
  --exclude="*_backend.py" \
  5_connectors/adapter/
# 期望：0 行
```

### 4.2 接口实现检查

所有 Backend Adapter 必须实现：
- `search()`
- `write()`
- `read()`
- `delete()`
- `health()`

缺少任一方法则为不合格实现。

---

## 5. 与宪法一致性

| 宪法原则 | 接口实现 |
|---------|---------|
| Backend-agnostic | 接口不依赖任何特定 backend |
| Control Plane / Memory Plane 分离 | Connector 只调接口，不知道 storage 实现 |
| 可替换性 | 任何满足接口的 backend 都可接入 |
