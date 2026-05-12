---
doc_id: ADR-0004-FINAL-COMPILE-GATE
title: Historical MCP Context Tool Policy
owner: platform-team
reviewers: [arch-lead, qa-lead]
status: historical
version: 2.0.0
effective_date: 2026-05-12
depends_on: [ADR-0001-PRODUCT-BOUNDARY, ADR-0003-INTERFACE-ACCESS-PATHS]
supersedes: [ADR-0004-FINAL-COMPILE-GATE-v1]
last_verified_commit: ""
---

# ADR-0004: Historical MCP Context Tool Policy

**状态：** Historical / Superseded
**日期：** 2026-05-12
**范围：** 旧 MCP context 工具语境的退休记录

---

## 当前结论

旧的 MCP context 工具策略已不再代表当前产品规范。

当前产品主线固定为：

```text
Agent request -> OmniMemora product ingress :18011
              -> internal product memory read/write
              -> internal context compile
              -> upstream model provider
```

`18011` 是 routing enabled 后唯一产品数据入口。MCP 只保留为兼容/诊断接入模块，不是当前产品要求通路。

---

## 废弃内容

以下旧语义已经退休：

| 旧对象 | 当前状态 | 当前解释 |
|--------|----------|----------|
| `memory.context` | deprecated | 旧 MCP 工具入口；不是产品记忆系统本体，也不是当前产品入口 |
| `memory.recall` | deprecated | 旧 context 工具别名；不再作为 agent-facing compile path |
| `omnimemora_search_memory` | deprecated | 旧 search/context 混合别名；不再默认暴露 |
| `memory.search` | compatibility | 可作为兼容检索工具，但不得要求再交给 context 工具 |
| `memory.write` | compatibility | 可作为兼容写入工具；产品主链路写入由 `18011` 内部执行 |

废弃对象不得再被描述为产品唯一入口，也不得作为 agent 侧 prompt 组装步骤。

---

## 保留内容

本 ADR 不删除产品内部记忆系统。

以下能力仍属于产品内部主线：

- `/memory/search`
- `/memory/write`
- internal `8765` memory plane
- `4_core.logic.engine.optimize_context()`
- `18011` ingress 内部的记忆读取、选择、编译和写入流程

这些能力应由 `18011` 内部主动使用，而不是依赖 agent 通过 MCP 工具自行取上下文。

---

## 兼容策略

MCP surface 可以继续存在，但默认 `tools/list` 不再暴露旧 context 工具。

如果历史客户端直接调用旧 context 工具，Adapter 应返回清晰的 deprecated/error 结果，并且不得返回可直接拼入 prompt 的 `packed_context`。

`/mcp/query` 暂时保留为内部兼容/测试路径。它不是 agent-facing product contract，也不是当前产品主入口。

---

## 验证标准

| # | 标准 | 验证方式 |
|---|------|----------|
| 1 | MCP `tools/list` 默认不暴露旧 context 工具 | JSON-RPC `tools/list` 检查工具名 |
| 2 | 直接调用旧 context 工具返回 deprecated/error | JSON-RPC `tools/call` 检查 content block |
| 3 | 旧 context 工具不返回 `packed_context` | 检查返回 JSON/text 中不存在该字段 |
| 4 | 产品记忆系统保留 | `/memory/search`、`/memory/write`、`8765`、`optimize_context()` 仍作为内部能力存在 |
| 5 | 产品主链路仍走 `18011` | LLM 请求 routing enabled 时从 `18011` 进入 |

---

## 相关文档

- [ADR-0003-interface-access-paths.md](ADR-0003-interface-access-paths.md) — 多接口单核心架构
- [ADR-0001-product-boundary-reset.md](ADR-0001-product-boundary-reset.md) — 产品边界定义
- [4_core/logic/engine.py](../4_core/logic/engine.py) — `OptimizationInput` 与 `optimize_context()`
- [5_connectors/adapter/mcp_surface.py](../../5_connectors/adapter/mcp_surface.py) — MCP compatibility surface

---

## 约束优先级

1. `18011` 是当前产品数据入口。
2. 产品记忆读写必须由产品内部链路主动执行。
3. MCP context 工具不得重新成为 agent-facing compile contract。
4. 兼容模块不得替代产品主链路。

违反以上约束视为产品边界缺陷。
