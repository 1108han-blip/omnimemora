
---
doc_id: DIR-ADR-README
title: 9_adr Architecture Decision Records Directory
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [STD-DOC-SCHEMA-001]
supersedes: []
last_verified_commit: "9e6f4ea"
effective_date: 2026-04-22
---

# 9_adr/ - 架构决策记录

**Purpose:** Architecture Decision Records - 所有重要的架构和产品决策

## 职责

- 产品边界决策
- 技术选型决策
- 架构变更决策
- 重要取舍记录

## 文件

- `ADR-0001-product-boundary-reset.md` - 产品边界重置
- `ADR-0002-cloud-refactor.md` - 云端重构（已修复文件名）
- `ADR-0004-final-compile-gate.md` - Final Compile Gate 工具策略
- `ADR-0005-agent-identity-fields.md` - Agent Identity 字段规范
- `ADR-0006-internal-transport.md` - 内部直连传递规范
- `ADR-0007-backend-abstraction-layer.md` - Backend 抽象层
- `ADR-0008-skill-suggestion-boundary.md` - Skill Suggestion advisory 边界
- `ADR-0003-interface-access-paths.md` - 多接入接口架构原则
- `ADR-PROJECT-CONVENTIONS.md` - 工程约定
- `README.md` - 本文档

## 治理规则

- 所有重要决策必须记录为 ADR
- ADR 必须包含上下文、决策、后果
- ADR 编号递增，永不复用
- 所有 ADR 必须遵循 `docs/standards/doc-schema.md` 元数据规范
