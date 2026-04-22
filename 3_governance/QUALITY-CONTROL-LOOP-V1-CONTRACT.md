---
doc_id: GOV-QC-LOOP-V1-2026-04-22
title: Local-First Quality Control Loop V1 — Governance Contract
owner: qc-team
status: active
version: 1.1.0
effective_date: 2026-04-22
scope: Phase 5 增强线 — 上下文层质量控制闭环
classification: internal enhancement line (not roadmap phase)
---

# Local-First Quality Control Loop V1 — Governance Contract

## 概述

V1 在 `Phase 5` 终态基线之上建立受控增强线，专注上下文层质量验证。

**定位**: 非产品阶段，不修改 roadmap，不改默认用户 UI。

**比较路径**: V1 采用**离线确定性比较**（offline deterministic comparison），不切在线 adapter，不新增 live override，不启动第二实例。

---

## 核心原则

1. **本地优先**: adapter 始终读本地 active 版本，云端 policy/flags 是非主路径
2. **人工 promotion**: candidate 通过评测后才允许切换 active
3. **离线比较**: V1 golden runner 直接加载 active/candidate 两版本，对自包含 fixture 跑本地优化链路，不调用 /compile
4. **证据分离**: repo reality、running reality、evidence layer 分离
5. **可验证闭环**: 上下文层质量 gate 可执行、可迭代

---

## 工件类型及职责

| 工件 | 位置 | 职责 |
|------|------|------|
| Golden Case 集 | `tools/verification/quality_control/golden_cases/` | 自包含 fixture，定义 must_pass/scored gates |
| 真实使用反馈日志 | `tools/usage_logs.jsonl` | wrapper 写入，包含 execution_feedback、policy_version |
| 评测报告 | `tools/verification/quality_control/reports/` | offline runner 输出，JSON 格式 |
| Promotion 记录 | `5_connectors/adapter/config/policies/manifest.json` | active_version、candidate_version、last_verified_report、last_promoted_at |

---

## 策略版本管理

### 目录结构

```
5_connectors/adapter/config/policies/
├── manifest.json           # 策略清单
├── local-default-v1.json   # Active 策略文件
└── [candidate-vN].json     # Candidate 策略文件（可选）
```

### Manifest 字段

```json
{
  "active_version": "local-default-v1",
  "candidate_version": null,
  "last_verified_report": null,
  "last_promoted_at": null
}
```

### 加载优先级

1. `manifest.json` → `active_version` → `{version}.json`
2. 若 manifest 或 version 文件缺失，回退到 `config/default_policy.json`
3. **V1: 云端 policy 不能覆盖本地 active 选择**

### 唯一写 last_promoted_at 的路径

`promote_candidate()` 是唯一设置 `last_promoted_at` 的函数。`record_verification()` 只更新 `last_verified_report`，不改变 `active_version`。

---

## Golden Case 格式 (V1 自包含 Fixture)

```json
{
  "case_id": "gc-001",
  "gate_class": "must_pass | scored",
  "query": "用户查询内容",
  "candidate_memories": [
    {"memory_id": "mem-001", "uri": "path/file.md", "category": "code", "content": "实际内容", "term": "内容片段"}
  ],
  "agent": "claude_code",
  "client": "test-client",
  "max_local_cards": 10,
  "candidate_limit": 10,
  "expected_task_type": "implementation | decision | continuation | ...",
  "expected_context_bypass": true | false,
  "required_memory_refs_or_terms": ["memory_id", "uri", "category", "content term"],
  "forbidden_memory_refs_or_terms": [],
  "min_selected": 1,
  "max_selected": 6
}
```

### 断言字段说明

- `task_type`: 从 query 关键词推导或使用 expected_task_type
- `context_bypass`: 基于选择结果和 min_selected 判断
- `selected_memories`: 根据策略权重对 candidate_memories 打分后选择
- `required/forbidden_memory_refs_or_terms`: 匹配 memory_id、uri、category、或 content/term

### Gate 类别

- **must_pass**: 必须全部通过，否则 promotion blocked
- **scored**: 加分项，candidate 总分不得低于 active

---

## Offline Comparison Runner

### 流程

1. 加载 manifest，获取 active_version 和 candidate_version
2. 加载 active 和 candidate 两版本策略
3. 对每个 golden case，自包含 fixture 的 candidate_memories 应用策略选择逻辑
4. 比较两版本的：task_type、context_bypass、selected_memories、selection_count
5. 聚合 must_pass 通过率和 scored 总分
6. 保存 comparison report，更新 `manifest.last_verified_report`

### Promotion Gate 规则

| 条件 | 结果 |
|------|------|
| active 的 must_pass 有任何失败 | **baseline invalid**，promotion blocked |
| candidate 的 must_pass 有任何失败 | **promotion blocked** |
| candidate.total_score < active.total_score | **promotion blocked** |
| candidate 全部 must_pass 通过 AND scored ≥ active | **promotion allowed** |

### 报告结构

```json
{
  "report_id": "cmp-20260422...",
  "timestamp": "...",
  "evaluated_active_version": "local-default-v1",
  "evaluated_candidate_version": null,
  "active_report": {
    "policy_version": "local-default-v1",
    "must_pass_cases": 2,
    "must_pass_passed": 2,
    "scored_cases": 2,
    "scored_passed": 1,
    "total_score": 2.5,
    "all_must_pass_passed": true,
    "baseline_invalid": false
  },
  "candidate_report": null,
  "promotion_allowed": true,
  "blocked_reason": null
}
```

---

## Wrapper Feedback 规范

### 执行反馈枚举

```python
execution_feedback: "better" | "same" | "worse" | "failed" | "unknown"
```

### 主观评分

```python
subjective_score: 1..5 | null
```

### 必需字段

每条 wrapper usage log 必须包含:
- `execution_feedback` (枚举校验)
- `subjective_score` (1-5 或 null)
- `policy_version` (处理此请求的策略版本)

### policy_version 来源

adapter 的上下文层响应必须包含 `policy_version` 字段，由实际生效策略返回。memrun.py 透传给 `emit_real_usage_log()`。

---

## 内部读面 (Diagnostics CLI)

路径: `tools/verification/quality_control/diagnostics.py`

汇总:
- 当前 active policy 和 manifest 状态
- last_verified_report 指向的报告（优先）或最新报告
- 近期 wrapper 反馈分布（按 policy_version 聚合）
- Promotion 就绪状态（四项 gate 检查）

### Promotion Readiness 判定

| Gate | 检查 |
|------|------|
| 1 | candidate_version 存在 |
| 2 | last_verified_report 存在 |
| 3 | 报告的 evaluated_candidate_version == 当前 candidate |
| 4 | 报告的 promotion_allowed == true |

---

## 边界约束

- V1 不做自动学习
- V1 不做自动 promotion
- V1 不做云端策略下发主路径
- V1 golden runner 不调用 /compile，不依赖在线 adapter
- 硬 gate 只验证上下文层质量，不验证最终模型回答层
- `implementation -> bypass=true` 是当前正确产品语义，V1 不修改此行为

---

## 验收标准

- [x] 只有 active、没有 candidate 时能产出 baseline 报告
- [x] candidate 全部通过 must_pass 且 scored 不回退时 promotion allowed
- [x] candidate 任何 must_pass 失败时 promotion blocked
- [x] cloud enabled 配置下仍以本地 active manifest 为唯一生效策略源
- [x] 测试只操作临时路径，不污染仓库 manifest.json
- [x] 只有 promote_candidate() 设置 last_promoted_at
- [x] record_verification() 只更新 last_verified_report，不改变 active_version
