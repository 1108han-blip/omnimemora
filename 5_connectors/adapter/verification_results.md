# Policy v1 Implementation Verification Results

**Date:** 2026-04-11
**Scope:** OmniMemora Adapter — Context Injection Policy v1
**Status:** VERIFIED AND LOCKED

---

## 一、策略目标

| 目标 | 实现 |
|------|------|
| implementation 任务默认不注入 context | ✅ 达成 |
| decision / continuation 继续走 optimize_context | ✅ 达成 |
| 无 embedding / semantic similarity / query rewrite | ✅ 达成（纯关键词规则） |
| connector/adapter 层实现任务分类与分流 | ✅ 达成 |
| 规则可解释、可观测 | ✅ 达成 |

---

## 二、验收结果

### 2.1 Implementation Bypass（核心目标）

**测试 Query:** `"write code for login function"`

| 检查项 | 期望值 | 实际值 | 状态 |
|--------|--------|--------|------|
| `task_type` | `implementation` | `implementation` | ✅ |
| `context_bypass` | `true` | `true` | ✅ |
| `matched_keywords` | 含 `"write code"` | `['write code']` | ✅ |
| `packed_context` | `""` (空字符串) | `""` | ✅ |
| `memory_tokens_injected` | `0` | `0` | ✅ |
| `tokens_saved_estimate` | `> 0` | `200` | ✅ |
| `selected_memories` | `[]` | `[]` | ✅ |
| `engine.optimize_context()` 调用次数 | `0` | `0` | ✅ |

**Short-Circuit 证据:**
```
impl query: optimize_context() call_count=0  ← NEVER called
dec query: optimize_context() call_count=1  ← called normally
```

### 2.2 Decision Path（不受影响）

**测试 Query:** `"should we use score or score_per_token for ranking"`

| 检查项 | 期望值 | 实际值 | 状态 |
|--------|--------|--------|------|
| `task_type` | `decision` | `decision` | ✅ |
| `context_bypass` | `false` | `false` | ✅ |
| `matched_keywords` | 含决策词 | `['should', 'should we']` | ✅ |
| `packed_context` | 非空 | 162 chars | ✅ |
| `memory_tokens_injected` | `> 0` | `45` | ✅ |
| `engine.optimize_context()` 调用次数 | `1` | `1` | ✅ |

### 2.3 Continuation Path（不受影响）

**测试 Query:** `"summarize current progress"`

| 检查项 | 期望值 | 实际值 | 状态 |
|--------|--------|--------|------|
| `task_type` | `continuation` | `continuation` | ✅ |
| `context_bypass` | `false` | `false` | ✅ |
| `matched_keywords` | 无通用疑问词 | `['progress', 'current']` | ✅ |

---

## 三、改动文件清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `5_connectors/adapter/task_classifier.py` | **新增** | TaskClassification + classify_task() + should_bypass_context() |
| `5_connectors/adapter/main.py` | 修改 | query_memory_v2 / internal_trial_query 增加 bypass 逻辑 |
| `4_core/logic/engine.py` | 修改 | OptimizationInput 增加 task_type/context_bypass 透传字段 |
| `4_core/logic/v2_compute.py` | 修改 | TokenSavingsMeter 增加 Policy v1 字段 |
| `5_connectors/adapter/__tests__/test_task_classifier.py` | **新增** | 分类器单元测试 |
| `5_connectors/adapter/__tests__/test_policy_v1_bypass.py` | **新增** | Bypass 验收测试 |

---

## 四、Policy v1 字段规范

