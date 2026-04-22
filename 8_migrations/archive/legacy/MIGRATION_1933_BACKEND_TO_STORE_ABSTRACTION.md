# MEMORY_BACKEND_INTERFACE.md

**Status:** PATCH（Implementation Guide）
**Scope:** MUST NOT override Blueprint / Constitution / RUNTIME_ARCHITECTURE
**If conflict occurs: Blueprint wins**
**Purpose:** 抽象 OmniMemora Memory Backend (1933) 为正式 Backend Interface，ScopeRef 随请求传递，URI 是存储映射
**Based on:** v2.3 (E:/AI/docker-data/memory-adapter) 实际调用链路
**Last Updated:** 2026-04-08

---

## 冲突标记表

| 对比维度 | Blueprint（RUNTIME_ARCHITECTURE.md） | 本文 | 风险等级 | 处理方式 |
| --- | --- | --- | --- | --- |
| Store 接口定义 | Go interface（RUNTIME_ARCHITECTURE.md L598-635） | Python ABC | **中** | Blueprint Go 为 Future 目标；本文为 Python 现有实现锚点 |
| 默认 Backend | SQLite（RUNTIME_ARCHITECTURE.md L638-646） | OmniMemora Memory Backend (1933) | **高** | Blueprint SQLite 为 Future 目标；本文 1933 为当前实现锚点 |
| Backend 替换策略 | 替换 store 实现类（RUNTIME_ARCHITECTURE.md L668-680） | 替换 Backend 类型 | **中** | Blueprint 提供替换策略框架；本文提供具体实现路径 |

**说明**：本文档描述现有 Python/1933 架构下的 Backend 抽象层，用于指导 v2.3→v2.4 增量改造。Blueprint 的 Go/SQLite 为 Future 重写目标，两者定位不同。

---

# 一、接口定位

```
┌────────────────────────────────────────────────────────────────┐
│            OmniMemora Runtime Service (8000)                     │
│                                                                 │
│  normalize() → filter() → classify() → resolve_scope()           │
│                        ↓                                        │
│               BackendInterface (抽象层)                          │
│                        ↓                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         OmniMemora Memory Backend (当前实现)              │   │
│  │         http://omni-memora-backend:1933                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                        OR                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         FutureBackend (Future 扩展)                       │   │
│  │         e.g., SQLite / PostgreSQL / Milvus               │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

**设计原则**：
- Backend Interface 是纯存储抽象，不感知 ScopeRef 治理逻辑
- ScopeRef 在 Runtime Service 层解析，结果以 URI/flags 形式传递给 Backend
- Backend 仅负责：持久化、索引、搜索、快照，不承担权限判断

---

# 二、接口契约

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class MemoryBackend(ABC):
    """
    OmniMemora Memory Backend 抽象接口

    职责：存储、索引、搜索、快照
    不负责：内容过滤、ScopeRef 解析、权限判断
    """

    # ---------- 写操作 ----------

    @abstractmethod
    async def write(
        self,
        content: str,
        uri: str,
        metadata: Dict[str, Any],
        wait: bool = True,
    ) -> Dict[str, Any]:
        """
        写入单条记忆

        Args:
            content: 记忆正文 (markdown)
            uri: 资源 URI (viking://resources/...)
            metadata: 元数据字典
                - agent: str
                - type: str
                - memory_type: str (local_only / long_term / short_term)
                - memory_level: str (L0 / L1 / L2 / L3)
                - score: int
                - expire_at: int (-1 = 永久)
                - content_id: str (去重ID)
                - scope: str (user / workspace / agent / custom) — 仅作为元数据记录
                - sharing_mode: str (isolated / shared / shared_read_only) — 仅作为元数据记录
            wait: 是否等待提交完成

        Returns:
            {
                "status": "stored" | "error",
                "uri": str,   # 实际存储 URI
                "root_uri": str,
            }
        """
        pass

    @abstractmethod
    async def temp_upload(
        self,
        file_name: str,
        content: bytes,
        mime_type: str,
    ) -> Dict[str, Any]:
        """
        上传到临时存储

        Args:
            file_name: 文件名
            content: 文件内容 bytes
            mime_type: MIME 类型

        Returns:
            {"temp_path": str}
        """
        pass

    # ---------- 读操作 ----------

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int,
        target_uri: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        语义搜索记忆

        Args:
            query: 搜索 query
            limit: 返回数量上限
            target_uri: 搜索范围根 URI（由 Runtime Service 根据 ScopeRef 构建）
            score_threshold: 最低相似度分数

        Returns:
            {"memories": [...], "total": int}
        """
        pass

    @abstractmethod
    async def read(
        self,
        query: Optional[str] = None,
        uri: Optional[str] = None,
        agent: Optional[str] = None,
        memory_type: Optional[str] = None,
        memory_level: Optional[str] = None,
        limit: int = 10,
        include_expired: bool = False,
    ) -> Dict[str, Any]:
        """
        按 query 或 uri 读取记忆

        Returns:
            {"memories": [...], "total": int}
            或 {"content": str} (单条 URI 读取)
        """
        pass

    # ---------- 删操作 ----------

    @abstractmethod
    async def delete(self, uri: str) -> Dict[str, Any]:
        """
        按 URI 删除记忆

        Args:
            uri: 资源 URI

        Returns:
            {"success": bool, "uri": str}
        """
        pass

    # ---------- 命名空间操作 ----------

    @abstractmethod
    async def ensure_namespace(self, uri: str) -> bool:
        """确保命名空间路径存在"""
        pass

    @abstractmethod
    async def namespace_exists(self, uri: str) -> bool:
        """检查命名空间是否存在"""
        pass

    # ---------- 快照操作 ----------

    @abstractmethod
    async def snapshot(
        self,
        agent: str,
        limit: int,
    ) -> Dict[str, Any]:
        """
        生成启动快照摘要（由 Runtime Service 调用）

        Returns:
            {
                "agent": str,
                "generatedAt": str,
                "sourceCount": int,
                "markdown": str,
                "sections": {...}
            }
        """
        pass

    # ---------- 健康检查 ----------

    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        """
        Backend 健康检查

        Returns:
            {"healthy": bool, "detail": {...}}
        """
        pass
```

