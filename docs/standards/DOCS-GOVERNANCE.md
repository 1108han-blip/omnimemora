---
doc_id: STD-DOCS-GOVERNANCE-001
title: OmniMemora Documentation Governance Framework
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [STD-DOC-SCHEMA-001, GOV-EXECUTION-GUARDRAILS-001]
supersedes: []
last_verified_commit: ""
---

# OmniMemora 文档治理框架

> **生效日期：** 2026-04-14  
> **主控文件**：`docs/standards/DOCS-GOVERNANCE.md`（本文档）  
> **配套文件**：`docs/standards/doc-schema.md`（元数据规范）、`docs/adr/ADR-TEMPLATE.md`、`docs/spec/SPEC-TEMPLATE.md`

---

## 一、文档分层架构

```
L0  Vision/PRD        → 0_blueprint/          产品目标、边界、非目标（唯一权威）
L1  ADR               → 9_adr/                 关键技术决策与取舍（唯一决策真相源）
L2  Spec              → docs/spec/             接口、状态机、数据模型、异常语义
L3  Plan/Task         → 7_docs/internal/phase* 实施计划、里程碑、验收标准
L4  Runbook           → 7_docs/internal/phase4 部署、回滚、告警、应急
```

**层级规则：**
- 上层可引用下层，下层**不得**反向定义上层
- 同一主题仅一个 canonical 文档，禁止重复定义
- 所有文档的 `doc_id` 命名必须遵循 `STD-DOC-SCHEMA-001`

---

## 二、元数据头规范（强制要求）

### 2.1 标准 YAML frontmatter

所有文档**必须**在文件开头包含：

```yaml
---
doc_id: <类型>-<域>-<序号>     # 必填，唯一标识
title: <标题>                  # 必填
owner: <团队|个人>             # 必填
reviewers: [<角色1>, ...]      # 推荐
status: draft|active|deprecated|superseded  # 必填
version: <semver>              # 必填，如 1.0.0
effective_date: YYYY-MM-DD     # 推荐
depends_on: [<doc_id>, ...]   # 推荐
supersedes: [<doc_id>, ...]    # deprecated 时必填
last_verified_commit: <hash>  # 推荐
---
```

### 2.2 双轨迁移策略（存量 vs 增量）

| 场景 | 要求 |
|------|------|
| **新增文档** | 必须带完整 YAML frontmatter，CI 强制检查 |
| **变更已有文档** | 必须同步更新 frontmatter 的 `version`、`effective_date` |
| **存量文档**（无 frontmatter） | 分批渐进补齐，不阻塞开发流；由 owner 负责在 next PR 中顺带补充 |
| **archive/ 目录** | 存量归档文档无需补充元数据，但新归档文件须保留原有 frontmatter |

**原因**：一次性全量整改会卡住所有开发迭代。双轨策略保证新变更不漂移，存量渐进收敛。

---

## 三、ADR 编号策略

### 3.1 编号分配规则

- ADR 编号**永久独占**，不得复用已废弃编号
- 同一编号不得分配给两个不同文档（P0 级违规，CI 强制检查）
- ADR 编号按时间顺序递增（0001 → 0002 → ...）

### 3.2 编号冲突处理（如本次修复）

**当前场景（2026-04-14 修正）：**

| 修正前 | 修正后 | 说明 |
|--------|--------|------|
| ADR-0003（backend-abstraction） | → `ADR-0007-BACKEND-ABSTRACTION` | 分配新编号 |
| ADR-0003（interface-access-paths） | → 保留为 `ADR-0003-INTERFACE-ACCESS-PATHS` | interface-access-paths 被更多文档引用，保留原编号 |
| `ADR-0002-cloud-refactor.md.md` | → `ADR-0002-CLOUD-REFACTOR.md` | 修复双后缀文件名 |

**引用维护原则：**
- 编号变更后，所有引用方应随变更顺带更新
- 若某文档引用的 ADR 编号已变更但自身未在本次 PR 中修改，owner 应在**下次触碰该文件时**一并更新
- 不得因"引用未更新"而阻止编号修复（CI 不因历史引用报错）

### 3.3 废弃与替代

```yaml
# 被替代的 ADR 在 frontmatter 中：
status: deprecated
supersedes: [ADR-XXXX-NEW-DOC-ID]   # 必填，指向替代文档
```

---

## 四、CI 门禁分级上线

CI 门禁采用**先 warn 后 block** 渐进策略，降低初期误杀风险。

### 4.1 上线阶段

| 阶段 | 触发 | 检查项 | 行为 |
|------|------|--------|------|
| **Phase 0**（Day 1-7） | PR 中 .md 变化 | 全部 4 项 | `warn` — 记录日志，不阻止合入 |
| **Phase 1**（Day 8+） | PR 中 .md 变化 | 全部 4 项 | `block` — 不满足则合入失败 |
| **滚动豁免** | 持续 | 豁免列表内的 exempt 文件 | 不检查 |

### 4.2 CI 检查项与失败条件

```
检查项               | 失败条件                        | exempt
--------------------|--------------------------------|--------
doc_id 唯一性        | 同一 doc_id 出现 > 1 个文件      | archive/, node_modules/
depends_on 有效性    | depends_on 的 doc_id 不存在     | —
deprecated 有 supersedes | status=deprecated 但无 supersedes | —
链接完整性           | markdown 链接指向不存在文件       | archive/, node_modules/
```

