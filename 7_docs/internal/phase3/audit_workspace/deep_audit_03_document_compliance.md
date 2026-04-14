# OmniMemora 深度审计 - 03 文档-代码对照

**审计日期**: 2026-04-13  
**状态**: 进行中

---

## 对照审计原则

**宪法优先级**: EXECUTION_GUARDRAILS > CONSTITUTION > DEFINITION > ARCHITECTURE > STRATEGY > ROADMAP

---

## 一、产品宪法对照

### 1.1 非接管原则（最重要）

**宪法条款**:
> OmniMemora 不接管 Agent 的 memory ownership
> - 不替代 Agent 原生 memory
> - 不作为主 memory storage
> - 不要求 Agent 迁移其 memory 系统
> - 仅作为 memory augmentation layer 存在

**代码验证**:

| 验证项 | 代码位置 | 状态 | 说明 |
|-------|---------|------|------|
| Agent 可跳过 | `adapter/main.py` | ✅ | Policy v1 bypass 支持跳过 context |
| 不做主 storage | `local-runtime/` | ✅ | Storage 仅在 Runtime，不在 Control Plane |
| 可选增强层 | README.md | ✅ | 明确标注为 "optional context optimization layer" |

**结论**: ✅ **合规** - 未发现接管迹象

---

### 1.2 弱侵入原则

**宪法条款**:
> OmniMemora 必须以"可选增强组件"存在
> - Agent 可不接入 OmniMemora 正常运行
> - OmniMemora 不得成为 Agent 必经路径
> - 接入成本必须最小化

**代码验证**:

| 验证项 | 代码位置 | 状态 | 说明 |
|-------|---------|------|------|
| Optional call | README.md | ✅ | 明确标注为 "(optional call)" |
| 单 API 接入 | `adapter/main.py` | ✅ | 仅 `/memory/query` 和 `/memory/write` 两个核心 API |
| 轻量调用 | `engine.py` | ✅ | 单次函数调用 `optimize_context()` |

**结论**: ✅ **合规** - 弱侵入原则得到遵守

---

### 1.3 单能力原则（极关键）

**宪法条款**:
> OmniMemora 只解决一个核心问题：
> → 提升 context 质量
> → 降低 token 使用
> 
> 所有功能必须直接服务于 token savings 或 context optimization

**代码验证**:

| 验证项 | 代码位置 | 状态 | 说明 |
|-------|---------|------|------|
| 核心能力: dedup | `logic/dedup.py` | ✅ | 直接服务于 token savings |
| 核心能力: ranking | `logic/router.py` | ✅ | 直接服务于 context optimization |
| 核心能力: compression | `logic/v2_compute.py` | ✅ | `build_packed_context()` |
| 核心能力: token savings | `logic/v2_compute.py` | ✅ | `TokenSavingsMeter` 完整计量 |
| 无越界功能 | 全局扫描 | ✅ | 未发现 orchestration/query understanding |

**结论**: ✅ **合规** - 所有能力直接服务于 token savings / context optimization

---

### 1.4 Context Strategy Boundary

**宪法条款**:
> OmniMemora 不得演化为：
> - query understanding system
> - retrieval pipeline（多阶段）
> - orchestration layer
> - adaptive learning system
> 
> Context Strategy 仅允许：
> → 对已召回结果进行选择与压缩

**代码验证**:

| 验证项 | 代码位置 | 状态 | 说明 |
|-------|---------|------|------|
| 无 query understanding | `adapter/main.py` | ✅ | Policy v1 仅简单关键词匹配，非理解 |
| 无多阶段召回 | `adapter/main.py` | ✅ | 仅单次调用 backend.search() |
| 无 orchestration | 全局扫描 | ✅ | 未发现 workflow/plan 相关代码 |
| 仅优化已召回结果 | `logic/engine.py` | ✅ | 输入是 `candidate_memories`，输出是选择+压缩 |

**结论**: ✅ **合规** - Context Strategy Boundary 未被突破

---

### 1.5 LLM Context Exposure Boundary