---

# 三、OmniMemoraMemoryBackend 实现（当前）

## 3.1 文件位置

```
E:/AI/docker-data/memory-adapter/app/backends/
├── __init__.py
├── omni_memory_backend.py   # 当前实现（替代原 openviking_backend.py）
└── sqlite_backend.py        # Future 扩展
```

## 3.2 实现

```python
# E:/AI/docker-data/memory-adapter/app/backends/omni_memory_backend.py
"""
OmniMemora Memory Backend 实现 v1.0
对应 OmniMemora Memory Backend (1933)
"""
import httpx
from typing import Dict, Any, Optional

from app.config import config


class OmniMemoraMemoryBackend:
    """对接 http://omni-memora-backend:1933 的 Backend 实现"""

    def __init__(self, backend_url: str = None, api_key: str = None):
        # 优先用新配置名，兼容旧名
        self.backend_url = (
            backend_url
            or getattr(config, "backend_url", None)
            or config.viking_url
        )
        self.api_key = (
            api_key
            or getattr(config, "backend_api_key", None)
            or config.viking_api_key
        )

    def _headers(self) -> Dict[str, str]:
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _timeout(self, seconds: float) -> httpx.Timeout:
        return httpx.Timeout(
            timeout=seconds,
            connect=config.viking_connect_timeout_seconds,
        )

    # ---------- 写 ----------

    async def write(
        self,
        content: str,
        uri: str,
        metadata: Dict[str, Any],
        wait: bool = True,
    ) -> Dict[str, Any]:
        """两阶段写入：temp_upload → commit"""
        temp_resp = await self.temp_upload(
            file_name="memory.md",
            content=content.encode("utf-8"),
            mime_type="text/markdown",
        )
        temp_path = temp_resp.get("temp_path")
        if not temp_path:
            raise ValueError("temp_upload returned no temp_path")

        commit_payload = {
            "temp_path": temp_path,
            "to": uri,
            "reason": f"omni-memora:{metadata.get('memory_type', 'general')}",
            "instruction": "Store this text as retrievable long-term memory for the agent.",
            "wait": wait,
        }
        async with httpx.AsyncClient(timeout=self._timeout(config.viking_commit_timeout_seconds)) as client:
            response = await client.post(
                f"{self.backend_url}/api/v1/resources",
                headers=self._headers(),
                json=commit_payload,
            )
        if not response.is_success:
            raise RuntimeError(f"commit failed: {response.status_code}")
        return response.json()

    async def temp_upload(
        self,
        file_name: str,
        content: bytes,
        mime_type: str,
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout(config.viking_upload_timeout_seconds)) as client:
            response = await client.post(
                f"{self.backend_url}/api/v1/resources/temp_upload",
                headers=self._headers(),
                files={"file": (file_name, content, mime_type)},
            )
        if not response.is_success:
            raise RuntimeError(f"temp_upload failed: {response.status_code}")
        return response.json()

    # ---------- 读 ----------

    async def search(
        self,
        query: str,
        limit: int,
        target_uri: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"query": query, "limit": limit}
        if target_uri:
            payload["target_uri"] = target_uri
        if score_threshold is not None:
            payload["score_threshold"] = score_threshold

        async with httpx.AsyncClient(timeout=self._timeout(config.viking_search_timeout_seconds)) as client:
            response = await client.post(
                f"{self.backend_url}/api/v1/search/find",
                headers=self._headers(),
                json=payload,
            )
        if not response.is_success:
            raise RuntimeError(f"search failed: {response.status_code}")
        return response.json()

    async def read(
        self,
        query: Optional[str] = None,
        uri: Optional[str] = None,
        agent: Optional[str] = None,
        memory_type: Optional[str] = None,
        memory_level: Optional[str] = None,
        limit: int = 10,
        include_expired: bool = False,
    ) -> Dict[str, Any]:
        from urllib.parse import quote

        if uri:
            encoded_uri = quote(uri, safe="")
            async with httpx.AsyncClient(timeout=self._timeout(config.viking_read_timeout_seconds)) as client:
                response = await client.get(
                    f"{self.backend_url}/api/v1/content/read?uri={encoded_uri}",
                    headers=self._headers(),
                )
            if not response.is_success:
                raise RuntimeError(f"read failed: {response.status_code}")
            result = response.json()
            return {"content": result.get("result")}

        payload: Dict[str, Any] = {"query": query or "", "limit": limit}
        if agent:
            payload["agent"] = agent
        if memory_type:
            payload["memory_type"] = memory_type

        async with httpx.AsyncClient(timeout=self._timeout(config.viking_read_timeout_seconds)) as client:
            response = await client.post(
                f"{self.backend_url}/retrieve",
                headers=self._headers(),
                json=payload,
            )
        if not response.is_success:
            raise RuntimeError(f"query read failed: {response.status_code}")
        return response.json()

    # ---------- 删 ----------

    async def delete(self, uri: str) -> Dict[str, Any]:
        from urllib.parse import quote
        encoded_uri = quote(uri, safe="")
        async with httpx.AsyncClient(timeout=self._timeout(config.viking_delete_timeout_seconds)) as client:
            response = await client.delete(
                f"{self.backend_url}/api/v1/fs?uri={encoded_uri}",
                headers=self._headers(),
            )
        if not response.is_success:
            raise RuntimeError(f"delete failed: {response.status_code}")
        return response.json()

    # ---------- 命名空间 ----------

    async def ensure_namespace(self, uri: str) -> bool:
        from app.main import ensure_namespace_tree
        return await ensure_namespace_tree(uri)

    async def namespace_exists(self, uri: str) -> bool:
        from app.main import namespace_exists
        return await namespace_exists(uri)

    # ---------- 快照 ----------

    async def snapshot(self, agent: str, limit: int) -> Dict[str, Any]:
        # snapshot 由 Runtime Service endpoint 直接实现，不通过 Backend
        raise NotImplementedError("snapshot is handled by Runtime Service endpoint")

    # ---------- 健康检查 ----------

    async def health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout(config.viking_health_timeout_seconds)) as client:
            response = await client.get(
                f"{self.backend_url}/health",
                headers=self._headers(),
            )
        return {
            "healthy": response.status_code == 200,
            "status_code": response.status_code,
        }


# ---------- 全局单例 ----------

_backend: Optional[OmniMemoraMemoryBackend] = None


def get_backend() -> OmniMemoraMemoryBackend:
    global _backend
    if _backend is None:
        _backend = OmniMemoraMemoryBackend()
    return _backend


def set_backend(backend: OmniMemoraMemoryBackend) -> None:
    global _backend
    _backend = backend
```

