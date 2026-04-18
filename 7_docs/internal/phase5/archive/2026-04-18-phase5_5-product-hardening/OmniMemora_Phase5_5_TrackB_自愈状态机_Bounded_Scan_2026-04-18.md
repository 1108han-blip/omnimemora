---
doc_id: SCAN-PHASE5_5-TRACKB-SELFHEAL-2026-04-18
title: OmniMemora Phase 5.5 Track B 自愈状态机 Bounded Scan
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Track B: 自动自愈状态机 Bounded Scan

## 可复用

- [5_connectors/adapter/agent_control_api.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/agent_control_api.py)
  - 已有 runtime `/health` 检查与 `healthy/degraded/unreachable` 粗分层
- [5_connectors/adapter/llm_proxy.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/llm_proxy.py)
  - 已有 `route=off -> passthrough` 与 `route=on -> compile path` 的真实入口
- [4_core/local-runtime/internal/attach/backup.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/internal/attach/backup.go)
  - 已有 install/uninstall 层备份恢复实现
- [start.sh](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/start.sh)
  - 已有 runtime / adapter 启动链与健康等待
- [OmniMemora_验证对象登记与验收记录_2026-04-18.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)
  - 已有 `route on/off`、`install/uninstall -> restore` 的候选实例证据

## 必须避开

- 把 `backup/restore` 混成自动故障回退路径
- 把能力层故障和入口层故障合并成单一“失败就退出产品”
- 让自动化替用户执行 uninstall/detach
- 把真实用户配置作为故障场景测试对象

## 需要清理

- 当前还没有正式的故障状态枚举、状态机文档和 UI 表达
- `agent_control_api.py` 的 `health_state` 只表达 runtime 健康，不足以区分：
  - `18011` 入口存活
  - 能力层故障
  - 用户决策待处理
- `start.sh` 和 runtime 启动链只有“启动成功/失败”，还没有可复用的自愈动作抽象

## 当前实现入口

- [5_connectors/adapter/agent_control_api.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/agent_control_api.py)
  - 当前最接近故障状态入口
- [5_connectors/adapter/llm_proxy.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/llm_proxy.py)
  - 当前最接近自动降级到 passthrough 的数据路径入口
- [start.sh](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/start.sh)
  - 当前最接近自动拉起入口
- [4_core/local-runtime/internal/cli/commands.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/internal/cli/commands.go)
  - 已有 runtime health / start 语义，但偏 CLI 视角
- [4_core/local-runtime/internal/attach/attach.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/internal/attach/attach.go)
  - 当前 backup/restore 的真实边界入口

## 扫描结论

Track B 当前不是“直接写恢复逻辑”，而是先把状态机输入源与动作边界建清：

1. 入口层故障与能力层故障必须分层
2. `route=off -> passthrough` 可以复用为能力层故障的自动降级动作
3. `backup/restore` 必须严格留在 install/uninstall 层
4. 真正缺的不是“恢复原上游实现”，而是：
   - 状态枚举
   - 健康来源整合
   - 用户决策待处理状态
   - 自愈动作的编排入口
