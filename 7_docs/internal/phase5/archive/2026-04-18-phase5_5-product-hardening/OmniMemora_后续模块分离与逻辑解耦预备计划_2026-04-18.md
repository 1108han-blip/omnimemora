---
doc_id: PREP-PHASE5_5-MODULE-DECOUPLING-2026-04-18
title: OmniMemora 后续模块分离与逻辑解耦预备计划
owner: arch-lead
reviewers: [product-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora 后续模块分离与逻辑解耦预备计划

## 一、定位

本文件不是当前 phase5.5 的立即实现计划。

本文件只用于固定后续稳定运行阶段的模块分离方向，避免未来再次把结构性问题伪装成当前 track 内的小尾巴。

## 二、为什么需要后续解耦

当前已确认的结构性限制：

- `runtime` 同时承担：
  - internal capability plane
  - user decision carrier
  - operator dashboard/action surface
- 当 `runtime` 自身不可用时：
  - `disable-route / uninstall` 的正式承载面随之消失
  - 当前不能安全完成 `runtime dead + uninstall`

这不是单点 bug，而是当前 mixed architecture 的边界。

## 三、目标分层

后续目标分层固定为四层：

1. `18011 ingress/orchestration`
   - LLM ingress
   - route on/off 分流
   - upstream orchestration
   - 统一系统状态聚合

2. `runtime capability plane`
   - memory/search/write/query
   - compile/runtime bridge
   - strategy application
   - diagnostics for capability health

3. `decision/control carrier`
   - 故障状态承载
   - user decision intake
   - `disable-route / uninstall` 执行入口
   - 不依赖 runtime capability 健康

4. `strategy module`
   - policy / flags / feature gates
   - compile quality knobs
   - 云端策略下发后的本地应用

## 四、解耦顺序

### Step 1: 逻辑解耦

先做逻辑边界，不急于新服务化：

- 把 `decision/status/action` 从 runtime capability 语义中分离
- 明确哪些接口属于 capability，哪些属于 control carrier
- 保持现有启动链路不变

### Step 2: 承载面解耦

将以下能力从 runtime capability 中移出：

- `gateway/status`
- `gateway/decision/*`
- dashboard 中的 user-decision-required action carrier

目标：

- runtime 即使失效
- decision carrier 仍能提供最小状态与动作入口

### Step 3: 进程/宿主解耦

只有在 Step 1/2 稳定后，才决定是否物理拆分：

- 独立 decision process
- 或由 gateway host 承载 decision carrier
- 或由更轻量的 local control plane 承载

本阶段不预设唯一物理形态。

## 五、明确不在当前阶段做的事

以下内容不并入当前 phase5.5：

- 不新增第三个正式产品入口
- 不重写全部故障状态机
- 不同时大拆 `18011` / compile / strategy
- 不为了极端场景立即引入新的常驻复杂服务

## 六、下一阶段建议工程名

建议未来单独立项：

- `Decision Carrier / Control-Plane Decoupling`

建议该工程的第一批只做：

- bounded scan
- 责任边界图
- 最小控制承载接口草案
- `runtime dead + uninstall` 的正式解决方案

## 七、与当前成果的关系

当前 phase5.5 已完成：

- `Track B` 的当前阶段自愈与联合恢复主干
- `Track C` 的入口层瘦身准备

所以后续模块分离工程应建立在这些成果之上，而不是推翻当前实现。
