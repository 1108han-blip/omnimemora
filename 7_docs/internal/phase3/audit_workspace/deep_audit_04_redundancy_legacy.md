# OmniMemora 深度审计 - 04 冗余与历史包袱

**审计日期**: 2026-04-13  
**状态**: 进行中

---

## 一、重复实现检查

### 1.1 Query Path 重复

| 实现 | 位置 | 状态 | 说明 |
|------|------|------|------|
| Python Engine | `4_core/logic/engine.py` | ✅ 主链 | 唯一产品能力入口 |
| Python Adapter | `5_connectors/adapter/main.py` | ✅ 主链 | 当前默认查询路径 |
| Go Runtime | `4_core/local-runtime/` | ✅ 主链 | 支持 `/memory/query` |
| Adapter Raw (v2.3) | `4_core/adapter-raw/` | ⚠️ 历史 | 旧版适配器，未在主链 |

**结论**: ✅ **无重复主链实现** - 路径清晰，无混乱

---

### 1.2 Write Path 重复

| 实现 | 位置 | 状态 | 说明 |
|------|------|------|------|
| Python Adapter | `5_connectors/adapter/main.py` | ✅ 主链 | 当前默认写入路径 |
| Go Runtime | `4_core/local-runtime/` | ✅ 主链 | 支持 `/memory/write` |
| Adapter Raw (v2.3) | `4_core/adapter-raw/` | ⚠️ 历史 | 旧版适配器，未在主链 |

**结论**: ✅ **无重复主链实现**

---

### 1.3 Metering 口径重复

| 口径 | 位置 | 状态 | 说明 |
|------|------|------|------|
| TokenSavingsMeter | `4_core/logic/v2_compute.py` | ✅ 主链 | 唯一计量定义 |
| meter_store.py | `5_connectors/adapter/meter_store.py` | ✅ 主链 | 唯一持久化层 |

**结论**: ✅ **无口径不一致** - 已在阶段 1-2 修复

---

## 二、历史兼容残留检查

### 2.1 Adapter Raw (v2.3)

**位置**: `4_core/adapter-raw/`

**状态**: ⚠️ **历史残留，但未在主链**

**检查项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 是否被主链依赖 | ❌ 否 | 独立 git 子模块 |
| 是否被新逻辑依赖 | ❌ 否 | 主链使用 `5_connectors/adapter/` |
| 是否有明确废弃标记 | ✅ 是 | README 说明是旧版 |
| 是否有切流说明 | ✅ 是 | 主链已迁移到 Python Adapter |

**结论**: ⚠️ **可接受** - 历史残留，有明确标记，未在主链

---

### 2.2 OpenViking Backend (1933)

**位置**: `5_connectors/adapter/backends/openviking_backend.py`

**状态**: ✅ **兼容性层，有明确边界**

**检查项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 是否被主链依赖 | ❌ 否 | 默认 backend 是 `omnimemora_runtime` |
| 是否有抽象层隔离 | ✅ 是 | 通过 `MemoryBackend` 接口 |
| 是否有明确切流说明 | ✅ 是 | 配置项 `MEMORY_BACKEND_TYPE` |
| OpenViking 协议是否泄漏 | ✅ 否 | 仅在 `openviking_backend.py` 内 |

**结论**: ✅ **合规** - 兼容性层，有抽象隔离，未泄漏

---

### 2.3 Policy v1 Bypass 逻辑

**位置**: `5_connectors/adapter/main.py` ~2000-2070 行

**状态**: ✅ **当前功能，非历史残留**

**检查项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 是否在产品路线图 | ✅ 是 | Phase 3 功能 |
| 是否有明确文档 | ✅ 是 | Constitution/Strategy 说明 |
| 是否与主链集成 | ✅ 是 | 在 query 路径最前面 |

**结论**: ✅ **当前功能** - 不是历史残留

---

## 三、壳层越权检查

### 3.1 Adapter 层越权

**位置**: `5_connectors/adapter/main.py`

**检查项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 是否内嵌产品决策逻辑 | ❌ 否 | 决策逻辑在 `engine.py` |
| 是否重复 engine 规则判断 | ❌ 否 | Policy v1 是独立 bypass 逻辑 |
| 是否仅做接入/鉴权/组装/持久化 | ✅ 是 | FastAPI 路由、后端调用、meter 存储 |

