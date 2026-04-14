---
doc_id: GOV-PR-CHECKLIST-001
title: OmniMemora PR Checklist
owner: doc-team
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [GOV-EXECUTION-GUARDRAILS-001, GOV-REPO-BOUNDARIES-001]
supersedes: []
last_verified_commit: a1b2c3d
---

# PR_CHECKLIST.md

**Status:** FINAL
**Role:** PR 合入入口（不定义规则）

---

# 合入规则

所有 PR 必须满足：

---

## 1. Guardrails

→ 必须通过：

EXECUTION_GUARDRAILS.md

---

## 2. Blueprint Alignment

→ 必须符合：

- PRODUCT_CONSTITUTION.md
- PRODUCT_DEFINITION.md
- SYSTEM_ARCHITECTURE.md
- EXECUTION_STRATEGY.md

---

## 3. Repo Boundaries

→ 必须符合：

REPO_BOUNDARIES.md

---

## 合入决策

- 任一不满足 → REJECT
- 全部满足 → APPROVE
