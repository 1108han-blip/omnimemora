---
doc_id: SCAN-DECISION-CARRIER-DECOUPLING-2026-04-18
title: OmniMemora Decision Carrier / Control-Plane Decoupling Bounded Scan
owner: arch-lead
reviewers: [product-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-DECISION-CARRIER-DECOUPLING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Decision Carrier / Control-Plane Decoupling Bounded Scan

## 可复用

- `Track B` 已完成的状态机、联合恢复 contract、用户动作语义
- `Track C` 已完成的 `18011` 入口职责瘦身结论
- 现有 `gateway/status`、`gateway/decision/*`、decision/status/action 文件载体

## 必须避开

- 把 `runtime capability plane` 继续当作最终 decision carrier
- 为解决极端故障而新增第二产品入口
- 在当前阶段同时展开 compile / strategy 大拆分

## 需要清理

- phase5.5 遗留的多份 Track A/B/C 中间文档仍处于活跃目录
- phase5 入口页当前活跃文档面过厚
- prep/track/final 结论散落在多份 active docs 中

## 当前实现入口

- `18011 ingress/orchestration`
- `runtime capability plane`
- `gateway/status`
- `gateway/decision/*`
- `start.sh` 中的 decision/status/action 协调路径