**宪法条款**:
> LLM 输入必须满足最小暴露：
> - 仅交付最终 context 结果
> - 不暴露候选集与淘汰过程
> - 不暴露评分细节与策略参数
> - 不暴露 control plane 内部元信息

**代码验证**:

| 验证项 | 代码位置 | 状态 | 说明 |
|-------|---------|------|------|
| 仅交付最终 context | `logic/engine.py` | ✅ | 输出 `packed_context` 是最终结果 |
| 不暴露候选集 | `adapter/main.py` | ✅ | Response 仅返回 `selected_memories` |
| 不暴露评分细节 | `adapter/main.py` | ✅ | Response 仅返回最终 score，不暴露中间过程 |
| 不暴露 control plane 元信息 | `adapter/main.py` | ✅ | Decision Log 仅 stdout，不进入 LLM |

**结论**: ✅ **合规** - LLM Context Exposure Boundary 得到遵守

---

## 二、技术架构映射对照

### 2.1 纯逻辑层约束

**技术映射要求**:
> `4_core/logic/engine.py` 不能 import http/file/config
> 所有数据通过参数注入

**代码验证**:

| 验证项 | 代码位置 | 状态 | 说明 |
|-------|---------|------|------|
| 无 I/O import | `logic/engine.py` | ✅ | 无 `open()`, `httpx`, `requests` |
| 无环境变量读取 | `logic/engine.py` | ✅ | 无 `os.getenv()` |
| 无配置读取 | `logic/engine.py` | ✅ | 无 `config` import |
| 所有数据参数注入 | `logic/engine.py` | ✅ | `OptimizationInput` 包含所有外部数据 |
| 可独立单元测试 | `logic/engine.py` | ✅ | 无需 mock HTTP/文件 |

**结论**: ✅ **合规** - 纯逻辑层约束得到严格遵守

---

### 2.2 壳层边界

**技术映射要求**:
> `5_connectors/adapter` 只能做接入、认证、后端调用、组装输入、持久化 meter
> 不能承载产品决策逻辑

**代码验证**:

| 验证项 | 代码位置 | 状态 | 说明 |
|-------|---------|------|------|
| 仅做接入/鉴权 | `adapter/main.py` | ✅ | FastAPI 路由、CORS、请求 ID |
| 仅做后端调用 | `adapter/backends/` | ✅ | 通过 `MemoryBackend` 接口 |
| 仅做组装输入 | `adapter/main.py` | ✅ | 组装 `OptimizationInput` |
| 仅做持久化 meter | `adapter/meter_store.py` | ✅ | SQLite 存储 meter artifact |
| 无产品决策逻辑 | `adapter/main.py` | ✅ | 决策逻辑在 `engine.py` |

**结论**: ✅ **合规** - 壳层边界清晰

---

## 三、文档一致性差异清单

| 编号 | 文档条款 | 代码现状 | 差异类型 | 严重级别 |
|-----|---------|---------|---------|---------|
| - | 未发现语义冲突 | - | - | - |

**结论**: ✅ **无文档一致性冲突**

---

## 四、架构风险分级报告

### P0 风险（违反产品宪法）

**数量**: 0

---

### P1 风险（分层错位/双轨并存）

**数量**: 0

---

### P2 风险（冗余/命名混乱/测试缺失）

**数量**: 0（审计阶段 1-2 已修复）

---

## 五、文档对照审计总结

| 宪法条款 | 合规状态 |
|---------|---------|
| 非接管原则 | ✅ 合规 |
| 弱侵入原则 | ✅ 合规 |
| 单能力原则 | ✅ 合规 |
| Context Strategy Boundary | ✅ 合规 |
| LLM Context Exposure Boundary | ✅ 合规 |
| 纯逻辑层约束 | ✅ 合规 |
| 壳层边界 | ✅ 合规 |

**总体结论**: ✅ **代码与文档完全一致，未发现违规**

---

## 下一步

继续进行：
1. **第四步**: 冗余与历史包袱审计