---

# 四、真抽象强制规则（施工检查红线）

**Backend Interface 是真抽象，不是假壳。以下三条红线在施工中必须满足：**

| 红线规则 | 说明 | 验收命令 |
| --- | --- | --- |
| **RT-1** | Runtime Service 内部禁止直接拼接 1933 HTTP URL | `grep -rn "1933\|openviking-server" app/main.py` → 0 行 |
| **RT-2** | Runtime Service 内部禁止直接依赖 `VIKING_URL` 环境变量 | `grep -rn "VIKING_URL\|viking_url" app/main.py` → 仅 config.py 定义行 |
| **RT-3** | 所有 backend 调用必须经 `get_backend().write()/search()/read()/delete()` | `grep -rn "httpx.AsyncClient\|requests\." app/main.py` → 仅 backends/ 目录下合法 |

**违规示例（禁止出现）：**

```python
# ❌ 禁止：Runtime 内直接拼 1933 URL
async with httpx.AsyncClient() as client:
    await client.post(f"{config.viking_url}/api/v1/resources", ...)

# ✅ 正确：经 Backend Interface
backend = get_backend()
await backend.write(content=..., uri=..., metadata=...)
```

**合法路径（仅限 Backend 实现层）：**

```text
app/backends/omni_memory_backend.py   ← 仅此处可出现 httpx + 1933 URL
app/backends/sqlite_backend.py        ← Future 扩展
app/backends/__init__.py              ← 工厂函数
```