### 4.1 Response 字段（Adapter → 调用方）

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_type` | `string` | `"implementation"` / `"decision"` / `"continuation"` |
| `context_bypass` | `bool` | `true` = 跳过了 optimize_context |
| `matched_keywords` | `string[]` | 触发分类的关键词列表 |

### 4.2 TokenSavingsMeter 字段（Policy v1 扩展）

| 字段 | 类型 | 说明 |
|------|------|------|
| `task_type` | `string?` | 任务分类结果 |
| `context_bypass` | `bool` | 是否 bypass |
| `bypassed_context_tokens` | `int` | 估算跳过的 token 数（仅 bypass 时 > 0） |
| `matched_keywords` | `string[]` | 触发分类的关键词 |

### 4.3 Bypass 计量逻辑

当 `context_bypass = true` 时：

```
baseline_tokens_estimate = bypassed_context_tokens  # 本该注入的
actual_tokens_estimate  = 0                         # 实际没注入
saved_tokens_estimate   = bypassed_context_tokens   # 真正省下的
savings_ratio          = 1.0                       # 100%
```

---

## 五、分类规则（已锁定）

### 优先级

1. **implementation**（最高）— 命中 IMPL_KEYWORDS 任一
2. **decision**（次之）— 命中 DECISION_KEYWORDS/DECISION_PHRASES 任一
3. **continuation**（默认）— 命中 CONTINUATION_PHRASES/CONTINUATION_INDICATORS 或默认

### 实现关键词（中文 + 英文）

```
write code, implement, create function, create class, fix bug,
refactor, build, deploy, 写代码, 实现, 修复, 重构, ...
```

### 决策关键词

```
choose, select, decide, recommend, which is better, should we,
compare, pros and cons, ...
```

### 继续关键词

```
what is the, how to, status of, progress, latest, summarize, ...
```

**注意：** 通用疑问词（what/how/why/when/where/who）不单独作为 continuation 依据。

---

## 六、架构边界（已确认）

| 规则 | 状态 |
|------|------|
| engine.py 不含 task_type 分支逻辑 | ✅ 确认 |
| 分类在 adapter 层执行 | ✅ 确认 |
| bypass 在 adapter 层执行 | ✅ 确认 |
| engine 纯透传 Policy v1 字段 | ✅ 确认 |

---

## 七、Memora Decision Log（自动生成）

每次调用后自动打印一条 JSON 日志。

**定位：** 这是 OmniMemora **服务端决策日志**，表示 adapter 做了什么判断、节省了多少。
**不是**完整的真实使用日志 — 完整日志（含用户主观评价）由 wrapper 层（memrun/ccm/ocm）补充。

### 输出位置
- 标准输出（stdout）
- 每条日志独立一行，无前缀/后缀

### 日志格式

```json
{
  "timestamp": "<ISO8601>",
  "query": "<用户原始请求，前200字符>",
  "task_type": "implementation | decision | continuation",
  "context_bypass": true | false,
  "context_stats": {
    "packed_context_length": <int>,
    "memory_tokens_injected": <int>,
    "baseline_tokens_estimate": <int>,
    "actual_tokens_estimate": <int>,
    "saved_tokens_estimate": <int>,
    "savings_ratio": <float>
  },
  "execution_feedback": null,   // ← wrapper 层填充
  "subjective_score": null,    // ← wrapper 层填充（用户反馈）
  "_meta": {
    "request_id": "<id>",
    "agent": "<agent>",
    "tenant": "<tenant>",
    "agent_id": "<agent_id>",  // 来自 API 入参，缺失时为 "unknown"
    "workspace_id": "<workspace_id>", // 来自 API 入参，缺失时为 "unknown"
    "scope": "<workspace|server>",    // 来自 API 入参，默认 "workspace"
    "matched_keywords": ["<keywords>"]
  }
}
```

### adapter 日志 vs wrapper 日志职责

| | adapter 日志 | wrapper 日志 |
|---|---|---|
| 名称 | Decision Log | Real Usage Log |
| 负责方 | OmniMemora 服务端 | memrun / ccm / ocm |
| task_type | ✅ 填写 | ✅ 可覆盖 |
| context_bypass | ✅ 填写 | ✅ 可覆盖 |
| context_stats | ✅ 填写 | ✅ 可覆盖 |
| execution_feedback | ❌ null | ✅ 真实用户行为 |
| subjective_score | ❌ null | ✅ 真实用户评价 |
| agent_id | ✅ 填写（来自 API 入参） | ✅ 可覆盖 |
| workspace_id | ✅ 填写（来自 API 入参） | ✅ 可覆盖 |
| scope | ✅ 填写（来自 API 入参） | ✅ 可覆盖 |

### 示例

**implementation bypass:**
```json
{"timestamp": "2026-04-11T04:43:20Z", "query": "write code for login function", "task_type": "implementation", "context_bypass": true, "context_stats": {"packed_context_length": 0, "memory_tokens_injected": 0, "baseline_tokens_estimate": 200, "actual_tokens_estimate": 0, "saved_tokens_estimate": 200, "savings_ratio": 1.0}, "execution_feedback": null, "subjective_score": null, "_meta": {"request_id": "req-abc123", "agent": "test-agent", "tenant": "test-tenant", "agent_id": "agent-001", "workspace_id": "ws-main", "scope": "workspace", "matched_keywords": ["write code"]}}
```

**decision (正常流程):**
```json
{"timestamp": "2026-04-11T04:43:20Z", "query": "should we use score or score_per_token", "task_type": "decision", "context_bypass": false, "context_stats": {"packed_context_length": 22, "memory_tokens_injected": 45, "baseline_tokens_estimate": 200, "actual_tokens_estimate": 45, "saved_tokens_estimate": 155, "savings_ratio": 0.775}, "execution_feedback": null, "subjective_score": null, "_meta": {"request_id": "req-def456", "agent": "test-agent", "tenant": "test-tenant", "agent_id": "agent-002", "workspace_id": "ws-main", "scope": "workspace", "matched_keywords": ["should", "should we"]}}
```

### 注入点
- `query_memory_v2` return 前
- `internal_trial_query` return 前

---

## 八、遗留项（后续迭代）

| 项 | 优先级 | 说明 |
|----|--------|------|
| continuation 边界词表扩展 | P2 | 可根据线上数据补充 |
| bypass 场景的更精确 token 估算 | P2 | 当前用 `max_local_cards * 50` 估算 |
| execution_feedback 精细化 | P2 | 当前基于启发式，后续可接 LLM 判断 |
| subjective_score 用户反馈接口 | P2 | 当前默认 true，后续接用户评价 |

---

## 九、锁定声明

本文档记录 Policy v1 最终验收状态。

**任何对分类规则、bypass 逻辑、字段定义的修改，均需更新本文档并重新通过验收测试。**

---

*验证执行：Claude Code*
*验收日期：2026-04-11*
