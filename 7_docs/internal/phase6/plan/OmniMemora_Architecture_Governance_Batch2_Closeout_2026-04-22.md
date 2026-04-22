---
doc_id: GOV-ARCH-BATCH2-CLOSEOUT-2026-04-22
title: OmniMemora Architecture Governance Batch 2 Closeout
owner: doc-team
reviewers: [arch-lead]
status: completed
version: 1.0.0
effective_date: 2026-04-22
depends_on: [GOV-AUDIT-SCHEME-001, ADR-0003-INTERFACE-ACCESS-PATHS]
supersedes: []
last_verified_commit: fa6b84e
---

# OmniMemora Architecture Governance Batch 2 Closeout

**Status:** COMPLETED  
**Date:** 2026-04-22  
**Type:** roadmap 外架构治理增强线  
**Scope:** `18011` 结构收敛与兼容协议路径迁移  
**Phase Note:** 不新增 roadmap phase，不改 `ROADMAP.md` 正式 phase 编号

---

## 1. 结论

Batch 2 已正式收口。

本批次完成了 `18011` 产品数据主链的结构收敛，确认：

- OpenAI-compatible 主路径已迁入 application compile entry
- Anthropic-compatible / Claude 路径已迁入 application compile entry
- `control plane / read-model` 已从 action API 视图中剥离
- Anthropic 路径 meter persistence 缺口已补齐

本批次收口后，兼容协议路径的工程实现已与当前产品原则重新对齐：

- 优先透传用户端既有、已熟悉的协议与上游真相
- 仅在缺失时使用最小必要 fallback/default
- 不把产品演化为新的配置中心、模型映射中心或市场适配中心
- 保持 transparent forwarding / passthrough 设计不变

---

## 2. 完成项

### 2.1 Batch 2A

**Commit:** `e04c549`

- 从 `agent_control_api.py` 视图中剥离 read-model 聚合
- 新增 `5_connectors/adapter/application/status_read_model.py`
- 将 control action 与 read-model 投影边界切开
- 同步补入 `ADR-0003` 的控制面 / 数据面口径

### 2.2 Batch 2B

**Commit:** `7fccf74`

- 新增 `5_connectors/adapter/application/compile_orchestrator.py`
- OpenAI-compatible 主路径改为通过 application compile entry 编排
- `llm_proxy.py` 不再独占 OpenAI compile 主链编排

### 2.3 Batch 2C

**Commit:** `fa6b84e`

- Anthropic-compatible / Claude 路径迁入 application 编排边界
- `_proxy_anthropic_messages()` 收敛为 ingress/egress 角色
- Anthropic 路径 meter persistence 修复完成
- 产品宪法补入“用户端接入真相优先、只做最小必要兼容”

---

## 3. 验证结论

本批次验证确认以下结论成立：

1. `routing=off` 时，Anthropic-compatible 三入口保持透明 passthrough
2. `routing=on` 时，OpenAI-compatible 与 Anthropic-compatible 路径均进入 application compile 主链
3. streaming 行为未回归
4. upstream error annotation 仍然成立
5. Anthropic 路径 meter 已可稳定命中查询接口

---

## 4. 边界与不在范围内事项

本次 Batch 2 收口范围仅包括：

- `18011` 内部 ingress / application 边界收敛
- OpenAI-compatible / Anthropic-compatible 协议路径迁移
- control/read-model 结构剥离
- Anthropic meter persistence 补齐
- 宪法级兼容原则补齐

本次 Batch 2 明确不包括：

- Skill Suggestion 独立能力批
- `5173` recommendation/advisory UI
- cloud policy binding optional interface
- `8765` 新一轮结构改造

---

## 5. 工作区说明

Batch 2 收口时，工作区仍存在以下 3 个未跟踪文档：

- `9_adr/ADR-0008-skill-suggestion-boundary.md`
- `docs/spec/SPEC-SKILL-SUGGESTION-CONSTRAINTS-002.md`
- `docs/spec/SPEC-SKILL-SUGGESTION-MODULE-001.md`

它们属于场外的 Skill Suggestion 独立能力批，不属于 Batch 2 收口范围，因此不影响本批次结论。

---

## 6. 后续建议

Batch 2 收口后，不应继续在本批次上扩面。

后续若继续推进，建议单独开启新的独立能力批，优先级可按以下顺序考虑：

1. Skill Suggestion 独立能力批
2. `5173` recommendation/advisory UI
3. cloud policy binding optional interface