---

# 五、main.py 改造点

## 4.1 Backend 接口调用改造

| 函数 | 改造前 | 改造后 |
| --- | --- | --- |
| `write_memory()` | 直接调用 `viking_request()` | 调用 `get_backend().write()` |
| `search_memory()` | 直接调用 `viking_request()` | 调用 `get_backend().search()` |
| `read_memory()` | 直接调用 `viking_request()` | 调用 `get_backend().read()` |
| `delete_memory()` | 直接调用 `viking_request()` | 调用 `get_backend().delete()` |
| `health()` | 直接调用 `viking_request()` | 调用 `get_backend().health()` |
| `build_memory_snapshot()` | 直接调用 local functions | 保持（复用 main.py scope 逻辑） |

## 4.2 注入点

```python
# main.py 顶部
from app.backends.omni_memory_backend import get_backend, set_backend, OmniMemoraMemoryBackend
```

```python
# write_memory() 中的改造（约 L1359-1416）
# 原：直接调用 viking_request POST /api/v1/resources
# 改：
backend = get_backend()
try:
    result = await backend.write(
        content=resource_markdown,
        uri=resource_uri,
        metadata={
            "agent": request.agent,
            "type": data.get("type", request.type),
            "memory_type": memory_type,
            "memory_level": memory_level,
            "score": score,
            "expire_at": expire_at,
            "content_id": content_id,
            "scope": scope,           # ScopeRef 字段透传
            "sharing_mode": sharing_mode,
        },
    )
except RuntimeError as e:
    # 错误映射保持不变
    ...
```

---

# 六、向后兼容

## 5.1 环境变量兼容

| 旧变量 | 新变量 | 优先级 |
| --- | --- | --- |
| `VIKING_URL` | `BACKEND_URL` | 旧名仍生效 |
| `VIKING_API_KEY` | `BACKEND_API_KEY` | 旧名仍生效 |
| `MEMORY_BACKEND=openviking` | `MEMORY_BACKEND=omni_memory` | 兼容 |

## 5.2 Backend 类型注册

```python
# app/backends/__init__.py

from app.backends.omni_memory_backend import OmniMemoraMemoryBackend
from app.backends.sqlite_backend import LocalSQLiteBackend  # Future

BACKEND_REGISTRY = {
    "omni_memory": OmniMemoraMemoryBackend,  # 当前默认
    "openviking": OmniMemoraMemoryBackend,    # 兼容旧名
    "sqlite": LocalSQLiteBackend,              # Future
}


def create_backend(backend_type: str = None) -> MemoryBackend:
    bt = backend_type or os.getenv("MEMORY_BACKEND", "omni_memory")
    cls = BACKEND_REGISTRY.get(bt)
    if cls is None:
        raise ValueError(f"Unknown backend type: {bt}")
    return cls()
```

