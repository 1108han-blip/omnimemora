---
doc_id: GOV-VIOLATION-CHECK-001
title: OmniMemora Violation Check Rules
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [GOV-EXECUTION-GUARDRAILS-001]
supersedes: []
last_verified_commit: a1b2c3d
---

# VIOLATION_CHECK.md

**Status:** FINAL
**Role:** 仓库自动刹车规则

---

# 违规检查规则

If any file outside `0_blueprint/`:

- redefines product
- introduces new system role
- conflicts with blueprint

→ MUST BE REJECTED

---

# 具体检查项

## ✅ 允许

- API contracts / interfaces / data schemas
- Implementation logic
- User flow / UI description
- Test code
- Documentation that references blueprint

---

## ❌ 禁止（触发自动拒绝）

### 产品定义类

- "OmniMemora is..."
- "What OmniMemora does..."
- "Product value..."
- "System position..."
- "Control Plane..."
- "Memory system..."

---

### 架构定义类

- Redefining system architecture
- Introducing new system layers
- Redefining scope model
- Redefining runtime architecture

---

### 边界越界类

- "We control memory..."
- "We are the memory system..."
- "This is the only path..."
- "All memory must go through..."

---

# 检查方式

All PRs must pass:
1. Manual check against this document
2. Auto grep for forbidden patterns
3. EXECUTION_GUARDRAILS.md validation

---

# 优先级

VIOLATION_CHECK > EXECUTION_GUARDRAILS > 0_blueprint/*
