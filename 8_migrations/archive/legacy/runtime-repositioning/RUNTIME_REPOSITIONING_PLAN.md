# RUNTIME_REPOSITIONING_PLAN.md

**Status:** PATCH（Implementation Guide）
**Scope:** MUST NOT override Blueprint / Constitution / RUNTIME_ARCHITECTURE
**If conflict occurs: Blueprint wins**
**Based on:** v2.3 (E:/AI/docker-data/memory-adapter) + v2.2 (4_core/adapter-raw) 实际运行态
**Last Updated:** 2026-04-08

---

## 冲突标记表

| 对比维度 | Blueprint（RUNTIME_ARCHITECTURE.md） | 本文 | 风险等级 | 处理方式 |
| --- | --- | --- | --- | --- |
| ScopeRef 字段 | 包含 `tenant_id` | 无 `tenant_id` | **高** | 以 Blueprint 为准 |
| Scope 来源优先级 | body > header > config（L354-358） | header > body > config | **高** | 以 Blueprint 为准 |
| 默认端口 | `8765`（RUNTIME_ARCHITECTURE.md L14） | `8765` ✅ | **低** | 2026-04-14: Runtime 现已使用 8765，Adapter 迁至 18011 |
| 默认 Store | SQLite（RUNTIME_ARCHITECTURE.md L638） | 1933 Backend | **极高** | 当前 1933 为现有实现锚点，Blueprint SQLite 为 Future 重写目标 |
| 接口语言 | Go（RUNTIME_ARCHITECTURE.md L598） | Python | **极高** | 现有实现为 Python，Blueprint Go 为 Future 重写目标 |

**说明**：本文档基于现有 Python/1933 实现，用于指导 v2.3→v2.4 的增量改造。Blueprint（RUNTIME_ARCHITECTURE.md）定义的是 Future 完整重写目标架构，两者定位不同。

---

# 一、官方命名体系（强制执行）

## 1.1 进程级正式命名

| 端口 | 官方名称 | 旧称（仅兼容说明用） |
| --- | --- | --- |
| **8765** | **OmniMemora Runtime Service** | （旧 8000 已废弃） |
| **18011** | **Memory Adapter Layer** | memory-adapter / adapter |
| **1933** | **OmniMemora Memory Backend** | OpenViking Server / viking-server |
| **整体** | **OmniMemora Runtime** | （无旧称） |

> **命名原则**：
> - 对内（代码/配置）：使用官方名称
> - 对外（文档/沟通）：使用官方名称
> - 旧名称仅在描述历史兼容时使用，不得作为设计依据

## 1.2 职责分工（已验证运行态）

**OmniMemora Runtime Service (8765)** — 认知编排层：
```
请求入口(/memory/write)
  → normalize()           [标准化字段统一]
  → should_store()       [过滤：长度/类型/关键词]
  → classify_memory_write() [两段式评分：L0提升判定 + 分层判定]
  → check_duplicate()    [去重检查]
  → _rate_limiter        [限流检查]
  → resolve_scope()      [ScopeRef 解析 + sharing_mode 推导]
  → build_scoped_uri()   [ScopeRef → URI 映射]
  → ensure_namespace_tree() [命名空间准备]
  → temp_upload()        [上传到 Backend 临时存储]
  → commit_resource()    [提交到 Backend 正式存储]
  → emit_metering_event() [绑定 ScopeRef 的 metering]
```

**禁止在 Runtime Service 层做的**：
- 直接写本地文件（Storage Backend 负责）
- 自己做 embedding/similarity 计算（委托 Backend）
- 承担 billing/UI 逻辑（Decision 07 禁止）

**OmniMemora Memory Backend (1933)** — 存储执行层：
```
接收 HTTP API 请求
  → /health              [健康检查]
  → /api/v1/resources/temp_upload  [临时文件上传]
  → /api/v1/resources  [资源提交]
  → /api/v1/search/find [向量搜索]
  → /api/v1/content/read [内容读取]
  → /api/v1/fs/tree    [目录树遍历]
  → /api/v1/fs/ls      [目录列表]
  → /api/v1/fs         [文件删除]
```

**Backend 不负责**：
- 内容过滤 / L0 提升判定
- 记忆类型/等级分配
- 去重 / 限流
- ScopeRef 解析

## 1.3 通信契约（已验证）

```
BACKEND_URL = http://openviking-server:1933  [Docker内部DNS，运行时注入]
BACKEND_API_KEY = openviking-local-dev-key-2026

超时配置：
- connect: 5s
- health: 5s
- search: 20s
- read: 20s
- delete: 20s
- snapshot: 60s
- upload: 20s
- commit: 45s
- resolve: 15s
- retry: 1次，backoff 0.75s
```

---

# 二、OmniMemora Runtime 官方边界

## 2.1 系统边界图