### 4.3 Phase 0 观测期规则

Phase 0 期间（warn 模式）：
- CI 在 PR 中输出检查结果为 comment，不阻止合入
- 若发现 P0 级问题（doc_id 重复），在 comment 中标注 `[@agent](需要人工确认)`
- 所有 warn 应在 Phase 1 切换前清零

### 4.4 CI 工具链

```
.github/workflows/
├── docs-governance.yml     # 主工作流（warn/block 切换）
├── check_doc_ids.py        # doc_id 唯一性（frontmatter only）
├── check_depends_on.py     # depends_on 引用有效性
├── check_deprecated.py     # deprecated 约束
├── check_metadata.py       # 必填字段
└── check_links.py          # 链接完整性
```

---

## 五、冲突裁决规则（Agent 执行标准）

当多个文档对同一事实或规则有**相互矛盾的描述**时，按以下优先级裁决：

### 5.1 权威层级（Authority Level）

```
第1优先级  权威层级（Layer）
  L0 0_blueprint/          > L1 9_adr/ > L2 docs/spec/ > L3 > L4
  上层文档的描述 > 下层文档的描述

第2优先级  状态（Status）
  active  >  draft  >  deprecated  >  superseded
  当前有效版本优先于历史版本

第3优先级  supersedes 关系
  有 supersedes 记录的文档  >  无 supersedes 的同名文档

第4优先级  时间（Time）
  effective_date 更近的版本  >  更旧的版本

第5优先级  可验证性（Verifiability）
  有 last_verified_commit 的文档  >  无 last_verified_commit 的文档
```

### 5.2 Agent 输出格式要求

当 Agent 发现或引发文档冲突时，**必须**在响应中包含以下结构：

```markdown
## 文档冲突分析

### 采用依据
<说明采用了哪份文档的描述，依据上述哪条优先级>

### 被拒绝的候选
| 候选文档 | 冲突内容 | 拒绝原因（优先级依据）|
|---------|---------|----------------------|
| <doc_id> | <冲突描述> | <依据第X优先级拒绝> |

### 待人工确认项
- [ ] <具体问题1，需人工判断>
- [ ] <具体问题2，需人工判断>
```

### 5.3 强制升级条件

以下情况**不得**由 Agent 自行裁决，必须上报人工：

1. 冲突涉及产品边界（`0_blueprint/` vs 其他层）
2. 冲突涉及安全或合规条款
3. 裁决结果会导致某文档从 `active` 变为 `deprecated`
4. 被拒绝的候选文档中有 `active` 状态的文档

---

## 六、PR 联动要求

所有涉及代码变更的 PR，必须同步更新关联文档。PR 模板见 `.github/pull_request_template.md`。

### 6.1 强制填写字段

| 字段 | 说明 |
|------|------|
| **Change Set ID** | `CHG-YYYY-MMDD-NN` 格式，变更集唯一标识 |
| **影响文档** | 列出所有受影响的 doc_id（新增/修改/删除）|
| **是否新增/修改 ADR** | 必须明确 |
| **兼容性说明** | 向后兼容 or 不兼容 + 影响范围 |
| **发布后验证步骤** | 合入后必须执行的验证项 |

### 6.2 No Doc, No Merge

- 若 PR 包含代码变更但**未更新相关 ADR/Spec**，PR 模板中"是否新增/修改 ADR"填写为"无"，则 CI 检查失败
- 若代码变更涉及接口语义（API/状态机/数据模型）但相关 Spec 未更新，CI 失败

---

## 七、一致性指标与 SLO

| 指标 | 计算方式 | SLO 目标 |
|------|---------|---------|
| Doc-Code Alignment Rate | 有 doc_id 且 frontmatter 与代码一致的变更占比 | ≥ 95%（Phase 1 上线后 30 天内达到 98%） |
| Stale Doc Age | 文档距最近 `last_verified_commit` 的天数 | ≤ 60 天 |
| Orphan Doc Rate | 无 owner 或无 `depends_on` 引用的 active 文档占比 | ≤ 5% |
| Contradiction MTTR | 发现文档冲突到修复完成的平均时长 | ≤ 3 个工作日 |

---

## 八、反熵机制

| 节奏 | 机制 | 输出物 |
|------|------|--------|
| 每迭代 | Doc Drift Review（30 分钟固定会议）| 更新 `last_verified_commit`，标记 drift 项 |
| 每月 | Documentation Debt Cleanup | 清理 orphan 文档，更新过期引用 |
| 每季度 | 基线重建 | 创建 `docs/baselines/vX.Y` 快照，合并冲突定义 |

---

## 九、文件速查

| 用途 | 文件路径 |
|------|---------|
| 元数据规范 | `docs/standards/doc-schema.md` |
| ADR 模板 | `docs/adr/ADR-TEMPLATE.md` |
| Spec 模板 | `docs/spec/SPEC-TEMPLATE.md` |
| **本文档（主治理文件）** | `docs/standards/DOCS-GOVERNANCE.md` |
| PR 模板 | `.github/pull_request_template.md` |
| CI 工作流 | `.github/workflows/docs-governance.yml` |
| 本地检查脚本 | `tools/docs/consistency-check.ps1` |

---

**治理层级**：DOCS-GOVERNANCE.md > doc-schema.md > 其他所有文档标准。
