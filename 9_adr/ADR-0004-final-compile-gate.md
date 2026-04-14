---
doc_id: ADR-0004-FINAL-COMPILE-GATE
title: OmniMemora Final Compile Gate — Memory Tool Policy
owner: platform-team
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-13
depends_on: [ADR-0001-PRODUCT-BOUNDARY]
supersedes: []
last_verified_commit: ""
---

# ADR-0004: Final Compile Gate — OmniMemora Memory Tool Policy

**状态：** Active
**日期：** 2026-04-13
**范围：** OmniMemora MCP 工具定义与使用约束

---

## 背景

2026-04-13 工程落地明确了 OmniMemora 在 OpenClaw 环境中的角色定位：
**不是 memory 管理系统，而是 LLM 之前最终编译层（Final Compile Gate）。**

---

## 一、核心定义

### 工具角色分工

| 工具 | 角色 | 说明 |
|------|------|------|
| `memory.context` | **FINAL COMPILE TOOL** | 唯一产品能力入口。接收所有来源候选，输出 `packed_context`。**必须经过此工具才能进入 LLM。** |
| `memory.search` | **CANDIDATE RETRIEVAL TOOL** | 候选检索工具。返回原始结果，不可直接进入 LLM。必须喂给 `memory.context` 做最终编译。 |
| `memory.write` | **WRITE TOOL** | 写入工具，职责不变。 |
| `omnimemora_search_memory` | **memory.context 的别名** | 等同 FINAL COMPILE TOOL，同等约束。 |
| `omnimemora_write_memory` | **memory.write 的别名** | 等同 WRITE TOOL。 |

### 关键原则

> **禁止旁路：native memory / native compiler / session context 的输出不得绕过 `memory.context` 直接进入 LLM prompt。**

```
允许路径（正确）：
  native memory ─→ memory.context ─→ packed_context ─→ LLM

禁止路径（错误）：
  native memory ─────────────────────→ LLM（绕过 Final Compile Gate）
  memory.search ─────────────────────→ LLM（绕过 Final Compile Gate）
```

---

## 二、Final Compile Gate 数据结构

`memory.context` 输入：

```json
{
  "query": "...",
  "limit": 8,
  "native_compiled_context": "...",      // 可选：OpenClaw native compiler 输出
  "current_session_context": "...",      // 可选：当前会话上下文
  "raw_candidates": [...]                 // 可选：显式候选列表
}
```

`memory.context` 输出（通过 MCP 协议）：

```json
{
  "request_id": "mcp-xxx",
  "packed_context": "<relevant-memories>...</relevant-memories>",
  "selected_memories": [...],
  "usage": {
    "saved_tokens_estimate": 89,
    "savings_ratio": 0.645,
    "actual_tokens_estimate": 49,
    "baseline_tokens_estimate": 138
  },
  "task_type": "continuation",
  "context_bypass": false
}
```

MCP 返回格式（两个 content block）：
- Block 0（人类可读摘要）：`OmniMemora: saved N tokens (X% reduction), Y memories selected\n\n{packed_context}`
- Block 1（机器可解析 JSON）：`{"saved_tokens": N, "ratio": X, "memory_count": Y, "selected_memories": [...]}`

**重要：Block 0 中的 `text` 字段必须是字符串，不得为 dict 或其他结构。**

---

## 三、多源候选合并逻辑

`engine.optimize_context()` 在过滤前执行三源合并：

```python
merged_candidates = candidate_memories[:candidate_limit]
if native_compiled_context:
    merged_candidates.append({
        "content": native_compiled_context,
        "abstract": "[native-compiled-context]",
        "category": "native_compiled",
        "score": 0.8,
        "_source": "native_compiled",
    })
if current_session_context:
    merged_candidates.append({
        "content": current_session_context,
        "abstract": "[current-session-context]",
        "category": "session",
        "score": 0.8,
        "_source": "session",
    })
if raw_candidates:
    for rc in raw_candidates[:candidate_limit]:
        rc["_source"] = "raw_candidate"
        merged_candidates.append(rc)
```

合并后统一经过：filter → route/score → reduce redundancy → select → pack → meter

---

## 四、OpenClaw 侧约束

OpenClaw Agent 在最终提交给 LLM 前，必须满足：

1. **必须调用 `memory.context`**（或别名 `omnimemora_search_memory`）
2. **最终 prompt 中只使用 `packed_context`**
3. **禁止将 `memory.search` 结果直接拼入 LLM prompt**
4. **禁止将 native memory / native compiler 输出绕过 `memory.context` 直接注入 prompt**

验证方法：在 OpenClaw Agent 运行中，检查发送给 LLM 的完整 prompt 是否来自 `memory.context` 返回的 `packed_context` 值，且不包含其他 memory 注入。

---

## 五、验证标准（6 条）

| # | 标准 | 验证方式 |
|---|------|---------|
| 1 | `memory.context` 被调用 | `curl http://127.0.0.1:18011/metrics/summary?tenant=openclaw` 中 `request_count` 持续增长 |
| 2 | 调用经过 `/mcp/query → engine.optimize_context()` | `/mcp/query` 返回结构化 JSON 含 `packed_context` 和 `usage` |
| 3 | 最终送给 LLM 的 context 来自 `packed_context` | 需在 OpenClaw Agent 侧验证 prompt 来源 |
| 4 | `memory.search` 结果不直接进 LLM | 工具描述已标注为 `CANDIDATE RETRIEVAL TOOL` |
| 5 | MCP 返回格式合规：`content[].text` 为 string | `curl -X POST /messages -d '{"method":"tools/call","params":{"name":"memory.context"}}'` 验证 Block text 类型 |
| 6 | metrics 持续增长 | `saved_tokens`, `savings_ratio`, `request_count` 在每次请求后更新 |

---

## 六、相关文档

- [ADR-0003-interface-access-paths.md](ADR-0003-interface-access-paths.md) — 多接口单路径架构
- [ADR-0001-product-boundary-reset.md](ADR-0001-product-boundary-reset.md) — 产品边界定义
- [4_core/logic/engine.py](../4_core/logic/engine.py) — `OptimizationInput` 定义与 `optimize_context()` 实现
- [5_connectors/adapter/main.py](../../5_connectors/adapter/main.py) — MCP 端点与工具注册

---

## 七、约束优先级

1. `memory.context` = Final Compile Gate（不可绕过）
2. `memory.search` = Candidate Retrieval（不可直接进 LLM）
3. 所有多源候选通过 `engine.optimize_context()` 统一压缩
4. 输出结构（`packed_context` + `usage`）是产品合约，不可破坏

**违反以上任何一条视为产品级缺陷。**