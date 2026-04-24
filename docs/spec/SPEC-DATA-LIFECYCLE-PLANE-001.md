---
doc_id: SPEC-DATA-LIFECYCLE-PLANE-001
title: Data Lifecycle Plane - Categories, Boundaries, Maintenance and Gates
owner: product-arch
reviewers: [arch-lead, qa-lead, sre-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - ADR-DLP-001
supersedes: []
last_verified_commit: ""
---

# SPEC-DATA-LIFECYCLE-PLANE-001: Data Lifecycle Plane

**状态：** `Active`
**接口版本：** 1.0
**所属 ADR：** `ADR-DLP-001`

---

## 0. Summary

定义 OmniMemora 内部 Data Lifecycle Plane 的数据类别、生命周期阶段、模块边界、维护策略与验收 gate，确保长期运行下的性能与追溯能力可持续。

---

## 1. 产品边界与对象

### 1.1 三类数据面

| 数据面 | 示例 | 生命周期治理责任 |
|--------|------|------------------|
| 用户端记忆（Client Memory） | Claude Code / OpenClaw / Codex / plugin / skill 本地记忆 | 不在本 spec 治理范围 |
| OmniMemora 产品记忆（Product Memory） | 产品路径中的可用记忆内容 | 第一阶段仅标注边界，不做删除策略 |
| 运行证据与遥测（Evidence/Telemetry） | telemetry、evidence、meter、trace、summary、maintenance state | 本 spec 第一治理对象 |

### 1.2 明确不做

- 不读取、不修改、不清理用户端应用或第三方记忆插件数据。
- 不改变 `18011` 用户请求协议语义。
- 不把 `5173` 变成生命周期规则定义层。

---

## 2. 生命周期模型（Evidence/Telemetry）

### 2.1 State Machine

```
  [ingested_raw] -> [indexed_summary_ready] -> [maintenance_eligible] -> [maintained]
                          |                                           |
                          +------------------> [traceable_raw_retained]+
```

| 当前状态 | 事件 | 下一状态 | 说明 |
|---------|------|---------|------|
| `ingested_raw` | summary/index complete | `indexed_summary_ready` | 生成热路径可读 summary |
| `indexed_summary_ready` | maintenance window reached | `maintenance_eligible` | 满足维护条件 |
| `maintenance_eligible` | maintenance executed | `maintained` | 完成压缩/归档/清理动作（仅证据面） |
| 任意 | trace lookup | `traceable_raw_retained` | raw evidence 可追溯，不在热路径直接扫描 |

### 2.2 热路径规则

- 控制面与 KPI 只读 summary 资产。
- raw evidence 默认不进入控制面热路径扫描。
- raw evidence 必须保留 traceability 映射。

---

## 3. 模块边界（目标架构）

### 3.1 模块职责

| 模块 | 职责 | 非职责 |
|------|------|--------|
| `summary_store` | 维护热路径 summary/index，供控制面和 KPI 读取 | 不直接持有/重写 raw evidence 全量 |
| `maintenance_manager` | 自动维护调度、状态更新、手动触发入口执行 | 不定义用户请求协议，不接管产品入口语义 |
| `evidence_store`（现有） | 保留 raw evidence 追溯资产 | 不再承担控制面热路径聚合 |
| `status_read_model`（现有） | 面向控制面的读模型投影 | 不再直接多轮扫描 raw evidence |

### 3.2 架构规则（强制）

1. **Extract, Don’t Accrete**
2. **Hot Path Reads Summary**
3. **Raw Evidence Stays Traceable**
4. **Local Autonomous Maintenance**
5. **No Client Memory Control**

---

## 4. 维护策略

### 4.1 默认策略

- 默认自动维护（local autonomous maintenance）。
- `5173` 仅显示维护状态并允许手动触发。
- 自动维护失败时，状态可见且可重试，不影响 `18011` 请求协议。

### 4.2 第一阶段约束

- 仅治理 evidence/telemetry 生命周期。
- 不删除产品核心记忆内容。
- 若后续涉及产品记忆压缩/归档，需新 spec + 新 gate。

---

## 5. 验收 Gate（Batch 0 文档后）

### Gate A：边界清晰

- [ ] 文档明确区分：用户端记忆 / 产品记忆 / 运行证据与遥测。
- [ ] 文档明确 `5173` 不定义生命周期，`18011` 协议不变。

### Gate B：主线定位

- [ ] phase6 active plan/README 将 DLP 标记为正式工程主线。
- [ ] 文档明确该主线不是 CSP 后续增强，也不是 UI 优化分支。

### Gate C：实现批前置

- [ ] 明确下批实现入口为 `summary_store` + `maintenance_manager` 最小骨架。
- [ ] 明确从 `status_read_model.py` 和 `meter_store.py` 抽离职责，而非继续堆叠。

---

## 6. 可观测性（Lifecycle Plane）

- [ ] maintenance cycle id（每轮维护唯一标识）
- [ ] summary freshness（热摘要时间戳）
- [ ] raw traceability mapping completeness
- [ ] maintenance last status（success/fail + reason）
- [ ] 手动触发审计痕迹（谁触发、何时触发）

---

## 7. 与代码对照（Batch 0 预对照）

| Spec 条目 | 当前代码位置 | Batch 0 状态 |
|-----------|-------------|--------------|
| 控制面热路径应读 summary | `5_connectors/adapter/application/status_read_model.py` | 待实现抽离 |
| 证据生命周期维护调度 | `5_connectors/adapter`（暂无独立 manager） | 待实现骨架 |
| meter/evidence 原始存储 | `5_connectors/adapter/infrastructure/meter_store.py` 等 | 现存，待边界重构 |

---

## 8. 变更历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-04-25 | 初始版本，定义 DLP 分类/边界/维护策略/验收 gate |

