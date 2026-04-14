# OmniMemora Backend Abstraction Layer 开发方案

> **方案已拆解到具体文件，请参考：**
> - [BACKEND_INTERFACE.md](./backend_abstraction/BACKEND_INTERFACE.md) - 接口定义
> - [BACKEND_ADAPTER_PATTERN.md](./backend_abstraction/BACKEND_ADAPTER_PATTERN.md) - Adapter 实现模式
> - [BACKEND_FACTORY.md](./backend_abstraction/BACKEND_FACTORY.md) - Factory 接线规则
> - [MIGRATION_PLAN_1933.md](./backend_abstraction/MIGRATION_PLAN_1933.md) - 迁移执行步骤
> - [ADR-0007-backend-abstraction-layer.md](../9_adr/ADR-0007-backend-abstraction-layer.md) - 架构决策记录

---

## 0. 方案定位

本方案用于解决当前 `18011 -> 1933` 的硬编码绑定问题，建立 **Backend Abstraction Layer**，使 OmniMemora 真正满足以下产品宪法要求：

- 不依赖特定 memory backend

- 可插拔、可迁移、可兼容

- Control Plane / Memory Plane 分离

- OpenViking 可兼容，但不再是默认架构前提
    

---

# 1. 当前问题定性

## 1.1 已确认事实

当前系统现状：

- `5_connectors/adapter` 直接通过 `viking_request()` 调用 `1933`
    
- 调用协议为 OpenViking 专用 REST 语义：
    
    - `/api/v1/fs/*`
        
    - `/api/v1/resources/*`
        
    - `/api/v1/content/read`
        
    - `/api/v1/search/find`
        
- `8765` 为另一套 OmniMemora MCP/REST 服务，接口模型与 1933 不兼容
    
- 项目中不存在真正实现的：
    
    - `backends/`
        
    - `MemoryBackend` 抽象接口
        
    - `OmniMemoraMemoryBackend`
        
- 存在迁移设计文档，但未工程落地
    

## 1.2 问题本质

这不是配置错误，不是指针错误，也不是 URL 切换问题。  
这是 **缺失 backend abstraction layer 导致的主链路硬绑定问题**。

---

# 2. 目标架构

## 2.1 目标一句话

将当前 `18011` 从 **OpenViking-specific adapter** 重构为 **backend-agnostic connector**。

## 2.2 目标结构

```text
Agent / Wrapper / Client
        ↓
5_connectors/adapter
        ↓
MemoryBackend Interface
        ↓
Backend Adapter
   ├─ OpenVikingBackend (1933)
   ├─ OmniMemoraRuntimeBackend (8765)
   └─ FutureBackend (...)
```

---

# 3. 架构原则

## 3.1 必须遵守

1. Connector 不得直接依赖具体 backend 协议
    
2. Engine 不得出现 backend 细节
    
3. `viking://`、`/api/v1/fs/*`、`/api/v1/resources/*` 只能存在于 OpenViking backend adapter 内
    
4. `18011` 必须只依赖统一接口，不依赖 `1933`
    
5. 新增 backend 不允许修改 connector 业务逻辑，只允许新增 adapter 实现
    

## 3.2 禁止事项

以下目录禁止出现 OpenViking 专用语义：

- `4_core/logic/`
    
- `5_connectors/adapter/main.py`
    
- `5_connectors/adapter/*` 除 backend factory 与 backend wiring 外
    

禁止词：

- `viking_request`
    
- `viking://`
    
- `/api/v1/fs`
    
- `/api/v1/resources`
    
- `viking_url`
    

这些只能保留在：

```text
5_connectors/adapter/backends/openviking_backend.py
```

---

# 4. 开发目标拆分

## Phase A：建立抽象层骨架（必须先做）

目标：让 connector 不再直接调用 OpenViking API。

### A1. 新增目录结构

建议新增：

