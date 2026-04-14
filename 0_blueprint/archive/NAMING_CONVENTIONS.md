
# NAMING_CONVENTIONS.md

**Status:** SEED  
**Owner:** 春光  
**Last Updated:** 2026-04-08  
**Supersedes:** 所有旧命名规范

---

## 文件命名规范

所有文件统一使用以下格式：

```
YYYY-MM-DD_[domain]_[type]_[title].md
```

### 示例

```
2026-04-08_architecture_current_cloud-control-plane.md
2026-04-08_product_constitution_omnimemora.md
2026-04-08_plan_current_phase-1-cloud-refactor.md
2026-03-30_archive_plan_p1-policy-externalization.md
2026-04-05_reference_local-architecture_pre-cloud.md
```

---

## Type 字段取值

| Type | 说明 |
|------|------|
| `current` | 当前有效文件 |
| `seed` | 母本层文件（宪法、路线图等） |
| `reference` | 参考文件 |
| `archive` | 归档文件 |

---

## Domain 字段取值

| Domain | 说明 |
|--------|------|
| `product` | 产品相关 |
| `architecture` | 架构相关 |
| `plan` | 计划相关 |
| `api` | API 相关 |
| `deployment` | 部署相关 |

---

## 文件头元数据

每个新文档开头必须包含：

```markdown
Status: CURRENT / SEED / REFERENCE / ARCHIVE
Owner: 春光
Last Updated: YYYY-MM-DD
Supersedes: [旧文件]
Superseded By: [新文件]
```

---

## 禁止的命名

- ❌ v1, v2, v3 等版本后缀
- ❌ final, revised, 修改后, 最新版, 真最终版 等修饰词
- ❌ 重复的版本化文件
- ❌ 旧命名体系（OpenViking 等）

---

## 版本治理

- 本文档是命名规范的最高权威
- 所有新文件必须遵循本规范
- 变更本文档需经过正式评审
