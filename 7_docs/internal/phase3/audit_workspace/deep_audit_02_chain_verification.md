# OmniMemora 深度审计 - 02 主调用链验证

**审计日期**: 2026-04-13  
**状态**: 进行中

---

## 链 1: `/memory/query` 详细验证

### 1.1 接收请求与鉴权

**位置**: `adapter/main.py` ~2000-2050 行

**验证项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| Policy v1 任务分类 | ✅ | `should_bypass_context()` 在调用 engine 之前 |
| Scope 解析 | ✅ | `resolve_query_access()` 正确执行 |
| 配额获取 | ✅ | 从 meter_store 获取 `current_usage` |

**关键发现**:
- ✅ Policy v1 bypass 逻辑正确：implementation task 跳过 engine
- ✅ Context bypass 时创建 synthetic meter artifact

---

### 1.2 获取候选记忆

**位置**: `adapter/main.py` ~2050-2070 行

**验证项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| Backend 抽象 | ✅ | 通过 `MemoryBackend.search()` 接口 |
| 默认后端 | ✅ | `omnimemora_runtime` (8765 端口) |
| 候选数量 | ✅ | `max_local_cards * 2` |

**关键发现**:
- ✅ 候选从 Runtime 8765 获取，不是从 OpenViking 1933
- ✅ Backend 抽象层工作正常

---

### 1.3 调用 Engine 优化

**位置**: `adapter/main.py` ~2070-2090 行 + `logic/engine.py`

**验证项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| OptimizationInput 组装 | ✅ | 所有数据从外部注入 |
| Engine 纯逻辑 | ✅ | 无 I/O，无配置读取 |
| Filter 阶段 | ✅ | `filter_with_score()` |
| Route/Score 阶段 | ✅ | `calculate_memory_score_detailed()` |
| 去重阶段 | ✅ | inline 去重（已修复 `dedup_applied`）|
| Select top-k | ✅ | `max_local_cards` |
| Pack context | ✅ | `build_packed_context()` |
| Token savings | ✅ | 已修复 baseline 计算 |
| Meter artifact | ✅ | `TokenSavingsMeter` 完整 |
| Quota check | ✅ | `check_quota_enforcement()` |

**关键发现**:
- ✅ Engine 确实是纯逻辑层，符合宪法要求
- ✅ 所有外部依赖（filter_rules, routing_rules, candidate_memories）通过参数注入
- ✅ Token savings 计算已修复（avg_chars × candidate_limit）
- ✅ `dedup_applied` 动态计算（len(scored) != len(scored_without_dup)）

---

### 1.4 Meter 持久化

**位置**: `adapter/main.py` ~2100-2120 行 + `adapter/meter_store.py`

**验证项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| store_meter() 调用 | ✅ | meter artifact 被持久化 |
| SQLite 存储 | ✅ | 存入 `omnimemora.db` |
| ScopeRef 绑定 | ✅ | Meter 绑定 tenant/user/agent/scope |
| Decision Log 输出 | ✅ | stdout 打印 JSON |

**关键发现**:
- ✅ Meter 完整持久化，支持后续聚合
- ✅ Decision Log 符合"服务端决策日志"要求

---

### 1.5 返回响应

**位置**: `adapter/main.py` ~2120-2150 行

**验证项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| Response 组装 | ✅ | `selected_memories`, `packed_context`, `meter_artifact` |
| Policy v1 字段 | ✅ | `task_type`, `context_bypass`, `matched_keywords` |
| Observability | ✅ | 完整可观测 |

---

## 链 2: `/memory/write` 详细验证

### 2.1 限流与过滤

**位置**: `adapter/main.py` ~1500-1550 行

**验证项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| RateLimiter | ✅ | 滑动窗口限流 |
| should_store() | ✅ | 内容长度、类型过滤 |
| filter_with_score() | ✅ | 评分过滤 |
| check_duplicate() | ✅ | 去重检查 |

---

### 2.2 路由与后端写入

**位置**: `adapter/main.py` ~1550-1600 行

**验证项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| route_memory_type_and_level() | ✅ | 决定记忆类型/等级 |
| MemoryBackend.write() | ✅ | 后端抽象写入 |
| Runtime 8765 | ✅ | 默认写入本地 Runtime |

**关键发现**:
- ⚠️ Write 路径**不产生 token savings meter**（这是设计，不是 bug）

---

## 链 3: Metering 聚合详细验证

### 3.1 读取路径

**位置**: `adapter/main.py` ~2200-2250 行 + `meter_store.py`

**验证项**:

| 检查项 | 状态 | 说明 |
|-------|------|------|
| get_meter() | ✅ | 按 tenant/user/agent/scope 查询 |
| get_trend_data() | ✅ | 趋势数据聚合 |
| SQLite 查询 | ✅ | 从 `meter_store` 表读取 |

**关键发现**:
- ✅ 聚合维度完整：user/workspace/agent/scope
- ✅ 符合宪法"token savings 展示"要求

---

## 主调用链验证总结

| 链 | 状态 | 说明 |
|-----|------|------|
| `/memory/query` | ✅ 完整验证 | 所有环节符合预期 |
| `/memory/write` | ✅ 完整验证 | 所有环节符合预期 |
| Metering 聚合 | ✅ 完整验证 | 所有环节符合预期 |

**关键正面发现**:
1. ✅ Engine 确实是纯逻辑层（无 I/O、无配置读取）
2. ✅ Adapter 确实只是壳层（无产品决策逻辑）
3. ✅ Policy v1 bypass 逻辑正确（在调用 engine 之前）
4. ✅ Token savings 计算已修复（avg_chars × candidate_limit）
5. ✅ `dedup_applied` 动态计算
6. ✅ Meter 完整持久化，支持聚合
7. ✅ Scope 治理在正确层执行

**暂未发现违规**:
- 未发现越界 retrieval pipeline
- 未发现越界 query understanding
- 未发现越界 orchestration
- 未发现产品漂移

---

## 下一步

继续进行：
1. **第三步**: 文档-代码对照审计
2. **第四步**: 冗余与历史包袱审计
