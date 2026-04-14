---
doc_id: STD-DOC-SCHEMA-001
title: OmniMemora Document Metadata Schema
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [GOV-EXECUTION-GUARDRAILS-001]
supersedes: []
last_verified_commit: a1b2c3d
---

# 标准文档元数据头（Document Metadata Header）

> 所有 OmniMemora 仓库内的 `.md` 文档**必须**以此 YAML frontmatter 开头。
> CI 门禁将检查此元数据，缺失或不合规则 PR 失败。

---

## 一、必填字段（Required Fields）

| 字段 | 类型 | 说明 |
|------|------|------|
| `doc_id` | string | 唯一文档标识，格式见下方"ID 命名规范" |
| `title` | string | 文档标题 |
| `owner` | string | 负责团队或个人 |
| `status` | enum | `draft` \| `active` \| `deprecated` \| `superseded` |
| `version` | semver | 语义化版本，如 `1.0.0` |

## 二、推荐字段（Recommended Fields）

| 字段 | 类型 | 说明 |
|------|------|------|
| `reviewers` | string[] | 需要 review 的人员/角色列表 |
| `effective_date` | date | 文档生效日期（YYYY-MM-DD） |
| `depends_on` | string[] | 依赖的其他 doc_id 列表 |
| `supersedes` | string[] | 本文档替代了哪些旧 doc_id |
| `last_verified_commit` | string | 最近一次与代码对照验证的 commit hash |

## 三、ID 命名规范（doc_id Format）

| 文档类型 | 格式 | 示例 |
|---------|------|------|
| L0 Vision/PRD | `PRD-PROJECTNAME-NNN` | `PRD-OMNIMEMORA-001` |
| L1 ADR | `ADR-NNNN-DESCRIPTION` | `ADR-0007-BACKEND-ABSTRACTION` |
| L2 Spec | `SPEC-DOMAIN-NNN` | `SPEC-BACKEND-001` |
| L3 Plan/Task | `PLAN-PHASE-NNN` | `PLAN-PHASE3-001` |
| L4 Runbook | `RUN-OPERATION-NNN` | `RUN-DEPLOY-001` |
| 标准/规范 | `STD-SCOPE-NNN` | `STD-DOC-SCHEMA-001` |

**规则：**
- `doc_id` 在整个仓库内必须唯一
- 大写 + 连字符（`ADR-0001` 不是 `adr-0001`）
- 同一主题只允许一个 canonical 文档

## 四、status 状态语义

| status | 含义 | 额外要求 |
|--------|------|---------|
| `draft` | 编辑中，尚未评审 | — |
| `active` | 已批准，当前有效 | — |
| `deprecated` | 已废弃 | **必须**同时有 `supersedes` 字段 |
| `superseded` | 被新文档替代 | 必须指向替代文档的 doc_id |

## 五、示例

```yaml
---
doc_id: ADR-0007-BACKEND-ABSTRACTION
title: Backend Abstraction Layer for Memory Backend Agnosticism
owner: team-platform
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [ADR-0001, ADR-0003]
supersedes: []
last_verified_commit: a1b2c3d
---
```

## 六、CI 检查规则（docs-governance.yml）

1. **ID 唯一性**：所有 `doc_id` 在仓库内不得重复
2. **依赖有效性**：`depends_on` 中列出的 doc_id 必须存在
3. **废弃约束**：`status: deprecated` 的文档必须有 `supersedes`
4. **链接完整性**：文档内 markdown 链接不得指向不存在的文件
5. **必填字段**：`doc_id`、`title`、`status`、`version` 不得缺失

---

**优先级**：本文档定义的元数据规范 > 任何旧文档的自定义字段。
