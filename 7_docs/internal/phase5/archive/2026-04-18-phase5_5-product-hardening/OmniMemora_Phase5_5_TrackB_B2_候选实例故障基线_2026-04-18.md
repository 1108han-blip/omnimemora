---
doc_id: BASELINE-PHASE5_5-TRACKB-B2-2026-04-18
title: OmniMemora Phase 5.5 Track B B2 候选实例故障基线
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [SPEC-PHASE5_5-TRACKB-SELFHEAL-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Track B / B2 候选实例故障基线

## 一、文档定位

本文件记录 Track B 在正式实现前的候选实例基线行为，用于说明“当前已经有什么”和“当前还缺什么”。

验证对象统一绑定：

- 候选 adapter: `18012`
- 候选 runtime: `18765`
- 隔离 runtime data: `.tmp/candidate-runtime-data-b2`
- 上游 stub: `http://127.0.0.1:19001/v1`

## 二、健康基线

### Healthy 基线

- `GET /health` 返回 `healthy`
- `GET /agents/control` 返回 agent 列表
- `enable(openclaw)` 后，顺序触发 `/llm/chat`
- 最新 compile event 为 `runtime_compile / compile_success`

结论：

- 当前 healthy 分支的 `route=on -> compile path` 在候选实例上成立

## 三、能力层故障基线

### 故障注入

- 保留 adapter `18012`
- 杀掉候选 runtime `18765`

### 观察结果

- `GET /health` 返回 `degraded`
- `GET /agents/control` 返回 `503`
- `POST /memory/search` 返回 `500`
- `POST /llm/chat` 仍可返回上游结果

### 当前缺口

- 没有统一的 `degraded-capability` 对外状态输出
- 控制面当前在能力层故障时直接不可用
- `/llm/chat` 可继续成功，但不是显式、可观测的“自动降级为 passthrough”结果
- 当前还没有 UI 静默提示的状态承载

## 四、入口层故障基线

### 故障注入

- 停掉候选 gateway `18012`

### 观察结果

- `18012/health` 不可访问
- `18012/agents/control` 不可访问

### 当前缺口

- 当前没有 `user-decision-required` 的对外承载面
- 当 gateway 不可达时，无法通过现有产品接口向用户暴露决策状态

## 五、基线结论

Track B 当前基线可总结为：

1. healthy 分支已经成立
2. 能力层故障能被健康面探测，但还没有统一降级状态输出
3. 入口层故障目前只能表现为入口消失，还没有用户决策载体
4. 后续实现优先级应是：
   - 先补状态输出
   - 再补自动修复与用户决策编排
