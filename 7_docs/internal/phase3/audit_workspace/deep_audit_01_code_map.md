# OmniMemora 深度审计 - 01 代码地图

**审计日期**: 2026-04-13  
**状态**: 进行中

---

## 一、仓库真实结构

| 模块/目录 | 真实职责 | 入口文件 | 出口/依赖 | 是否主链 |
|---------|---------|---------|----------|---------|
| `0_blueprint/` | 产品宪法/定义/架构 | `PRODUCT_CONSTITUTION.md` | 所有实现必须遵守 | - |
| `4_core/logic/` | 纯逻辑引擎 | `engine.py` | 无 I/O，纯函数 | ✅ 主链 |
| `4_core/local-runtime/` | Go Runtime | `main.go` | API 服务 + SQLite | ✅ 主链 |
| `5_connectors/adapter/` | Python FastAPI 适配器 | `main.py` | 后端抽象 + 路由 | ✅ 主链 |
| `5_connectors/adapter/backends/` | 后端实现 | `base.py`, `factory.py` | OpenViking / Runtime | ✅ 主链 |

---

## 二、API 入口盘点

### 查询路径 (`/memory/query`)

| 层级 | 文件 | 函数 | 职责 |
|-----|------|------|------|
| API 入口 | `adapter/main.py` | `query_memory_v2()` | 接收请求、鉴权、Policy v1 |
| 后端抽象 | `adapter/backends/base.py` | `MemoryBackend.search()` | 搜索接口 |
| 后端实现 | `adapter/backends/omnimemora_runtime_backend.py` | 调用 Runtime 8765 | 获取候选记忆 |
| 逻辑引擎 | `logic/engine.py` | `optimize_context()` | 纯逻辑优化 |
| 计量存储 | `adapter/meter_store.py` | `store_meter()` | 持久化 meter artifact |

### 写入路径 (`/memory/write`)

| 层级 | 文件 | 函数 | 职责 |
|-----|------|------|------|
| API 入口 | `adapter/main.py` | `write_memory()` | 接收请求、限流、鉴权 |
| 后端抽象 | `adapter/backends/base.py` | `MemoryBackend.write()` | 写入接口 |
| 后端实现 | `adapter/backends/omnimemora_runtime_backend.py` | 调用 Runtime 8765 | 写入记忆 |

### 计量聚合路径

| 层级 | 文件 | 函数 | 职责 |
|-----|------|------|------|
| API 入口 | `adapter/main.py` | `get_meter()`, `get_trend_data()` | 查询接口 |
| 计量存储 | `adapter/meter_store.py` | `get_meter()`, `get_trend_data()` | 从 SQLite 读取 |

---

## 三、主调用链梳理

### 链 1: `/memory/query` 完整路径

```
1. adapter/main.py: query_memory_v2()
   ├─ Policy v1: classify_task() / should_bypass_context()
   ├─ Backend: get_memory_backend().search()
   │  └─ omnimemora_runtime_backend.py: POST http://127.0.0.1:8765/memory/search
   ├─ Engine: optimize_context(OptimizationInput)
   │  ├─ filter_with_score()
   │  ├─ calculate_memory_score_detailed()
   │  ├─ (去重)
   │  ├─ select top-k
   │  ├─ build_packed_context()
   │  ├─ token savings compute
   │  └─ generate_meter_artifact()
   ├─ Meter Store: store_meter(meter_artifact)
   └─ emit_decision_log() (stdout)
```

**关键发现**:
- ✅ Engine 确实是纯逻辑（无 I/O）
- ✅ 所有外部数据通过 `OptimizationInput` 注入
- ✅ Meter artifact 由 adapter 层持久化

---

### 链 2: `/memory/write` 完整路径

```
1. adapter/main.py: write_memory()
   ├─ RateLimiter.is_allowed()
   ├─ should_store() + filter_with_score()
   ├─ check_duplicate()
   ├─ route_memory_type_and_level()
   ├─ Backend: get_memory_backend().write()
   │  └─ omnimemora_runtime_backend.py: POST http://127.0.0.1:8765/memory/write
   └─ (注意: write 路径不产生 token savings meter)
```

---

### 链 3: Metering 聚合路径

```
1. adapter/main.py: get_meter(), get_trend_data()
   └─ meter_store.py: get_meter(), get_trend_data()
       └─ SQLite 查询（从 omnimemora.db 读取）
```

**关键发现**:
- ✅ Meter 数据持久化在 SQLite
- ✅ 支持按 user/workspace/agent/scope 聚合
- ✅ 符合宪法要求

---

## 四、核心模块职责确认

### `4_core/logic/` - 纯逻辑引擎验证

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 无 I/O | ✅ | 无 `open()`, `httpx`, `requests` |
| 无环境变量读取 | ✅ | 无 `os.getenv()` |
| 无配置读取 | ✅ | 所有规则通过参数注入 |
| 无 HTTP 请求 | ✅ | 纯函数 |
| 可独立单元测试 | ✅ | 无需 mock |

**结论**: ✅ 符合宪法"纯逻辑层"要求

---

### `5_connectors/adapter/` - 壳层验证

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 只做接入/鉴权/组装/持久化 | ✅ | FastAPI 路由、后端调用、meter 存储 |
| 未内嵌产品决策逻辑 | ✅ | 决策逻辑在 engine.py |
| 未重复 engine 的规则判断 | ✅ | Policy v1 是独立的 bypass 逻辑 |

**结论**: ✅ 符合宪法"壳层边界"要求

---

## 五、Scope 治理确认

| 路径 | Scope Enforcement | 位置 |
|-----|------------------|------|
| `/memory/write` | ✅ | `resolve_query_access()` + backend 写入时 |
| `/memory/query` | ✅ | `resolve_query_access()` + backend 搜索时 |
| `/memory/search` | ✅ | `resolve_query_access()` |
| Metering | ✅ | Meter artifact 绑定 ScopeRef |

**结论**: ✅ Scope 治理在正确层执行

---

## 六、产品边界初步检查

| 宪法条款 | 代码现状 | 结论 |
|---------|---------|------|
| 不接管 memory ownership | ✅ 仅作为可选层 | ✅ 合规 |
| 不成为 required gateway | ✅ Agent 可跳过 | ✅ 合规 |
| 不演化成 orchestration | ✅ 仅优化 context | ✅ 合规 |
| 不做主 storage | ✅ Storage 在 Runtime | ✅ 合规 |
| 仅对已召回结果选择压缩 | ✅ Engine 只优化候选 | ✅ 合规 |

**初步结论**: ✅ 产品边界未明显违规

---

## 下一步

继续进行：
1. **第二步**: 跑通主调用链的详细验证
2. **第三步**: 文档-代码对照审计
3. **第四步**: 冗余与历史包袱审计
