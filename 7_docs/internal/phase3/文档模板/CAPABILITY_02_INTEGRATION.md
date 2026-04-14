---
doc_id: PLAN-PHASE3-CAP02-INTEGRATION
title: Phase 3 Capability 02 — Integration Simplicity
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-09
depends_on: [ADR-0001-PRODUCT-BOUNDARY, PLAN-PHASE3-OVERVIEW]
supersedes: []
last_verified_commit: ""
---

# CAPABILITY_02_INTEGRATION.md

## 3.1 目标

```text
让 Agent “无脑接入”
```

---

## 3.2 最小接入方式（核心）

```text
POST /memory/search

{
  "query": "...",
  "options": {
    "assemble_context": true
  }
}
```

---

## 3.3 默认行为（必须稳定）

```text
默认：

strategy = auto
mode = balanced
```

---

## 3.4 Phase 3 增强（允许做）

```text
1. SDK 封装（轻量）

searchWithContext(query)

2. Agent 适配指南（文档级）

- CC
- Codex
- OpenClaw
```

---

## 3.5 禁止扩展

```text
❌ 不做 Agent runtime
❌ 不接管 prompt 构建
❌ 不嵌入 Agent 内部状态
```
