---
doc_id: PLAN-PHASE4-STATUS
title: OmniMemora Phase 4 Status
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [ADR-0001-PRODUCT-BOUNDARY]
supersedes: []
last_verified_commit: ""
---

# Phase 4 状态标记

**版本：** OmniMemora Phase 4 / Agent Observability v1.2 — Identity Canonicalization
**状态：** ✅ ACCEPTED
**日期：** 2026-04-14

---

## Agent Observability 版本线

```text
v1.0 — 基础观测（2026-04-12）  ✅
v1.1 — JSONL 持久化（2026-04-13） ✅
v1.2 — Identity Canonicalization（2026-04-14） ✅
```

---

## 状态说明

已完成 JSONL 持久化改造，agent_metrics 写入磁盘，启动时自动回放历史事件，重启后指标完整恢复。
JSONL 文件路径：`~/.omnimemora/adapter/agent_events.jsonl`（可通过 `OMNIMEMORA_AGENT_EVENTS_PATH` 配置）。

---

## Phase 4 v1.1 交付物清单

| 交付物 | 位置 | 状态 |
|--------|------|------|
| Final Compile Gate 文档 | [9_adr/ADR-0004-final-compile-gate.md](9_adr/ADR-0004-final-compile-gate.md) | ✅ 冻结 |
| Agent Observability 工程方案 | [7_docs/internal/phase4/plan/AGENT_OBSERVABILITY_MINI_v1.md](7_docs/internal/phase4/plan/AGENT_OBSERVABILITY_MINI_v1.md) | ✅ 完成 |
| v1.1 实现方案 | [7_docs/internal/phase4/plan/AGENT_OBSERVABILITY_v1.1_JSONL_PERSISTENCE.md](7_docs/internal/phase4/plan/AGENT_OBSERVABILITY_v1.1_JSONL_PERSISTENCE.md) | ✅ 完成 |
| agent_identity.py | [5_connectors/adapter/agent_identity.py](5_connectors/adapter/agent_identity.py) | ✅ 完成 |
| control_mode.py | [5_connectors/adapter/control_mode.py](5_connectors/adapter/control_mode.py) | ✅ 完成 |
| agent_metrics.py (JSONL) | [5_connectors/adapter/agent_metrics.py](5_connectors/adapter/agent_metrics.py) | ✅ 完成 |
| config.py (新增配置) | [5_connectors/adapter/config.py](5_connectors/adapter/config.py) | ✅ 完成 |
| Unit tests v1.0 (27 tests) | [5_connectors/adapter/tests/test_agent_identity.py](5_connectors/adapter/tests/test_agent_identity.py) | ✅ 通过 |
| Unit tests v1.1 (14 tests) | [5_connectors/adapter/tests/test_agent_metrics.py](5_connectors/adapter/tests/test_agent_metrics.py) | ✅ 通过 |
| `/agents/live` API | main.py | ✅ 运行中 |
| `/agents/metrics` API | main.py | ✅ 运行中 |

---

## Phase 4 完整验收

| # | 标准 | 状态 |
|---|------|------|
| 1 | engine.py 完全未改 | ✅ |
| 2 | 原有 query 主路径正常 | ✅ |
| 3 | agent_id / session_id 识别 | ✅ |
| 4 | UI 可拿到 per-agent 指标 | ✅ |
| 5 | `force_if_possible` 仅在 adapter 可控范围 | ✅ |
| 6 | 所有新增能力留在 5_connectors/adapter/ | ✅ |
| 7 | 历史工具注册：context 类 MCP 工具曾用于 Phase 4 试验；当前主线已废弃 | ✅ |
| 8 | MCP 返回 `content[].text` 为 string | ✅ |
| 9 | metrics 持续增长 | ✅ |
| 10 | ADR-0004 Final Compile Gate 已文档化 | ✅ |
| 11 | JSONL 写盘验证（21行/15请求） | ✅ |
| 12 | 重启恢复验证（request_count=15 before, =15 after） | ✅ |
| 13 | 累计数据正确（restart后5条，total=20） | ✅ |
| 14 | JSONL 文件滚动（文件超50MB时自动rotate） | ✅ |
| 15 | 30天旧事件自动清理（replay时跳过） | ✅ |

---

## v1.1 实测数据

| 阶段 | 请求数 | saved_tokens | JSONL行数 |
|------|--------|-------------|----------|
| 重建前 | 15 | 1245 | 21 |
| 重启后 | 15（回放） | 1245（回放） | — |
| 重启后+5 | 20 | 1660 | 31 |

验收通过：15请求重启 → 15恢复 → 再加5 → 20总计 ✅

---

## ADR-0005 Agent Identity 字段规范（v1.0）已落地

**日期：** 2026-04-14
**状态：** ✅ v1.2 Canonical Identity Alignment 完成

ADR-0005 已保存至 [9_adr/ADR-0005-agent-identity-fields.md](9_adr/ADR-0005-agent-identity-fields.md)。

**v1.0 → v1.2 改动：**

| 文件 | 改动 |
|------|------|
| `agent_identity.py` | 新增 `canonical_agent_id` + `raw_agent_id` 双字段；新增 `resolve_canonical_agent_id()` 映射函数 |
| `agent_metrics.py` | `record_request/record_result` 改用 `canonical_agent_id` |
| `main.py` | `load_control_mode()` 传 `canonical_agent_id`；新增 `_reload_agent_modes()` + `_agent_modes_cache` |
| `config/agent_modes.json` | **新建** — per-agent control mode 配置，key = canonical_agent_id |
| `test_agent_identity.py` | 全部重写测试（17 tests），覆盖映射/Optional defaults/raw captured |
| `test_agent_metrics.py` | `MockIdentity` 改用 `canonical_agent_id` |

**v1.2 Canonical Identity Alignment 修复：**

| 问题 | 修复 |
|------|------|
| `/agents/metrics?agent_id=raw` 返回空 | API 层调用 `resolve_canonical_agent_id()` 归一化后再查询 |
| `per_agent_modes` 加载用 `getattr(dict)` 报错 | 改用 `_agent_modes_cache` tuple（已缓存 canonical key 的 dict） |
| `agent_modes.json` 不存在 | 新建 `config/agent_modes.json`，key = canonical agent_id |

**关键语义：**
- `canonical_agent_id` = runtime 治理字段，对齐 memory scope
- `raw_agent_id` = 外部原始值，仅用于日志/tracking
- session_id / workspace_id / user_id = Optional，None 表示未提供

---

## 下一版本（v1.2）待办

1. **per-agent control mode 配置** — 接入 config/agent_modes.json
2. **force_if_possible 补偿执行** — 在 `/mcp/query` 中实现"具备输入则补做一次 optimize_context"的逻辑
3. **OpenClaw 真实任务验证** — 在运行中的 OpenClaw Agent 做白盒 prompt 来源验证
