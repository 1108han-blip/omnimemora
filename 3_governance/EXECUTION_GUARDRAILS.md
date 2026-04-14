---
doc_id: GOV-EXECUTION-GUARDRAILS-001
title: OmniMemora Execution Guardrails
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: []
supersedes: []
last_verified_commit: a1b2c3d
---

# EXECUTION_GUARDRAILS.md

**Status:** FINAL
**Role:** 所有实现行为的强制约束（不可绕过）

---

⚠️  **This file is the single source of truth for execution constraints.**

---

# 一、作用（必须理解）

本文件不是参考文档。

这是：

→ 所有 agent / coder / patch 的执行防火墙

---

# 二、强制规则（必须执行）

任何实现前，必须通过以下检查：

---

## 1. Boundary Check（边界检查）

是否违反以下任一条：

- 控制 memory ownership ❌
- 成为必经路径 ❌
- 引入 orchestration ❌
- 依赖云端才能运行 ❌
- 绑定 storage backend ❌

👉 任一触发 → 立即停止

---

## 2. Capability Check（能力合法性）

该功能是否：

- 提升 context 质量
- 降低 token 使用
- 提升 recall / control / metering

👉 若全部否 → 不允许实现

---

## 3. Replaceability Check（可替换性）

该能力是否：

- 可关闭
- 可替换
- 不影响系统存在

👉 否 → 不允许实现

---

## 4. Complexity Check（复杂度控制）

是否：

- 引入新系统层
- 增加跨服务依赖
- 增加状态复杂度

规则：

- 2个 yes → 重设计
- 3个 yes → 拒绝

---

## 5. Observability Check（可观测性）

必须具备：

- request_id
- tenant
- agent
- usage record

---

## 6. Final Veto（最终否决）

问：

→ 这会不会让系统看起来像 memory system？

👉 只要有一点点像 → 拒绝

---

# 三、执行方式（关键）

## 所有 coding agent 必须：

在实现前：

1. 明确列出检查结果
2. 若违反 → 停止并说明原因
3. 不允许"先做再补"

---

# 四、优先级

EXECUTION_GUARDRAILS > 所有实现文档

---

# 五、核心一句话

如果这套规则不存在：

→ 系统一定会演化成 memory server
