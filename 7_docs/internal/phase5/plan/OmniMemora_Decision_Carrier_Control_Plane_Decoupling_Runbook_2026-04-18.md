---
doc_id: RUNBOOK-DECISION-CARRIER-DECOUPLING-2026-04-18
title: OmniMemora Decision Carrier / Control-Plane Decoupling Runbook
owner: arch-lead
reviewers: [product-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-DECISION-CARRIER-DECOUPLING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Decision Carrier / Control-Plane Decoupling Runbook

## 一、当前状态

- 当前阶段：`Decision Carrier / Control-Plane Decoupling`
- 当前 gate：`Track B / 第十四批逻辑解耦已落地`
- 工作区健康：`绿色`
- 当前分支：`master`

## 二、固定规则

- 每个 track 先做 bounded scan，再做实现
- 行为验证继续绑定验证对象登记文档
- 文档净化与实现并行执行，不积累到阶段尾部
- 已完成 track 的中间控制文档立即归档或删除

## 三、Track A: Decision/Control Bounded Scan

### 输入

- [OmniMemora Decision Carrier / Control-Plane Decoupling Bounded Scan](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Decision_Carrier_Control_Plane_Decoupling_Bounded_Scan_2026-04-18.md)
- [OmniMemora 验证对象登记与验收记录](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)

### 动作

- 固定 decision carrier / control-plane / runtime capability 的当前入口
- 识别 phase5.5 遗留文档中可归并结论
- 产出唯一 active bounded scan 文档

### 停止条件

- 若扫描结果要求重启 phase5.5 既有 Track A/B/C，则停止并回到计划层

## 四、Track B: 逻辑解耦与接口边界

### 动作

- 将 `gateway/status`
- `gateway/decision/*`
- user-decision-required action carrier

统一标为 decision/control carrier 责任

### 验收

- capability 相关语义不再承载 decision carrier 结论
- 文档与代码入口定义一致
- [x] 第一批低风险逻辑解耦已落地：runtime `gateway/status` 与 `gateway/decision/*` 的文件承载逻辑已从 gateway handler 中抽离为独立 control-carrier store
- [x] 第二批低风险逻辑解耦已落地：runtime `gateway/status` 与 `gateway/decision/*` 的 HTTP handler 已抽离为独立 control-carrier surface，`routes.go` 不再承载该入口实现
- [x] 第三批低风险逻辑解耦已落地：runtime dashboard 中的 user-decision-required 呈现与动作脚本已抽离为独立 control-carrier dashboard 片段
- [x] 第四批低风险逻辑解耦已落地：runtime server wiring 中的 control-carrier route 注册已独立成 `registerControlCarrierRoutes(...)`
- [x] 第五批低风险逻辑解耦已落地：runtime low-frequency install layer 的 `/agents/control*` route wiring 已独立成 `registerInstallControlRoutes(...)`
- [x] 第六批低风险逻辑解耦已落地：runtime bootstrap/internal metrics 承载已独立成 `registerBootstrapRoutes(...)` 与 bootstrap surface
- [x] 第七批低风险逻辑解耦已落地：runtime operator dashboard 主 surface 已独立成 `operator_dashboard_surface.go` 与 `registerOperatorDashboardRoutes(...)`
- [x] 第八批低风险逻辑解耦已落地：runtime bootstrap/control 状态已独立成 `bootstrap_state.go`，不再由 `Server` 主结构直接承载
- [x] 第九批低风险逻辑解耦已落地：operator dashboard 对 gateway status / action script 的直接消费已收敛为统一 control-carrier fragment
- [x] 第十批低风险逻辑解耦已落地：`/` 的 operator-facing redirect surface 已独立成 `root_surface.go` 与 `registerRootRoutes(...)`
- [x] 第十一批低风险逻辑解耦已落地：MCP startup error 状态已独立成 `mcp_state.go`，不再由 `Server` 主结构直接承载
- [x] 第十二批低风险逻辑解耦已落地：MCP session registry 已独立成 `mcp_transport_state.go`，不再由 `Server` 主结构直接承载
- [x] 第十三批低风险逻辑解耦已落地：MCP metrics / counter state 已独立成 `mcp_metrics_state.go`，不再由 `Server` 主结构直接承载
- [x] 第十四批低风险逻辑解耦已落地：MCP protocol types 与 tool response helpers 已独立成 `mcp_protocol.go`

## 五、Track C: 最小 decision carrier 承载实现

### 动作

- 在不新开正式产品入口的前提下，为 `runtime dead` 提供最小控制承载
- 先逻辑解耦，再决定是否需要更轻量宿主

### 验收

- `runtime dead + uninstall` 可成立
- `runtime dead + disable-route` 可成立

## 六、Track D: 候选实例与极端故障验证

### 动作

- 使用隔离 `HOME` 与候选实例
- 重点验证极端故障而非日常 happy path

### 验收

- 所有关键极端故障路径写入验证记录
- 不影响真实用户配置

## 七、文档净化动作

- 活跃面只保留：
  - 当前执行计划
  - 当前 runbook
  - 当前验证记录
  - 当前主线专题文档
  - 必要的 sidecar/prep 文档
- phase5.5 已完成的中间 track 文档移入 archive
- phase5.5 已完成的旧计划/runbook 移入 archive
- archive 文档不再从 phase5 入口页当作 active docs 互链

## 八、当前下一步

- [x] 建立本阶段唯一 bounded scan 文档
- [x] 完成 phase5.5 中间 track 文档归档
- [x] 压薄 phase5 入口活跃文档面
- [x] 开始 `Track B`：固化 decision/control carrier 与 runtime capability 的逻辑边界
- [x] 将 runtime internal plane 中的 control-carrier 责任与 capability 责任拆成更清晰的模块入口
- [ ] 继续 `Track B`：识别并外移仍混在 runtime lifecycle / operator dashboard 总装配中的剩余 decision/control 语义，重点转向更小的 bootstrap/lifecycle 装配边界
