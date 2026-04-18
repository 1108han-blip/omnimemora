---
doc_id: PLAN-PHASE5_5-TRACKC-BOUNDARY-MAP-2026-04-18
title: OmniMemora Phase 5.5 Track C 责任边界图与迁移顺序
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on:
  - PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18
  - SCAN-PHASE5_5-TRACKC-18011-2026-04-18
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Track C: 责任边界图与迁移顺序

## 一、目的

本文件不是立即拆分代码，而是把 `18011` 的未来边界固定下来，避免后续继续把入口层做胖。

本文件回答三件事：

1. `18011` 应保留什么
2. compile / strategy 应抽离什么
3. 迁移顺序如何安排，才能最小化返工和工作区污染

## 二、目标分层

### 1. `18011 ingress/orchestration`

保留职责：

- 协议入口
  - OpenAI / Anthropic / Responses ingress
- route on/off 判定
- upstream passthrough / compile path 分流
- 统一状态聚合
  - system status
  - proxy status
  - control surface aggregation
- Trace / request identity 透传

不再长期承担：

- compile 细节实现
- strategy registry / selection policy 细节
- packed context 生成内核
- V2 artifact / meter / quota 宿主式聚合

### 2. `local compile module`

目标职责：

- inbound normalize
- compile context build
- memory candidate fetch bridge
- optimization / packing 调用
- compiled payload rebuild

当前候选承载：

- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/gateway_compile.py`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/runtime_bridge.py`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/engine.py`

### 3. `local strategy module`

目标职责：

- strategy registry
- mode / token budget
- score / filter / select policy
- future feature gates / policy knobs

当前候选承载：

- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/app/context/strategy.go`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/app/context/strategy_topk.go`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/app/context/strategy_recency.go`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/router.py`
- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/logic/filter.py`

## 三、当前边界图

### A. 现状

- `main.py`
  - 历史 adapter 宿主
  - router 挂载
  - V2 meter / dedup / filter / route 依赖聚合
- `llm_proxy.py`
  - ingress
  - route 判定
  - compile path / passthrough 分流
  - upstream response shaping
- `gateway_compile.py`
  - compile facade
  - normalize + fetch + compile + rebuild
- `runtime_bridge.py`
  - backend search + optimization bridge
- `engine.py`
  - pure optimization pipeline
- runtime context strategies
  - strategy registry / mode / excerpt selection

### B. 目标

- `main.py`
  - 只保留 app 宿主、router 注册、基础 middleware
- `llm_proxy.py`
  - 只保留 ingress/orchestration
- `gateway_compile.py`
  - 成为 compile facade
- `runtime_bridge.py`
  - 成为 compile/runtime bridge
- `engine.py`
  - 继续作为 pure optimization core
- runtime strategy files
  - 成为显式 strategy layer

## 四、必须避免的迁移方式

### 1. 不要从 `main.py` 直接大搬家

`main.py` 现在承担历史宿主作用，直接从这里拆会同时碰：

- app lifecycle
- middleware
- trace
- V2 imports
- backend initialization

风险过高。Track C 不应从 `main.py` 开始大改。

### 2. 不要先拆 `llm_proxy.py` 的行为再定义边界

`llm_proxy.py` 现在是实际产品入口逻辑。若先拆行为、后定义边界，容易直接影响：

- route=off passthrough
- route=on compile
- Track B 状态机与 gateway 故障恢复

所以先画边界，再移动调用点。

### 3. 不要把 V2 artifact 直接判成“立即删除”

`v2_compute.py` 仍承载：

- token estimate
- meter artifact
- quota enforcement result

这些可后置治理，但不能在 Track C 第一批中粗暴删除。

## 五、迁移顺序

### C1. 边界冻结

动作：

- 冻结本文件中的三层边界
- 约束后续新增逻辑不得继续加厚 `main.py`
- 约束后续 compile 相关新增逻辑优先写到 `gateway_compile.py / runtime_bridge.py`

完成标准：

- 责任边界文档通过
- runbook 指向本文件

### C2. `main.py` 瘦身准备

动作：

- 列出 `main.py` 当前真正需要保留的最小职责
- 列出可以外移的导入聚合与历史宿主逻辑
- 不搬实现，只产出“保留/外移/后置”清单

完成标准：

- 有一份 `main.py` slimming candidate 清单
- 第一批低风险外移已验证成立：
  - `startup probe`
  - `quota/path observation helpers`
- 第二批中风险外移已验证成立：
  - `MCP/SSE surface`
  - diagnostics surface

### C3. compile facade 固定

动作：

- 让 compile 相关新增逻辑只进入：
  - `gateway_compile.py`
  - `runtime_bridge.py`
- 不再让 `llm_proxy.py` 增长 compile 细节

完成标准：

- compile 调用点和 facade 边界被文档化

### C4. strategy layer 固定

动作：

- 把 strategy registry / mode / budget / policy 明确标成独立 layer
- 先定义 contract，不搬算法

完成标准：

- strategy layer contract 被文档化

### C5. 再决定是否进入代码迁移

只有在 C1-C4 完成后，才判断是否进入真正的拆分实现批次。

## 六、`main.py` 瘦身建议

后续若进入 `main.py` slimming，优先顺序建议如下：

1. 抽离纯 helper / import aggregation
2. 抽离历史 V2 meter / dedup / quota 宿主式依赖
3. 保留：
   - app init
   - middleware
   - backend lazy init
   - router mount
4. 已完成的表层 router 外移：
   - `MCP/SSE surface`
   - diagnostics surface
4. 不在第一批触碰：
   - request middleware 链
   - trace header 传播
   - app include_router 注册顺序

## 七、当前结论

Track C 当前已经具备进入“拆分准备”阶段的条件，但还不应直接开始大规模代码搬迁。

最合理的下一步是：

- 先出 `main.py slimming candidate` 清单
- 再决定是否开始第一批小范围代码迁移