**结论**: ✅ **合规** - 壳层边界清晰，未越权

---

### 3.2 逻辑层污染

**位置**: `4_core/logic/engine.py`

**检查项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 是否 import httpx/fastapi/requests | ❌ 否 | 无 HTTP 依赖 |
| 是否 import os/glob/open | ❌ 否 | 无文件 I/O |
| 是否 import config | ❌ 否 | 无配置读取 |
| 是否读写文件 | ❌ 否 | 纯函数 |
| 是否引用 `__file__` | ❌ 否 | 无路径依赖 |

**结论**: ✅ **合规** - 逻辑层未被污染

---

## 四、双轨逻辑检查

### 4.1 Engine vs Runtime

| 职责 | Engine | Runtime | 边界清晰度 |
|------|--------|---------|-----------|
| Context 优化决策 | ✅ | ❌ | ✅ 清晰 |
| Memory 存储执行 | ❌ | ✅ | ✅ 清晰 |
| Meter 计算 | ✅ | ❌ | ✅ 清晰 |
| Meter 持久化 | ❌ | ✅ | ✅ 清晰 |
| API 暴露 | ❌ | ✅ | ✅ 清晰 |

**结论**: ✅ **无边界混淆** - Control Plane / Memory Plane 分离清晰

---

## 五、冗余代码与历史残留清单

| 模块 | 问题类型 | 是否主链 | 建议动作 | 优先级 |
|------|---------|---------|---------|-------|
| `4_core/adapter-raw/` | 历史残留 | 否 | 保留归档 | P2 |
| `4_core/adapter-raw/` | 旧版本 | 否 | 标注"历史" | P2 |

**结论**: ✅ **无严重冗余/历史包袱** - 仅有旧版 adapter 归档，未在主链

---

## 六、可维护性与演进风险

### 6.1 主调用链可追踪性

| 检查项 | 状态 | 说明 |
|-------|------|------|
| Request ID 贯穿 | ✅ | `X-Request-ID` header + state |
| Tenant/User 贯穿 | ✅ | `resolve_query_access()` + ScopeRef |
| Meter 绑定 ScopeRef | ✅ | Meter artifact 包含完整身份 |
| Decision Log 输出 | ✅ | stdout JSON 日志 |

**结论**: ✅ **可追踪性良好**

---

### 6.2 错误处理统一性

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 统一异常类型 | ✅ | `SupportAPIError` |
| 统一错误目录 | ✅ | `SUPPORT_ERROR_CATALOG` |
| 统一响应格式 | ✅ | `MemoryResponse` + support payload |

**结论**: ✅ **错误处理统一**

---

### 6.3 配置集中性

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 配置单例 | ✅ | `config.py` 集中管理 |
| 环境变量映射 | ✅ | `config.py` 读取 env |
| 无散落配置 | ✅ | 无 hardcode 配置 |

**结论**: ✅ **配置集中**

---

### 6.4 模块耦合度

| 检查项 | 状态 | 说明 |
|-------|------|------|
| Engine 无外部依赖 | ✅ | 纯逻辑，参数注入 |
| Adapter 仅依赖接口 | ✅ | `MemoryBackend` ABC |
| Backend 可替换 | ✅ | Factory 模式 |
| Store 可替换 | ✅ | Go Runtime 有 Store 抽象 |

**结论**: ✅ **耦合度低，可替换性强**

---

### 6.5 隐性单点

| 检查项 | 状态 | 说明 |
|-------|------|------|
| 无隐性单点 | ✅ | 所有依赖可配置 |
| Backend 可切换 | ✅ | `MEMORY_BACKEND_TYPE` |
| Runtime 可替换 | ✅ | 仅通过 API 交互 |

**结论**: ✅ **无隐性单点**

---

## 七、冗余与历史包袱审计总结

| 类别 | 发现数 | 严重程度 |
|------|--------|---------|
| 重复路径 | 0 | - |
| 历史残留 | 1 | P2 |
| 壳层越权 | 0 | - |
| 逻辑层污染 | 0 | - |
| 双轨逻辑 | 0 | - |

**总体结论**: ✅ **无严重冗余/历史包袱** - 代码库健康

---

## 下一步

进行最终审计汇总，输出完整深度审计报告
