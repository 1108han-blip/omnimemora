## Summary

<!-- What is changed? One paragraph. -->

-

## Change Set ID

<!-- Format: CHG-YYYY-MMDD-NN -->
<!-- Example: CHG-2026-0414-01 -->
CHG-2026-____-__

## 影响文档

<!-- List all doc_ids affected by this change (read: docs/standards/doc-schema.md for ID format) -->
<!-- 新增文档：doc_id: ??? -->
<!-- 修改文档：doc_id: ??? -->
<!-- 删除文档：doc_id: ??? -->

| 变更类型 | doc_id | 文档标题 |
|---------|--------|---------|
| 新增 |  |  |
| 修改 |  |  |
| 删除 |  |  |

## 是否新增/修改 ADR

- [ ] 新增 ADR（附 doc_id）
- [ ] 修改现有 ADR（附 doc_id）
- [ ] 无 ADR 变更

## Scope

<!-- Which layer does this change belong to? -->

- [ ] 0_blueprint
- [ ] 1_architecture
- [ ] 2_product
- [ ] 3_governance
- [ ] 4_core
- [ ] 5_connectors
- [ ] 6_console
- [ ] 7_docs
- [ ] 8_migrations
- [ ] 9_adr

---

## Decision Checklist

### Core 3 questions

- [ ] This change is **controlling** memory, not **storing** primary memory
- [ ] This change does not introduce required backend dependency
- [ ] This capability remains replaceable / disableable

### Hard stop check

- [ ] Does NOT make cloud store user primary memory
- [ ] Does NOT introduce `/memory/write` as core cloud capability
- [ ] Does NOT require memory backend URL
- [ ] Does NOT create centralized hosted memory service
- [ ] Does NOT strongly bind system to one storage backend

### Architecture check

- [ ] Control Plane / Memory Plane separation remains clear
- [ ] Product still works without hosted memory backend
- [ ] Connector remains lightweight
- [ ] Engine / storage / model remain replaceable

### Value check

- [ ] Improves token savings, recall quality, control capability, or measurable usage
- [ ] If none of the above, this PR should not exist

### Compatibility

<!-- 说明本次变更是否向后兼容，影响哪些接口或数据格式 -->

-

## 发布后验证步骤

<!-- 列出合入后必须执行的验证步骤（如运行测试、部署检查等） -->

1. [ ] ...
2. [ ] ...

## Codex Closeout Evidence

<!-- Fill this when Codex or another agent produced the change. Use product-local evidence only. -->

- tests: <!-- run / not run / not applicable; include command -->
- doctor: <!-- run / not run / not applicable; include make doctor or workflow link -->
- docs: <!-- updated / not needed / not run -->
- runtime evidence: <!-- run / not run / not applicable -->

Doctor quality is report-only unless a separate release gate explicitly says otherwise.

## Files Changed

<!-- List the files changed in this PR -->

-

## Acceptance Criteria

<!-- How do we verify this change works correctly? -->

-
