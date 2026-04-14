---
doc_id: BASELINE-v0.2
title: OmniMemora Baseline Snapshot v0.2 (Phase 3-4 + Governance)
owner: doc-team
reviewers: [arch-lead]
status: active
version: 0.2.0
effective_date: 2026-04-14
depends_on: []
supersedes: [BASELINE-v0.1]
last_verified_commit: ""
---

# docs/baselines/v0.2 — Phase 3-4 + 治理体系基线快照

**创建日期：** 2026-04-14
**快照目的：** 记录文档治理体系建立后的基线状态

## 快照内容

### 治理核心文档（新建）

| doc_id | 文档 | 说明 |
|--------|------|------|
| STD-DOC-SCHEMA-001 | docs/standards/doc-schema.md | 元数据规范 |
| STD-DOCS-GOVERNANCE-001 | docs/standards/DOCS-GOVERNANCE.md | 治理主文档 |
| STD-DOCS-GOVERNANCE-001 | docs/standards/DOCS-GOVERNANCE.md | 治理主文档 |
| SPEC-BACKEND-ABSTRACTION-001 | docs/spec/SPEC-BACKEND-ABSTRACTION-001.md | Canonical Spec |

### ADR（全部有 doc_id）

| doc_id | 文档 | 版本 |
|--------|------|------|
| ADR-0001-PRODUCT-BOUNDARY | ADR-0001-product-boundary-reset.md | 1.0.0 |
| ADR-0002-CLOUD-REFACTOR | ADR-0002-cloud-refactor.md | 1.0.0 |
| ADR-0003-INTERFACE-ACCESS-PATHS | ADR-0003-interface-access-paths.md | 1.1.0 |
| ADR-0004-FINAL-COMPILE-GATE | ADR-0004-final-compile-gate.md | 1.0.0 |
| ADR-0005-AGENT-IDENTITY | ADR-0005-agent-identity-fields.md | 1.0.0 |
| ADR-0006-INTERNAL-TRANSPORT | ADR-0006-internal-transport.md | 1.0.0 |
| ADR-0007-BACKEND-ABSTRACTION | ADR-0007-backend-abstraction-layer.md | 1.0.0 |

### Phase Plan 文档（部分有 doc_id）

| doc_id | 文档 |
|--------|------|
| PLAN-PHASE3-OVERVIEW | 7_docs/internal/phase3/文档模板/PHASE3_OVERVIEW.md |
| PLAN-PHASE3-CAP01-OBSERVABILITY | 7_docs/internal/phase3/文档模板/CAPABILITY_01_OBSERVABILITY.md |
| PLAN-PHASE3-CAP02-INTEGRATION | 7_docs/internal/phase3/文档模板/CAPABILITY_02_INTEGRATION.md |
| PLAN-PHASE3-CAP03-STABILITY | 7_docs/internal/phase3/文档模板/CAPABILITY_03_STABILITY.md |
| PLAN-PHASE3-METRICS | 7_docs/internal/phase3/文档模板/METRICS.md |
| PLAN-PHASE4-STATUS | 7_docs/internal/phase4/PHASE4_STATUS.md |
| PLAN-PHASE5-CLOUD-ENGINEERING | 7_docs/internal/phase5/plan/云端小工程.md |

## CI 检查基线

| 检查项 | 基线状态 |
|--------|---------|
| doc_id 唯一性 | 16 docs with frontmatter, 0 duplicates |
| depends_on 有效性 | 0 broken refs |
| deprecated 约束 | PASS |
| 链接完整性 | 165 docs, 0 broken links |
| 元数据必填字段 | 16/16 PASS |

## 重要决策记录

1. **2026-04-14** — 建立文档治理体系（governance framework）
2. **2026-04-14** — 整合 Backend Abstraction 分散文档为 canonical SPEC
3. **2026-04-14** — ADR 编号冲突修复（0003 → 0003 + 0007）
