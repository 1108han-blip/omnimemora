---
doc_id: SCAN-PHASE5_5-TRACKB-COMBINED-RECOVERY-2026-04-18
title: OmniMemora Phase 5.5 Track B 联合恢复策略 Bounded Scan
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on:
  - PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18
  - SPEC-PHASE5_5-TRACKB-SELFHEAL-2026-04-18
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Track B: 联合恢复策略 Bounded Scan

## 可复用

- [5_connectors/adapter/track_b_state_machine.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/track_b_state_machine.py)
  - 已固定状态集合、状态来源约束、终态锁定与 override 合法转移
- [5_connectors/adapter/track_b_orchestrator.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/track_b_orchestrator.py)
  - 已具备从 backend/runtime 健康推导顶层状态的单一入口
- [5_connectors/adapter/track_b_status.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/track_b_status.py)
  - 已具备统一状态文件读写与 override 应用能力
- [start.sh](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/start.sh)
  - 已具备 runtime restart、gateway restart、恢复窗口、退避与用户决策文件消费
- [4_core/local-runtime/api/gateway_status.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/api/gateway_status.go)
  - 已具备 runtime internal plane 的只读状态承载面
- [4_core/local-runtime/api/gateway_decision.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/api/gateway_decision.go)
  - 已具备 `disable-route` / `uninstall` 的 runtime 决策入口

## 必须避开

- 把“能力层故障自动降级”和“入口层故障用户决策”混成一个统一失败终态
- 让 `gateway-exit-monitor` 与 `runtime-restart-monitor` 互相覆盖 `user-decision-required`
- 让联合恢复策略直接改写 backup/restore 语义
- 在联合恢复编排中顺手改动 `llm_proxy.py` 的 compile / passthrough 路径
- 把 runtime internal plane 暗中升级成正式产品入口

## 需要清理

- 当前 `start.sh` 负责较多运行时编排，但“能力层故障”和“入口层故障”的协同优先级仍然分散在脚本逻辑里
- `track_b_orchestrator.py` 当前偏重状态推导，尚未定义联合恢复的优先级规则
- runtime `/gateway/status` 目前暴露状态结果，但还没有单独的“联合恢复策略 contract”说明
- `disable-route` 与 `uninstall` 的后续恢复窗口虽然存在，但还没有单独定义“用户动作后，哪些恢复仍允许自动继续”

## 当前实现入口

- [start.sh](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/start.sh)
  - 当前真正的联合恢复原型入口
- [5_connectors/adapter/track_b_state_machine.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/track_b_state_machine.py)
  - 当前状态优先级与终态约束入口
- [5_connectors/adapter/track_b_orchestrator.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/track_b_orchestrator.py)
  - 当前观测态聚合入口
- [4_core/local-runtime/api/gateway_status.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/api/gateway_status.go)
  - 当前 runtime 面向 UI/operator 的联合状态读取入口
- [4_core/local-runtime/api/gateway_decision.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/api/gateway_decision.go)
  - 当前用户动作进入联合恢复流程的入口

## 扫描结论

Track B 下一步不该继续加新接口，而应补一层“联合恢复优先级 contract”：

1. 当 `gateway_health=healthy` 且 `capability_health=degraded|unreachable` 时：
   - 继续走能力层自动修复或自动降级
   - 不进入 `user-decision-required`

2. 当 `gateway_health=unreachable` 时：
   - 入口层故障优先级高于能力层故障
   - 先走 gateway recovery window
   - 只有窗口耗尽后才进入 `user-decision-required`

3. 当用户已经做出 `disable-route` 决策后：
   - 允许 gateway 恢复继续进行
   - 但恢复后的顶层状态应回到 `healthy + routing_effective=false`
   - 不再因能力层故障升级为顶层故障

4. 当用户选择 `uninstall` 后：
   - 可允许 gateway 继续拉起，以保持 internal/operator surface 可用
   - 但产品接入语义已退出，不应再回到产品增强路径

因此，Track B 的下一步实现应是：

- 先定义“联合恢复优先级与用户动作后状态收敛”的 contract
- 再决定是否需要把这层 contract 提升成独立 orchestrator / supervisor 模块
