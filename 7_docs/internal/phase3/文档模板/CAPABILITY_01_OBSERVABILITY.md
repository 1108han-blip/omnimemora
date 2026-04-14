---
doc_id: PLAN-PHASE3-CAP01-OBSERVABILITY
title: Phase 3 Capability 01 — Observability
owner: doc-team
reviewers: [arch-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-09
depends_on: [ADR-0001-PRODUCT-BOUNDARY, PLAN-PHASE3-OVERVIEW]
supersedes: []
last_verified_commit: ""
---

# CAPABILITY_01_OBSERVABILITY.md

## 2.1 目标

```text
让用户“看见”token savings 和策略效果
```

---

## 2.2 当前已有数据（直接引用）

```text
- raw_tokens
- compressed_tokens
- saved_tokens
- assembled_hits
- strategy_effectiveness
```

---

## 2.3 Phase 3 新增（只允许 UI/统计）

```text
1. 每次 search 返回 summary：

{
  "context_summary": {
    "strategy": "...",
    "saved_tokens": ...,
    "compression_ratio": ...
  }
}

2. 聚合统计（按 strategy）

- avg saved_tokens
- avg compression_ratio
- usage frequency
```

---

## 2.4 禁止扩展

```text
❌ 不引入策略学习
❌ 不动态调整 strategy
❌ 不引入 ranking feedback
```
