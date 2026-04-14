---
doc_id: PLAN-PHASE3-METRICS
title: Phase 3 Metrics Definition
owner: doc-team
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-09
depends_on: [ADR-0001-PRODUCT-BOUNDARY, PLAN-PHASE3-OVERVIEW]
supersedes: []
last_verified_commit: ""
---

# METRICS.md

## 6.1 核心指标

```text
Token Efficiency

= saved_tokens / raw_tokens
```

---

## 6.2 Strategy 指标

```text
- usage %
- avg saved_tokens
- avg compression_ratio
```

---

## 6.3 系统指标

```text
- P95 latency
- error rate
- assembly success rate
```

---

## 6.4 禁止指标

```text
❌ "模型理解能力"
❌ "query 意图识别率"
```