```
┌─────────────────────────────────────────────────────────────────┐
│                       OmniMemora Runtime                          │
│                                                                  │
│  ┌──────────────┐        ┌────────────────────────────────────┐  │
│  │ OpenClaw     │ ──────→│  OmniMemora Runtime Service (8765)  │  │
│  │ Plugins /    │  HTTP  │  - normalize                        │  │
│  │ Connectors   │ ←───── │  - filter / classify (L0/Tier)     │  │
│  └──────────────┘  JSON  │  - dedup + rate limit              │  │
│                         │  - ScopeRef 解析 + URI 映射          │  │
│                         │  - format convert                    │  │
│                         └───────────────┬──────────────────────┘  │
│                                         │                         │
│                                  HTTP+JSON                       │
│                                         │                         │
│                         ┌───────────────▼──────────────────────┐  │
│                         │  OmniMemora Memory Backend (1933)    │  │
│                         │  - persistence (workspace volume)    │  │
│                         │  - embedding / index                │  │
│                         │  - vector search                    │  │
│                         │  - snapshot                         │  │
│                         └─────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────┐        ┌────────────────────────────────────┐  │
│  │ Bootstrap   │ ──────→│  Config Injection                    │  │
│  │ Layer       │  ENV   │  - BACKEND_URL                      │  │
│  └──────────────┘        │  - BACKEND_API_KEY                  │  │
│                         │  - DEFAULT_USER_ID                   │  │
│                         │  - DEFAULT_WORKSPACE_ID              │  │
│                         └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 2.2 ScopeRef — 治理主体定义

**ScopeRef 是记忆访问权限的治理主体，URI 是 ScopeRef 的存储映射。**

```
ScopeRef = {
    user_id: str,         # 用户维度隔离标识
    workspace_id: str,     # 工作空间维度标识
    scope: str,           # user | workspace | agent | custom
    agent_id: str,         # agent 标识（运行时必填）
    sharing_mode: str,     # isolated | shared | shared_read_only | custom
}
```

**关键澄清**：
- ScopeRef 在 Runtime Service 层解析，是权限判断的唯一依据
- URI 是 ScopeRef 的持久化映射格式，但 URI 本身不承载权限语义
- 权限判断逻辑：`can_write(ScopeRef_A, ScopeRef_B)` / `can_read(ScopeRef_A, ScopeRef_B)`

## 2.3 URI 路径结构（存储映射，非权限依据）

```
viking://resources/memory-adapter/{user_id}/{workspace_id}/{scope}/{agent_id}/{memory_type}/mem-{uuid}.md
```

| 路径段 | 来源 | 说明 |
| --- | --- | --- |
| `user_id` | ScopeRef.user_id | 用户维度 |
| `workspace_id` | ScopeRef.workspace_id | 工作空间维度 |
| `scope` | ScopeRef.scope | 隔离域类型 |
| `agent_id` | ScopeRef.agent_id | agent 标识 |
| `memory_type` | L0提升判定结果 | local_only / long_term / short_term |
| `mem-{uuid}.md` | 系统生成 | 具体记忆文件 |

**memory_type**:
- `local_only`: 留在 L0，不远程
- `long_term`: 长期记忆
- `short_term`: 短期缓存

## 2.4 本地运行时定位：执行层 / Memory Plane，非 Control Plane

**强制声明：**

OmniMemora 本地运行时（8765+1933）是**执行层（Memory Plane）**，不是 Control Plane。

| 层级 | 职责 | 归属 |
| --- | --- | --- |
| **Control Plane**（云端） | 元数据聚合、Token Savings UI、全局治理策略 | 云端服务 |
| **Memory Plane / 执行层**（本地） | 记忆写入、检索、scope 隔离、metering 事件产生 | 本地 Runtime (8765+1933) |

**硬规则：**

- 本地 Runtime 永不自称"Control Plane"
- 本地 Runtime 的 metering 事件发往 Control Plane，不在本地做聚合
- 本地 Runtime 不承担 UI 渲染、全局策略配置职责

---

# 三、命名治理

## 3.1 立即废弃（旧名称不得出现在新代码/新设计中）

| 旧名称 | 废弃原因 |
| --- | --- |
| `memory-adapter` 服务名 | 混淆 Runtime Service 与 Backend |
| `viking` 变量前缀 | 与 Backend 产品名混淆 |
| `adapter-memory-adapter` 容器名 | 应改为 `omni-memora-service` |
| `openviking-server` 容器名 | 应改为 `omni-memora-backend` |

## 3.2 保留兼容（旧代码/配置中可见，新设计禁止）

| 兼容名称 | 说明 |
| --- | --- |
| `VIKING_URL` 环境变量 | 仍指向 Backend URL（过渡期） |
| `/memory/*` API 路径 | 保持兼容 OpenClaw 插件 |
| `memory_level` 字段 (L0/L1/L2/L3) | 已稳定，保留 |

## 3.3 新增官方命名

| 新名称 | 说明 |
| --- | --- |
| `OmniMemora Runtime Service` | 8765 进程官方名称 |
| `OmniMemora Memory Backend` | 1933 进程官方名称 |
| `OmniMemora Runtime` | 整体联合体 |
| `ScopeRef` | 治理主体抽象 |
| `backend_url` | 配置属性（替代 `viking_url`） |
| `backend_api_key` | 配置属性（替代 `viking_api_key`） |

---

# 四、迁移路径

## 4.1 配置兼容（已实现，过渡期）

```python
# E:/AI/docker-data/memory-adapter/app/config.py
class Config(BaseModel):
    # 旧名仍支持（向后兼容）
    viking_url: str = os.getenv("VIKING_URL", "http://host.docker.internal:1933")
    viking_api_key: str = os.getenv("VIKING_API_KEY", "")

    # 新名指向同一值（向前兼容）
    @property
    def backend_url(self) -> str:
        return self.viking_url

    @property
    def backend_api_key(self) -> str:
        return self.viking_api_key
```

## 4.2 容器命名（下一步）

```yaml
# docker-compose.yml
services:
  omni-memora-service:   # 替代 adapter-memory-adapter (Adapter层，18011端口)
    image: ghcr.io/.../memory-adapter:latest
    ports:
      - "18011:18011"
    environment:
      - VIKING_URL=http://omni-memora-backend:1933

  omni-memora-backend:   # 替代 openviking-server
    image: ghcr.io/volcengine/openviking:main
    ports:
      - "1933:1933"
```

---

# 四、清理项（施工验收强制检查）

以下路径/代码必须在本次改造中**删除或禁用**，不得以"兼容"名义保留。

| 清理项 | 目标文件/路径 | 验收动作 |
| --- | --- | --- |
| 删除 `VIKING_URL` 直连 HTTP 调用 | `app/main.py` 内所有 `viking_request()` 直接调用 | `grep -n "viking_url\|VIKING_URL\|viking_request" app/main.py` 应返回 0 |
| 禁止 adapter 直连 1933 | `app/main.py` 内所有 `POST /api/v1/resources` 直连 | `grep -n "1933\|openviking-server" app/main.py` 应返回 0 |
| 禁止 connector 绕过 8765 | Codex connector / OpenClaw connector 配置 | 确认无 connector → 1933 直连路径 |
| 废弃旧 `/memory/*` 云端路径 | `app/main.py` 云端路由声明 | 确认无 `app.post("/cloud/...")` 等遗留路由 |
| 删除旧 `viking_request()` 函数 | `app/main.py` | 确认函数已移除或标记为废弃 |

**验收自检命令（必须在交付前执行）：**

```bash
# 检查 Runtime Service 层不再有直接 1933 HTTP 调用
grep -rn "httpx.*1933\|requests.*1933\|http://.*1933\|POST.*resources\|GET.*content/read" app/main.py

# 检查 memory write/query/delete 全部经过 scope enforcement
grep -rn "resolve_scope_ref\|enforce_scope\|can_write\|can_delete" app/main.py

# 检查不再出现直连 VIKING_URL 的散落 HTTP 调用
grep -rn "os.getenv.*VIKING\|config.viking_url\|config.viking_api_key" app/main.py
```

所有 grep 命令返回行数应为 0，方可认为清理完成。

---

# 五、决策追溯

| 决策 | 来源 | 影响范围 |
| --- | --- | --- |
| Decision 06: Single Runtime | DECISION_LEDGER | 一个用户/workspace 一个 Runtime 实例（8765+1933） |
| Decision 07: Bootstrap Layer 作为入口 | DECISION_LEDGER | Bootstrap 负责安装/配置/升级，不含 UI/计量 |
| Decision 01: Local First | DECISION_LEDGER | 默认本地运行，Docker 部署即为生产态 |

---

# 六、验收标准

## 6.1 功能验收

1. **职责不越界**：Runtime Service 不直接写存储；Memory Backend 不做内容过滤
2. **命名统一**：代码/文档中不再出现 `adapter` / `viking` 作为产品级命名
3. **API 路径不变**：`/memory/write/search/read/delete/snapshot` 保持兼容
4. **ScopeRef 主导**：URI 是存储映射，权限判断依据 ScopeRef
5. **Docker 网络正确**：`VIKING_URL=http://omni-memora-backend:1933` 在 Docker 内可解析
6. **本地非 Control Plane**：本地 Runtime 明确为 Memory Plane，metering 事件发往 Control Plane

## 6.2 Grep 级验收（交付前强制自检）

```bash
# ① Runtime 层无直接 1933 HTTP 调用
grep -rn "httpx.*1933\|requests.*1933\|http://.*1933\|POST.*resources\|GET.*content/read" app/main.py
# 期望：0 行

# ② memory write/query/delete 全部经过 scope enforcement
grep -rn "resolve_scope_ref\|enforce_scope\|can_write\|can_delete" app/main.py
# 期望：所有 memory 操作均出现在调用链中

# ③ 无直连 VIKING_URL 的散落 HTTP 调用
grep -rn "os.getenv.*VIKING\|config.viking_url\|config.viking_api_key" app/main.py
# 期望：仅存在于 config.py 的默认值定义，main.py 中为 0 行
```

> 任意一项不满足，视为未完成交付。
