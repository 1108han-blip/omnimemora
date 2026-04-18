---
doc_id: SPEC-PHASE5_5-TRACKB-SELFHEAL-2026-04-18
title: OmniMemora Phase 5.5 Track B 自愈状态机定义
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Track B: 自愈状态机定义

## 一、文档定位

本文件定义 Track B 的最小状态机，不直接实现自动拉起逻辑，但固定后续实现不得偏离的故障语义。

本文件只定义：

- 状态
- 输入信号
- 自动动作
- 用户决策入口
- 禁止动作

## 二、状态输入

Track B 的状态机输入固定为四类：

1. `gateway_health`
   - 来源：`18011` 健康检查
   - 目标：判断入口层是否存活

2. `capability_health`
   - 来源：runtime health、compile path 可用性、runtime bridge、策略加载能力
   - 目标：判断产品增强能力是否可用

3. `routing_state`
   - 来源：agent routing state
   - 目标：判断当前是否要求产品增强路径生效

4. `install_state`
   - 来源：runtime `/agents/control*`
   - 目标：判断当前是否仍处于已接入状态

## 三、状态定义

### `healthy`

条件：

- `gateway_health = healthy`
- `capability_health = healthy`

动作：

- 保持当前 `route` 语义
- `route=on` 继续 compile path
- `route=off` 继续 passthrough

补充：

- 当 `route=off` 且 `gateway_health=healthy` 时，即使 `capability_health=degraded|unreachable`，顶层状态仍保持 `healthy`
- 此时能力层故障只作为诊断信息保留，不升级成顶层故障，因为用户当前显式处于 passthrough

### `degraded-capability`

条件：

- `gateway_health = healthy`
- `capability_health = degraded|unreachable`
- 自动修复尝试失败或短时间内不可恢复
- 且 `route=on`

动作：

- 自动降级为产品效果旁路
- 进入 `passthrough`
- 保持 install 状态不变
- UI 静默提示能力层故障

禁止：

- 不得自动 restore backup
- 不得自动 uninstall/detach

### `recovering-gateway`

条件：

- `gateway_health = degraded|unreachable`
- 系统判定入口层仍可自动修复

动作：

- 自动尝试拉起或恢复 `18011` 及必要依赖
- 修复成功则回到 `healthy` 或 `degraded-capability`

### `user-decision-required`

条件：

- `gateway_health = unreachable`
- 自动修复失败，或超过恢复窗口

动作：

- 暴露用户决策状态
- 默认不改 install 状态
- 默认不动 backup/restore
- 等待用户明确选择：
  - `disable route`
  - 或 `uninstall/detach + restore backup`

禁止：

- 不得自动替用户退出产品
- 不得自动执行 restore backup

## 四、固定状态转移

1. `healthy -> degraded-capability`
   - 入口健康，但能力层不可恢复

2. `healthy -> recovering-gateway`
   - 入口层故障，但系统判定可自动修复

3. `recovering-gateway -> healthy`
   - 入口恢复成功，且能力层健康

4. `recovering-gateway -> degraded-capability`
   - 入口恢复成功，但能力层仍不可用

5. `recovering-gateway -> user-decision-required`
   - 入口恢复失败

6. `degraded-capability -> healthy`
   - 能力层恢复成功

7. `user-decision-required -> healthy`
   - 用户选择保留接入并入口恢复成功

8. `user-decision-required -> route-off-installed`
   - 用户选择仅关闭路由

9. `user-decision-required -> detached`
   - 用户选择 uninstall/detach

注：

- `route-off-installed` 与 `detached` 是用户动作结果，不是自动故障终态
- 一旦进入 `user-decision-required`，自动来源不得自行清除该状态；只有显式用户动作、手动 override 或测试 override 才允许把状态带离该终态

## 五、自动化动作上限

Track B 自动化只允许做：

- 健康检测
- 自动修复尝试
- 自动降级到 passthrough
- 标记 `user-decision-required`

Track B 自动化明确不允许做：

- `RestoreBackup()`
- `DetachAgent()`
- 任何会修改用户原配置并退出产品接入的动作

## 六、最小接口要求

后续实现至少需要一个统一状态输出，供 UI / gateway / 诊断面共享。

最小字段建议：

- `status`
  - `healthy`
  - `degraded-capability`
  - `recovering-gateway`
  - `user-decision-required`
- `status_source`
  - `observed-health`
  - `runtime-restart-monitor`
  - `gateway-exit-monitor`
  - `manual-override` / `internal-test`（仅调试）
- `transition_reason`
- `gateway_health`
- `capability_health`
- `routing_effective`
- `user_action_required`
- `recommended_action`
- `error_code`

## 七、状态写入责任方

Track B 的状态写入责任方固定为：

1. `observed-health`
   - 来源：adapter 基于实时 backend health 的默认推导
   - 可产生：`healthy`、`degraded-capability`

2. `runtime-restart-monitor`
   - 来源：`start.sh` 中的 runtime 自愈监控
   - 可产生：`recovering-gateway`、`degraded-capability`、`healthy`

3. `gateway-restart-monitor`
   - 来源：`start.sh` 中的 gateway 自动重启窗口
   - 可产生：`recovering-gateway`、`healthy`
   - 仅用于入口层自动修复窗口，不得直接写 `user-decision-required`

4. `gateway-exit-monitor`
   - 来源：`start.sh` 中的 adapter/gateway 退出监控
   - 可产生：`user-decision-required`
   - 该状态一旦写入，后续自动来源不得自行清除

5. `manual-override` / `internal-test`
   - 仅用于调试、测试或内控验证
   - 不作为正式产品运行时责任方

## 九、自动修复窗口

入口层故障的自动修复按“窗口 + 次数”约束执行：

- `gateway` 进程退出后，先进入自动修复窗口
- 在窗口内按有限次数重启 `18011`
- 任一次重启成功即回到 `healthy`
- 只有自动修复窗口耗尽后，才允许进入 `user-decision-required`

这条规则的目的，是把“可自动恢复的瞬时入口故障”和“需要用户决策的不可恢复故障”分开，避免系统过早打断用户。

## 八、与现有实现的绑定关系

- `agent_control_api.py`
  - 当前已有 `healthy/degraded/unreachable` 粗状态，可作为入口
- `llm_proxy.py`
  - 当前已有 `route=off -> passthrough` 行为，可作为能力层降级动作
- `start.sh` 与 runtime 启动链
  - 当前可作为自动拉起原型入口
- `attach/backup.go`
  - 明确只属于 install/uninstall 层，不进入自动故障回退