```text
5_connectors/adapter/
├── backends/
│   ├── __init__.py
│   ├── base.py
│   ├── factory.py
│   ├── openviking_backend.py
│   └── omnimemora_runtime_backend.py
```

### A2. 定义统一接口

在 `base.py` 中定义 `MemoryBackend` 抽象接口。

接口只保留产品真正需要的最小能力：

- `search_memory(...)`
    
- `write_memory(...)`
    
- `read_memory(...)`（如当前链路实际需要）
    
- `healthcheck()`
    

### A3. 统一入参/出参模型

新增 backend-neutral 的数据对象，例如：

- `MemorySearchRequest`
    
- `MemorySearchResult`
    
- `MemoryWriteRequest`
    
- `MemoryRecord`
    

要求：

- 不出现 `viking://`
    
- 不出现文件路径概念
    
- 不出现 OpenViking resource API 字段
    
- 不出现 MCP 工具特有字段
    

统一以“memory record / content / scope / metadata”建模

---

## Phase B：实现 OpenViking backend adapter（兼容旧链路）

目标：先把旧能力装进接口里，保证行为不变。

### B1. 把现有 `viking_request()` 相关逻辑迁入

新建：

```text
backends/openviking_backend.py
```

职责：

- 封装所有对 `1933` 的 HTTP 调用
    
- 处理：
    
    - `/api/v1/fs/*`
        
    - `/api/v1/resources/*`
        
    - `/api/v1/content/read`
        
    - `/api/v1/search/find`
        
- 对外只暴露 `MemoryBackend` 接口语义
    

### B2. connector 中移除直接调用

把当前 `main.py` 中所有直接调用 `viking_request()` 的逻辑改为：

```python
backend = get_memory_backend(config)
backend.search_memory(...)
backend.write_memory(...)
```

### B3. 保证行为等价

此阶段不改变对外 API 行为，不改变当前查询结果，不改变 token savings 逻辑，只做“依赖收口”。

---

## Phase C：实现 OmniMemora runtime backend（8765）

目标：让 8765 首次成为可挂接 backend，而不是旁路服务。

### C1. 新建 runtime backend

```text
backends/omnimemora_runtime_backend.py
```

职责：

- 封装对 `8765` 的 `/memory/*` 或 MCP/REST 接口调用
    
- 实现与 `MemoryBackend` 统一对齐的：
    
    - `search_memory`
        
    - `write_memory`
        
    - `read_memory`（如可行）
        

### C2. 数据映射

完成两类映射：

#### 统一请求 → 8765 请求

例如：

- query → keyword
    
- scope → runtime scope
    
- limit → runtime limit
    

#### 8765 响应 → 统一结果

例如：

- runtime memory item → `MemoryRecord`
    

### C3. 明确限制

如果 `8765` 暂不支持某些能力：

- 不要在 connector 内写兼容脏逻辑
    
- 直接在 backend 内做：
    
    - 显式降级
        
    - 显式报错
        
    - 显式 TODO 注释
        

原则：**能力差异只能留在 backend adapter 内，不得外溢到 connector**

---

## Phase D：引入 backend factory + 配置切换

目标：让 backend 成为配置项，而不是硬编码。

### D1. 新配置项

在 `config.py` 中新增：

- `memory_backend_type`
    
    - `openviking`
        
    - `omnimemora_runtime`
        

新增：

- `memory_backend_base_url`
    

兼容期允许保留：

- `viking_url`
    

但必须标记：

- deprecated
    
- 仅供 `openviking` backend 使用
    

### D2. backend factory

在 `factory.py` 中实现：

```python
get_memory_backend(config) -> MemoryBackend
```

逻辑：

- `openviking` → `OpenVikingBackend`
    
- `omnimemora_runtime` → `OmniMemoraRuntimeBackend`
    

### D3. 健康检查输出修正

`/health` 返回值不再暴露：

- `viking_url`
    
- `viking_connected`
    

