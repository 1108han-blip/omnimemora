---
doc_id: DESIGN-DECISION-CARRIER-TRACKC-2026-04-18
title: OmniMemora Decision Carrier / Control-Plane Decoupling Track C 最小承载路径设计
owner: arch-lead
reviewers: [product-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on:
  - PLAN-DECISION-CARRIER-DECOUPLING-2026-04-18
  - RUNBOOK-DECISION-CARRIER-DECOUPLING-2026-04-18
supersedes: []
last_verified_commit: ""
---

# OmniMemora Decision Carrier / Control-Plane Decoupling Track C 最小承载路径设计

## 一、目标

Track C 只解决一个最小结构问题：

- 在 `runtime dead` 时，仍然给 `disable-route` / `uninstall` 提供正式承载路径
- 不新增第二产品入口
- 不新增复杂常驻服务
- 不把 capability plane 和 decision carrier 再次绑死

## 二、当前结构事实

当前已完成：

- runtime internal plane 中的 control-carrier store/surface/dashboard/wiring 已独立成模块边界
- `gateway/status` 与 `gateway/decision/*` 的 HTTP surface 已从 capability surface 中抽离
- `start.sh` 已能消费 `gateway_decision.json` 与 `track_b_status.json`

当前仍未解决：

- `runtime dead + uninstall`
- `runtime dead + disable-route`

原因不是单点 bug，而是当前用户动作仍物理依赖 runtime HTTP 面。

## 三、最小实现方向

不引入新服务，采用三段式最小承载路径：

1. `shared decision action core`
   - 把 `disable-route` / `uninstall` 的动作核心从 runtime HTTP handler 中抽离
   - 新 carrier 只负责采集动作，不重复实现动作逻辑

2. `offline control carrier entry`
   - 新增本地离线入口，优先放在 runtime CLI，而不是新常驻服务
   - 该入口只执行：
     - 读取 family / action
     - 调用 shared decision action core
     - 持久化决策文件与 route state
   - 不承担 capability plane 健康判断

3. `supervisor recovery hint`
   - 当 `runtime dead` 且 control-carrier HTTP 面不可用时，supervisor 输出明确人工动作提示
   - 指向统一离线入口，而不是要求用户手工改配置文件

## 四、边界定义

### 4.1 保留不变

- `18011` 仍是唯一正式产品入口
- `8765` 仍是内部 memory plane
- runtime HTTP internal plane 仍是正常情况下的 user-decision carrier

### 4.2 新增但不升格为产品入口

- CLI/offline decision carrier 仅作为极端故障 fallback
- 其定位是 operator recovery path，不是新的产品入口
- 不参与日常 happy path

### 4.3 明确禁止

- 不新增第三个常驻 daemon
- 不新增新的用户产品端口
- 不把 `start.sh` 继续扩成新的业务能力平面
- 不在 Track C 同时做真实客户端恢复或 `5173` 修复

## 五、建议实现批次

### Batch C1: Shared Decision Action Core

目标：

- 从 runtime HTTP surface 中抽出 `disable-route` / `uninstall` 的动作核心
- 后续 HTTP carrier 与 offline carrier 共同复用

范围：

- `control_carrier_surface.go`
- 新的 action core 文件
- 既有 tests

### Batch C2: Offline Carrier CLI Entry

目标：

- 给 `runtime dead` 场景提供本地恢复命令入口

当前约束：

- 当前 `4_core/local-runtime/main.go` 仍以 `serve` 为主路径
- `internal/cli/commands.go` 已有 attach/detach/start/stop/status 语义，但尚未作为稳定 CLI dispatch 入口正式暴露
- 因此 C2 的第一步不是直接加恢复命令，而是先补最小 command router，使 offline carrier 有正式宿主

建议形式：

- runtime CLI 新增极小子命令，例如：
  - `omnimemora recover disable-route <family>`
  - `omnimemora recover uninstall <family>`

要求：

- 不依赖 runtime HTTP 健康
- 直接调用 shared decision action core
- 输出清晰结果

### Batch C3: Supervisor Hint / Manifest

目标：

- 在 runtime dead 场景中，给出确定性的下一步动作

建议形式：

- `start.sh` 在进入该极端分支时输出明确命令提示
- 必要时写 recovery hint 文件，但不额外引入新状态平面

### Batch C4: Candidate Validation

目标：

- 用隔离候选实例验证：
  - `runtime dead + disable-route`
  - `runtime dead + uninstall`

## 六、验收标准

- `disable-route` 动作核心不再只存在于 runtime HTTP handler 内
- `uninstall` 动作核心不再只存在于 runtime HTTP handler 内
- 在 runtime dead 时，用户仍有正式且简单的动作入口
- 不新增第二产品入口
- 不要求用户手动改配置文件

## 七、当前结论

Track C 的最小承载路径优先采用：

- 共享动作核心
- CLI/offline fallback entry
- supervisor 提示

而不是：

- 新常驻服务
- 新 dashboard
- 新产品入口

这是当前架构下复杂度最低、风险最低、可连续验证的方案。
