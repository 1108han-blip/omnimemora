---
doc_id: PLAN-PHASE5_5-TRACKC-MAIN-SLIMMING-2026-04-18
title: OmniMemora Phase 5.5 Track C main.py Slimming Candidate
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on:
  - PLAN-PHASE5_5-TRACKC-BOUNDARY-MAP-2026-04-18
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Track C: `main.py` Slimming Candidate

## 一、目的

本文件只回答：

- `main.py` 里什么必须保留
- 什么可以外移
- 什么应该后置处理

本文件不触发立即迁移。

## 二、当前问题

`/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/main.py` 当前混合了：

- app 宿主
- middleware
- router 挂载
- MCP/SSE surface
- health / support / metrics / debug
- memory CRUD/query
- token savings / quota / trial / internal admin
- V2 历史聚合导入

这会直接带来三个问题：

1. `18011` 入口职责边界不清
2. 后续任何改动都容易继续加厚 `main.py`
3. Track B / Track C / 历史 V2 逻辑交织，增加回归风险

## 三、必须保留

以下内容当前应继续留在 `main.py`：

### 1. app 宿主与基础 middleware

- `FastAPI(...)`
- `app.add_middleware(CORSMiddleware, ...)`
- `@app.middleware("http") attach_request_id`

原因：

- 这是 adapter 应用宿主和基础请求上下文入口
- 现在动它，风险高，收益低

### 2. backend lazy init

- `_initialized_backend`
- `_get_backend()`

原因：

- 这是当前 adapter 全局 backend 访问点
- 可后续收敛，但不适合作为第一批 slimming 对象

### 3. router mount

- `app.include_router(_llm_proxy_mod.router, prefix="")`
- `app.include_router(_status_api_mod.router, prefix="")`
- `app.include_router(_agent_control_api_mod.router, prefix="")`

原因：

- 这是当前较清晰的“已拆模块”接入点
- 不应在第一批 slimming 中再折腾

## 四、可外移

以下内容适合成为后续 slimming 的分批候选：

### A. 启动探测与内部 transport 预探测

当前位置：

- startup probe 代码块

当前状态：

- [x] 已外移

建议去向：

- 独立 `startup_probe.py` 或 `boot/runtime_probe.py`

原因：

- 这是启动诊断逻辑，不是 app 宿主核心

### B. quota/path observation helper

当前位置：

- `_QUOTA_ROUTE_KEYWORDS`
- `_PROXY_INGRESS_PATHS`
- `_is_quota_related_path`
- `_quota_marker`
- `_classify_quota_observation`
- `_upstream_url_for_observation`

当前状态：

- [x] 已外移

建议去向：

- 独立 `quota_observer.py` / `path_observer.py`

原因：

- 这是辅助观测逻辑，不应继续挂在 app 宿主层

### C. MCP/SSE surface

当前位置：

- `/sse`
- `/messages`
- `/mcp`
- `/mcp/query`
- MCP bootstrap helpers

当前状态：

- [x] 已外移

建议去向：

- 独立 `mcp_surface.py`

原因：

- 这是清晰的协议面
- 现在仍留在 `main.py` 只是历史宿主原因

### D. metrics / debug / support surface

当前位置：

- `/metrics/*`
- `/debug/*`
- `/support/error-codes`
- `/agents/live`
- `/agents/metrics`

当前状态：

- [x] 已外移

建议去向：

- 独立 `diagnostics_surface.py`

原因：

- 这些已经接近独立诊断面
- 继续留在 `main.py` 只会阻碍入口瘦身

## 五、后置处理

以下内容不适合放在第一批 slimming：

### 1. `/memory/query`

原因：

- 它仍然牵涉：
  - `FilterRules`
  - `RoutingRules`
  - `classify_task`
  - `TokenSavingsMeter`
  - quota enforcement
  - meter persistence
- 这条路径牵涉 V2 遗产最多
- 应等 compile / strategy 边界更清楚后再动

### 2. `/memory/write` / `/memory/search` / `/memory/read` / `/memory/delete`

原因：

- 它们虽然更像 memory API，但仍直接依赖：
  - backend
  - dedup
  - routing/score
  - namespace prepare
- 先移动风险高于收益

### 3. trial / internal admin surfaces

当前位置：

- `/api/admin/trials/provision`
- `/internal/trial-query`

原因：

- 这是独立业务轴线
- 当前不应和 Track C 的入口瘦身绑在一起
- 它们更适合作为第三批候选中的“单独业务 surface”，而不是继续混在 `main.py` 的纯入口瘦身里

### 4. token-savings / meter query surface

当前位置：

- `/usage/token-savings`
- `/usage/token-savings/trend`
- `/requests/{request_id}/meter`

原因：

- 这批 surface 相对 `memory/query` 更表层，但仍依赖 meter artifact 与 V2 统计链路
- 可以作为第三批候选，但应独立于 memory CRUD 与 compile path

## 六、建议的瘦身顺序

### Step 1

先抽离：

- startup probe
- quota/path observation helpers

状态：

- [x] 已完成

风险最低，且不触发路由行为变化。

### Step 2

再抽离：

- MCP/SSE surface
- diagnostics surface

状态：

- [x] 已完成

收益高，但应单独成批验证。

### Step 3

再抽离：

- token-savings / meter query surface
- trial / internal admin surface

状态：

- [ ] 候选，未开始

说明：

- 这一步已经不再是“纯表层无状态 route 外移”
- 若继续推进，应再次判断是否仍属于 `Track C` 的低风险拆分准备
- 若会触及 meter artifact、trial entitlement、quota 业务轴线，应单独立批

- metrics / debug / support / agents diagnostics 到 `diagnostics_api.py`

这一步可以明显减轻 `main.py` 体量。

### Step 4

最后才考虑：

- memory query / memory CRUD
- internal trial/admin surfaces

## 七、当前结论

`main.py` 可以瘦身，但当前最合理的第一批不是“动核心路由”，而是先剥离：

- startup probe
- quota/path observation helpers
- MCP/SSE surface
- diagnostics surface

也就是说，`main.py slimming` 现在已经可以进入“小批次迁移准备”，但不应直接从 `/memory/query` 这类高耦合路径下手。