替换为通用字段：

- `memory_backend_type`
    
- `memory_backend_base_url`
    
- `memory_backend_connected`
    

---

# 5. 代码改造范围

## 5.1 必改文件

### `5_connectors/adapter/main.py`

目标：

- 删除直接 `viking_request()` 依赖
    
- 所有 memory search / write / read 逻辑统一走 backend interface
    
- 不出现 OpenViking 特有路径和协议
    

### `5_connectors/adapter/config.py`

目标：

- 引入 backend-neutral 配置
    
- 将 `viking_url` 降级为兼容字段
    
- 增加 backend type 配置
    

### `5_connectors/adapter/backends/base.py`

新增抽象类和中立数据结构

### `5_connectors/adapter/backends/openviking_backend.py`

封装旧链路全部实现

### `5_connectors/adapter/backends/omnimemora_runtime_backend.py`

新增 8765 对接实现

### `5_connectors/adapter/backends/factory.py`

backend 实例创建

---

# 6. 具体执行步骤（Claude Code 可按序执行）

## Step 1

创建 `backends/` 目录与基础文件：

- `base.py`
    
- `factory.py`
    
- `openviking_backend.py`
    
- `omnimemora_runtime_backend.py`
    

## Step 2

在 `base.py` 中定义：

- `MemoryBackend` ABC
    
- backend-neutral request/response dataclass
    

## Step 3

把 `main.py` 中所有 `viking_request()` 的直接调用点逐一收集，整理为调用清单：

- 搜索调用
    
- 写入调用
    
- 内容读取调用
    
- 目录/资源操作调用
    

## Step 4

实现 `OpenVikingBackend`：

- 将现有调用逻辑迁移进去
    
- 保持现有行为一致
    
- 在 adapter 外部不再暴露 OpenViking 协议细节
    

## Step 5

修改 `main.py`：

- 统一通过 `backend = get_memory_backend(config)` 获取 backend
    
- 所有 memory 相关逻辑改用 backend 接口
    
- 删除直接协议调用
    

## Step 6

修改 `config.py`：

- 增加 `memory_backend_type`
    
- 增加 `memory_backend_base_url`
    
- 将 `viking_url` 改为 deprecated compatibility field
    

## Step 7

实现 `OmniMemoraRuntimeBackend`：

- 先对接最小闭环能力：
    
    - search
        
    - write
        
- 如 read 不可用，先做显式 NotImplemented 或受控降级
    

## Step 8

扩展 `/health`：

- 输出 backend-neutral 健康状态
    
- 不再输出 OpenViking 专属字段
    

## Step 9

增加测试：

- OpenViking backend 单测
    
- Runtime backend 单测
    
- factory 单测
    
- connector 集成测试
    

## Step 10

完成“无污染检查”：

在非 `openviking_backend.py` 文件中 grep 以下关键词并清零：

- `viking`
    
- `viking://`
    
- `/api/v1/fs`
    
- `/api/v1/resources`
    
- `/api/v1/search/find`
    

---

# 7. 测试要求

## 7.1 单元测试

### OpenVikingBackend

验证：

- search request 正确映射到 `/api/v1/search/find`
    
- write request 正确写入资源
    
- 错误码处理正确
    
- healthcheck 正常
    

### OmniMemoraRuntimeBackend

验证：

- search request 正确映射到 `/memory/search` 或 MCP 接口
    
- write request 正确映射
    
- 返回结果正确转成统一模型
    
- 不支持能力的报错符合预期
    

### Factory

验证：

- backend type 正确选择
    
- 配置缺失时报错合理
    

---

## 7.2 集成测试

至少覆盖两组：

### 组 1：openviking backend

链路：

```text
18011 -> OpenVikingBackend -> 1933
```

验证：

- `/memory/query` 正常
    
- `/memory/write` 正常
    
- token savings 流程不回归
    

### 组 2：omnimemora_runtime backend

