---
doc_id: SCAN-PHASE5_5-TRACKC-18011-2026-04-18
title: OmniMemora Phase 5.5 Track C 18011 Bounded Global Scan
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Track C: 18011 Bounded Global Scan

## 一、扫描范围

本次 bounded global scan 只覆盖与 `18011` 责任拆分直接相关的模块：

- adapter ingress / control / status：
  - `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/main.py`
  - `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/llm_proxy.py`
  - `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/gateway_compile.py`
  - `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/runtime_bridge.py`
- 当前主线 compile / strategy 逻辑：
  - `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/engine.py`
  - `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/v2_compute.py`
  - `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/app/context/strategy.go`
  - `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/app/context/strategy_topk.go`
- internal runtime bridge：
  - `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/backends/omnimemora_runtime_backend.py`

本扫描不进入大重构，也不覆盖所有历史 phase 文档，只回答 Track C 所需的边界问题。

## 二、可复用

### 1. `18011` 的 ingress / orchestration 骨架

- `llm_proxy.py` 已经具备协议入口与路由分叉职责：
  - agent 识别
  - route on/off 判定
  - upstream passthrough
  - compile 前后 payload 转换
- 这部分是未来 `18011 ingress/orchestration` 的自然骨架。

关键入口：

- `proxy_openai_chat`
- `proxy_anthropic_messages`
- `_compile_or_passthrough_for_route`
- `_routing_enabled_for_agent`

### 2. `gateway_compile.py` 适合作为独立 compile module 雏形

- `normalize_inbound_request`
- `build_compile_context`
- `run_gateway_compile`

这一层已经把 compile 过程抽成：

- request normalize
- memory candidate fetch
- runtime compile
- compiled payload rebuild

它虽然还在 adapter 内，但天然更像将来的 `local compile module`，而不是入口层本体。

### 3. `engine.py` 适合作为本地 compile/packing 内核

`4_core/logic/engine.py` 当前职责是：

- filter
- route/score
- dedup
- select
- pack
- meter

它基本符合“纯逻辑编排内核”的预期，不依赖 HTTP，不直接依赖 UI，不直接依赖产品入口。

### 4. runtime context strategy 可复用为本地 strategy module 候选

`4_core/local-runtime/app/context/strategy*.go` 现有内容已经具备：

- strategy registry
- mode / token budget
- Top-K / recency / diversity 之类的选择策略

这部分更适合归入未来 `local strategy module`，而不是继续挂在 `18011` 入口层。

## 三、必须避开

### 1. 避免把 `main.py` 当成 Track C 的长期结构模板

`main.py` 仍然保留明显历史叙事与聚合式职责：

- `Memory Adapter v2.2`
- OpenViking 中间层
- V2 meter / quota / filter / dedup / route / transform 聚合

它是现有系统的宿主，不是未来的清晰分层模板。Track C 不应沿着 `main.py` 继续堆责任。

### 2. 避免让 `llm_proxy.py` 继续直接长大成“胖入口”

`llm_proxy.py` 当前除了 ingress/orchestration，还直接承担：

- compile route decision
- upstream contract adaptation
- usage/trace logging
- 部分 passthrough/raw response shaping

如果 Track B 和后续策略继续直接加在这里，会把 `18011` 进一步绑定成超胖入口。

### 3. 避免把 V2 metering / quota artifacts 回流成 Track C 主边界

`4_core/logic/v2_compute.py` 中的：

- `TokenSavingsMeter`
- `QuotaEnforcementResult`
- `generate_meter_artifact`

对当前产品仍有价值，但它们不是 `18011` ingress/orchestration` 的核心职责。Track C 不应把这些 artifact 重新塞回入口层边界定义里。

## 四、需要清理

### 1. `18011` 当前职责仍然混合了 5 类内容

当前从 `18011` 可追到的职责包含：

- ingress
- compile orchestration
- diagnostics/status
- control aggregation
- 历史 adapter/meter/filter/quota 宿主逻辑

Track C 的第一目标不是立刻搬代码，而是先把这 5 类内容拆成清晰责任图。

### 2. compile / strategy 边界目前仍散落两种实现传统

compile 侧散点：

- `gateway_compile.py`
- `runtime_bridge.py`
- `engine.py`
- `v2_compute.py`

strategy 侧散点：

- `4_core/local-runtime/app/context/strategy*.go`
- `4_core/logic/router.py` / `filter.py` 中的策略/打分规则

这说明“compile module”与“strategy module”还没有统一的显式边界。

### 3. V2 遗产与当前主线的逻辑边界仍需声明

当前仍可见：

- `main.py` 的 V2 / OpenViking 宿主痕迹
- `v2_compute.py` 的 artifact/meter 逻辑

这些不是要立刻删除，而是要在 Track C 的责任图里明确：

- 哪些继续作为当前主线依赖
- 哪些只算遗产资产
- 哪些不应再反向定义未来边界

## 五、当前实现入口

### A. 当前 `18011 ingress/orchestration` 入口

- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/llm_proxy.py`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/main.py`

当前自然职责：

- LLM ingress
- route on/off
- upstream forwarding
- control/status router mounting

### B. 当前 `local compile module` 候选入口

- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/gateway_compile.py`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/runtime_bridge.py`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/engine.py`

建议边界：

- `gateway_compile.py`：compile orchestration facade
- `runtime_bridge.py`：adapter -> compile/runtime bridge
- `engine.py`：pure optimization core

### C. 当前 `local strategy module` 候选入口

- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/app/context/strategy.go`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/app/context/strategy_topk.go`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/router.py`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/filter.py`

建议边界：

- runtime context strategy：显式 strategy registry / policy mode
- Python router/filter：当前主线打分与过滤规则，后续需要明确是保留在 compile core 还是上移为 strategy layer

## 六、Track C 边界结论

Track C 当前不该直接做代码大拆分，而应先固定以下目标分层：

1. `18011 ingress/orchestration`
   - 只保留协议接入、路由判定、调用编排、统一状态聚合

2. `local compile module`
   - normalize
   - candidate fetch
   - optimize/pack
   - compiled payload rebuild

3. `local strategy module`
   - strategy registry
   - mode / budget / feature gates
   - score/filter/select policy

## 七、下一步建议

Track C 下一步不进实现，先补一份责任边界图与迁移顺序说明：

- 哪些函数/文件继续留在 `18011`
- 哪些优先抽成 compile facade
- 哪些先只做 contract，不搬实现

只有这一步完成后，才适合进入真正的拆分准备实现。
