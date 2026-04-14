---
doc_id: GOV-REPO-BOUNDARIES-001
title: OmniMemora Repository Directory Boundaries
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: []
supersedes: []
last_verified_commit: a1b2c3d
---

# REPO_BOUNDARIES.md

**Status:** FINAL
**Role:** 仓库目录边界定义

---

# 目录职责边界

## 0_blueprint/

**Allowed:**
- 产品定义
- 系统架构
- 执行策略
- 路线图
- 执行防火墙

**Forbidden:**
- 实现代码
- 测试代码
- UI 描述
- 用户流程

---

## 1_architecture/

**Allowed:**
- API contracts
- Interface definitions
- Data schemas
- Protocol definitions
- Technical structure

**Forbidden:**
- "OmniMemora is..."
- Product value
- System position
- Control Plane / Memory system redefinition

---

## 2_product/

**Allowed:**
- UI descriptions
- User flows
- Interaction patterns
- Usage documentation

**Forbidden:**
- Product definition
- System position
- Architecture description
- "What OmniMemora is..."

---

## 3_governance/

**Allowed:**
- Execution guardrails
- Repo boundaries
- PR checklist
- Enforcement rules

**Forbidden:**
- Product definition
- Architecture
- Implementation logic

---

## 4_core/

**Allowed:**
- Implementation logic
- Business logic
- API implementation
- Tests

**Forbidden:**
- Product behavior definition
- System role definition
- Architecture definition
- Must reference 0_blueprint only

---

## 5_connectors/

**Allowed:**
- Connector implementations
- Skill/Plugin integrations
- Platform-specific adapters

**Forbidden:**
- Product redefinition
- Core logic duplication

---

## 6_console/

**Allowed:**
- UI implementation
- Metering display
- Console features

**Forbidden:**
- Product redefinition
- Core logic

---

## 7_docs/

**Allowed:**
- User documentation
- API docs
- Violation check rules

**Forbidden:**
- Product redefinition
- Must reference 0_blueprint

---

## 8_migrations/

**Allowed:**
- Migration scripts
- Data migrations
- Schema migrations

**Forbidden:**
- Product redefinition

---

## 9_adr/

**Allowed:**
- Architecture decision records
- Technical decisions

**Forbidden:**
- Product redefinition
- Must align with 0_blueprint
