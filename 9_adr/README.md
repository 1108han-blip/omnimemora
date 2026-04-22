---
doc_id: DIR-ADR-README
title: 9_adr Architecture Decision Records Directory
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.1.0
effective_date: 2026-04-22
depends_on: [STD-DOC-SCHEMA-001]
supersedes: []
last_verified_commit: ""
---

# 9_adr/ - 架构决策记录

Purpose: Architecture Decision Records（重要架构与产品决策）。

## Active ADRs

- `ADR-0002-cloud-refactor.md` - Cloudflare/Railway/Local 职责重置
- `ADR-0003-interface-access-paths.md` - 多接入单产品路径
- `ADR-0004-final-compile-gate.md` - Final Compile Gate 策略边界
- `ADR-0005-agent-identity-fields.md` - Agent Identity 字段规范
- `ADR-0006-internal-transport.md` - 内部直连传递规范
- `ADR-PROJECT-CONVENTIONS.md` - 工程约定

## Historical ADRs (Superseded)

- `ADR-0001-product-boundary-reset.md`
- `ADR-0007-backend-abstraction-layer.md`

## Notes

- ADR 编号递增，不复用。
- superseded ADR 可保留实现历史，但不得作为当前产品入口口径。