链路：

```text
18011 -> OmniMemoraRuntimeBackend -> 8765
```

验证：

- `/memory/query` 至少跑通最小闭环
    
- `/memory/write` 至少跑通最小闭环
    
- 健康检查正确显示 backend 类型
    

---

# 8. 验收标准

以下条件全部满足，才算完成：

## 8.1 架构验收

- `main.py` 不再直接调用 `viking_request()`
    
- `18011` 不再硬编码绑定 `1933`
    
- connector 仅依赖 `MemoryBackend` 接口
    

## 8.2 兼容验收

- OpenViking 作为 backend 仍可运行
    
- 不破坏当前旧链路能力
    

## 8.3 新链路验收

- 8765 可作为 backend 挂接
    
- 至少 search/write 最小闭环成立
    

## 8.4 去污染验收

除 `openviking_backend.py` 外，其余核心代码中不再出现：

- `viking://`
    
- `/api/v1/fs/*`
    
- `/api/v1/resources/*`
    
- `viking_request`
    

## 8.5 宪法一致性验收

实现结果符合：

- 不依赖特定 backend
    
- backend 可替换
    
- OpenViking 变为兼容插件，不再是系统前提
    

---

# 9. 风险与规避

## 风险 1：把抽象层做成“薄包装”

表现：

- 接口虽然存在，但参数仍然充满 OpenViking 语义
    

规避：

- 接口模型必须采用 memory record / scope / content 语义
    
- 不允许 URI / 文件树概念进入抽象层
    

## 风险 2：connector 中残留协议分支

表现：

- `if backend_type == "openviking": ...`
    

规避：

- backend 差异必须封装在 adapter 内
    
- connector 只调统一接口
    

## 风险 3：8765 能力不足导致 connector 污染

规避：

- 能力缺失在 runtime backend 内做降级，不在 connector 内补丁
    

## 风险 4：兼容层永久化

规避：

- OpenViking backend 保留，但其地位明确为 optional compatibility backend
    
- 不再允许其语义进入产品主路径
    

---

# 10. 推荐交付顺序

## 第一批交付（P0）

- Backend interface
    
- OpenVikingBackend
    
- Factory
    
- main.py 改造
    
- config 改造
    
- 旧链路跑通
    

## 第二批交付（P1）

- OmniMemoraRuntimeBackend
    
- 8765 search/write 闭环
    
- health 输出统一
    

## 第三批交付（P2）

- 清理 deprecated 字段
    
- 补文档
    
- 加 lint / grep 守卫，防止 OpenViking 语义再次污染核心层
    

---

# 11. 最终决策

本次开发不以“删除 OpenViking”为目标。  
本次开发的唯一目标是：

> **将 OpenViking 从默认硬依赖降级为兼容 backend，实现真正的 Backend Abstraction Layer，使 OmniMemora 成为 backend-agnostic 的 Control Plane。**

---

# 12. 给 Claude Code 的执行指令

请按以下顺序执行，不要跳步：

1. 创建 `backends/` 目录与基础抽象
    
2. 实现 `MemoryBackend` ABC 与统一数据模型
    
3. 将 `main.py` 中所有直接 `viking_request()` 调用迁入 `OpenVikingBackend`
    
4. 在 `main.py` 中改为只通过 backend factory 获取 backend
    
5. 新增 backend-neutral 配置项
    
6. 实现 `OmniMemoraRuntimeBackend`
    
7. 修正 `/health` 输出
    
8. 增加单元测试与集成测试
    
9. 对核心目录做 OpenViking 污染 grep 清理
    
10. 输出最终变更说明：哪些文件新增、哪些函数迁移、哪些遗留项仍待处理
    

执行要求：

- 先保证旧链路不回归
    
- 再接入 8765
    
- 不得在 connector/core 中继续扩散 OpenViking 协议细节
    
- 所有 backend 差异必须收敛在 `backends/` 内