---

# 七、Future: LocalSQLiteBackend（Future 扩展）

> **注意**：此节为 Future 扩展，不在 MVP 范围内。

```python
# app/backends/sqlite_backend.py
"""
Local SQLite Backend — Future 扩展
不依赖 1933，适用于纯本地离线场景
"""
import sqlite3, json, os
from typing import Dict, Any


class LocalSQLiteBackend:
    def __init__(self, db_path: str = "/app/data/memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                uri TEXT UNIQUE,
                content TEXT,
                agent TEXT,
                memory_type TEXT,
                memory_level TEXT,
                score INTEGER,
                expire_at INTEGER,
                created_at INTEGER,
                metadata TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON memories(agent)")
        conn.commit()
        conn.close()

    async def write(self, content: str, uri: str, metadata: Dict, wait: bool = True) -> Dict:
        import uuid, time
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO memories
            (id, uri, content, agent, memory_type, memory_level, score, expire_at, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), uri, content, metadata.get("agent"),
              metadata.get("memory_type"), metadata.get("memory_level"),
              metadata.get("score", 0), metadata.get("expire_at", -1),
              int(time.time()), json.dumps(metadata)))
        conn.commit()
        conn.close()
        return {"status": "stored", "uri": uri}

    async def search(self, query: str, limit: int, target_uri=None, score_threshold=None) -> Dict:
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute(
            "SELECT uri, content, agent, memory_type, memory_level, score, metadata "
            "FROM memories WHERE content LIKE ? ORDER BY score DESC LIMIT ?",
            (f"%{query}%", limit))
        rows = cur.fetchall()
        conn.close()
        memories = [{"uri": r[0], "content": r[1], "agent": r[2],
                     "memory_type": r[3], "memory_level": r[4],
                     "score": r[5], "metadata": json.loads(r[6]) if r[6] else {}} for r in rows]
        return {"memories": memories, "total": len(memories)}

    async def delete(self, uri: str) -> Dict:
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM memories WHERE uri = ?", (uri,))
        conn.commit()
        conn.close()
        return {"success": True, "uri": uri}

    async def health(self) -> Dict:
        return {"healthy": True}
```

---

# 八、决策追溯

| 决策 | 来源 | 影响 |
| --- | --- | --- |
| Decision 02: Cloud Optional | DECISION_LEDGER | Backend 抽象允许替换云端为本地 SQLite |
| Decision 06: Single Runtime | DECISION_LEDGER | 每个 Runtime 实例对应一个 Backend 实例 |
| Decision 01: Local First | DECISION_LEDGER | 默认本地 Backend，Docker 即生产态 |

---

# 九、验收标准

1. **接口完整**：write / search / read / delete / snapshot / health 均通过 Backend 接口
2. **向后兼容**：`MEMORY_BACKEND=openviking` 仍指向当前实现
3. **ScopeRef 透传**：metadata 中含 scope / sharing_mode，随写入存入 Backend
4. **可切换**：Future 可通过 `MEMORY_BACKEND=sqlite` 切换到 LocalSQLiteBackend
5. **代码改动最小**：仅改动 main.py 的 HTTP 调用层，不改动 Router/Filter 逻辑
6. **真抽象**：Runtime Service 层不出现直连 1933 的 HTTP 调用（grep 验收）
7. **Grep 级验收**：

```bash
# RT-1：Runtime 内无直接 1933 HTTP
grep -rn "1933\|openviking-server" app/main.py
# 期望：0 行

# RT-2：Runtime 内无直连 VIKING_URL
grep -rn "VIKING_URL\|viking_url" app/main.py
# 期望：0 行（config.py 定义行除外）

# RT-3：httpx/requests 仅出现在 backends/ 目录
grep -rn "httpx.AsyncClient\|requests\." app/main.py | grep -v "backends/"
# 期望：0 行
```
