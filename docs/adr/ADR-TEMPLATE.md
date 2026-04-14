---
doc_id: ADR-NNNN-SLUG
title: <Title>
owner: <team-name>
reviewers: [arch-lead, qa-lead]
status: active
version: 0.1.0
effective_date: YYYY-MM-DD
depends_on: []
supersedes: []
last_verified_commit: ""
---

# ADR-NNNN: <Title>

**状态：** `{{STATUS}}`（Active/Accepted/Deprecated/Superseded）
**日期：** YYYY-MM-DD
**范围：** <What this ADR covers>

---

## 0. Summary（执行摘要）

> 一句话说明这个决策是什么，以及为什么重要。
> 审查者应能在30秒内理解核心意图。

---

## 1. Context（背景）

### 当前状态
<描述当前系统状态、技术或产品环境>

### 问题
<描述这个问题或痛点，为什么现在需要做这个决定>

### 约束
<有哪些限制条件（技术、业务、时间、资源）>

---

## 2. Decision（决策）

### 选择
<明确说明做了什么决定>

### 替代方案（Alternatives Considered）

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 方案A | ... | ... | 未选 |
| 方案B | ... | ... | **选中** |

---

## 3. Consequences（后果）

### 正面
- ...

### 负面
- ...

### 兼容性说明
<如果涉及接口变更，说明兼容性影响>

---

## 4. Change Log（变更记录）

| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|---------|--------|
| 1.0.0 | YYYY-MM-DD | 初始版本 | name |

---

## 5. 关联文档

- 依赖：`depends_on: [...]`
- 被替代：无
- 关联 L2 Spec：`<spec doc_id>`

---

## 6. Review Checklist

- [ ] 上下文充分，决策依据清晰
- [ ] 替代方案评估了至少2个选项
- [ ] 后果（正/负）均已说明
- [ ] 与现有 ADR 无冲突
- [ ] owner 和 reviewers 已确认
