---
doc_id: ADR-DLP-001
title: Data Lifecycle Plane as Formal Architecture Correction Mainline
owner: product-arch
reviewers: [arch-lead, qa-lead]
status: active
version: 1.0.0
effective_date: 2026-04-25
depends_on:
  - GOV-AUDIT-SCHEME-001
supersedes: []
last_verified_commit: ""
---

# ADR-DLP-001: Data Lifecycle Plane as Formal Architecture Correction Mainline

**状态：** `Active`
**日期：** 2026-04-25
**范围：** OmniMemora 内部 telemetry/evidence/meter/trace/summary/maintenance 的生命周期治理边界与工程主线定位

---

## 0. Summary（执行摘要）

将 Data Lifecycle Plane 定义为 OmniMemora 的正式架构修正主线，用于解决长期运行后的性能、内存、磁盘、证据追溯与模块边界问题；该主线不是 CSP 延伸，也不是 5173 UI 优化分支。

---

## 1. Context（背景）

### 当前状态

- `/agents/control` 相关批次已证明 timeout tail 可降压，但后端 CPU p95 仍有 residual。
- 当前读模型与证据路径在热路径上存在高耦合风险，长期运行下会累积性能与维护复杂度。
- phase6 当前索引包含多个 closeout 记录，但尚未把“生命周期治理”明确为独立架构主线。

### 问题

现有路径容易把“性能修补”误解为局部优化，导致生命周期职责继续堆叠到旧模块（accrete），而不是结构性抽离（extract）。

### 约束

- 产品边界不变：`5173` 控制入口，`18011` 产品数据入口，`8765` 内部 plane。
- 不读取/修改/清理用户端应用或第三方记忆插件数据。
- 第一阶段不删除产品核心记忆内容。
- 维护平面不得改变用户请求协议语义。

---

## 2. Decision（决策）

### 选择

从本日起，将 Data Lifecycle Plane 作为正式工程主线启动，按“Docs-Only Batch 0 -> 实现批”推进。该主线只治理 OmniMemora 内部运行证据与遥测资产的生命周期，不扩展到用户端记忆控制。

架构规则固定如下：

1. **Extract, Don’t Accrete**：从旧模块抽离职责，不向旧模块继续堆维护逻辑。
2. **Hot Path Reads Summary**：控制面和 KPI 只读 hot summary，不扫 raw evidence。
3. **Raw Evidence Stays Traceable**：原始证据保持可追溯，但退出控制面热路径。
4. **Local Autonomous Maintenance**：默认自动维护，用户只保留状态查看和手动触发入口。
5. **No Client Memory Control**：不读取、不修改、不清理用户端应用或第三方记忆插件的数据。

### 替代方案（Alternatives Considered）

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 继续按 `/agents/control` 局部性能补丁推进 | 变更小，短期见效快 | 生命周期边界继续漂移，长期维护成本高 | 未选 |
| 作为 CSP/5173 附属增强处理 | 文档改动少 | 主线定位错误，工程治理对象不清晰 | 未选 |
| **升级为正式 Data Lifecycle Plane 架构主线** | 边界清晰、可分批抽离、可建立独立验收 gate | 启动成本更高，需要先补架构文档 | **选中** |

---

## 3. Consequences（后果）

### 正面

- 性能、存储、追溯问题可在统一生命周期平面下治理。
- 模块边界可从“读时重扫”转向“summary-first”。
- 后续实现批有清晰验收口径，不再混入 UI/CSP 语义。

### 负面

- 需要新增维护模块与状态面，初期文档和实施成本上升。
- 需要谨慎处理“产品记忆”与“运行证据”的边界，避免误删核心内容。

### 兼容性说明

- 不改变 `18011` 请求协议语义。
- 不改变现有 `/agents/control` response schema。
- 不改变用户端应用与第三方记忆数据面。

---

## 4. Change Log（变更记录）

| 版本 | 日期 | 变更内容 | 变更人 |
|------|------|---------|--------|
| 1.0.0 | 2026-04-25 | 初始版本，定义 DLP 主线定位与架构规则 | codex |

---

## 5. 关联文档

- L2 Spec：`SPEC-DATA-LIFECYCLE-PLANE-001`
- Product Definition：`0_blueprint/PRODUCT_DEFINITION.md`
- Active Plan Index：`7_docs/internal/phase6/plan/README.md`

---

## 6. Review Checklist

- [x] 上下文充分，决策依据清晰
- [x] 替代方案评估了至少2个选项
- [x] 后果（正/负）均已说明
- [x] 与现有 ADR 无冲突
- [x] owner 和 reviewers 已确认

