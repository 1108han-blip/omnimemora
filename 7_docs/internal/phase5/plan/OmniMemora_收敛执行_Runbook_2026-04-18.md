---
doc_id: RUNBOOK-PHASE5-CONVERGENCE-2026-04-18
title: OmniMemora 收敛执行 Runbook
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5-CONVERGENCE-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora 收敛执行 Runbook / Checklist

## 一、文档定位

本文件是 [OmniMemora 收敛执行计划（管理里程碑版）](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_收敛执行计划_2026-04-18.md) 的执行版清单。

用途：

- 把 `M1 -> M2 -> M3 -> M4 -> M5` 拆成可逐日推进的执行项
- 为每个阶段给出输入、动作、输出、停止条件、回滚条件
- 避免继续混用主基线、候选现实和运行实例

说明：

- 本文件不是新的产品定义文档
- 本文件也不是逐命令脚本
- 它是“每日推进 checklist + gate 记录载体”
- 云端边界仍由 [7_docs/internal/phase5/plan/云端小工程.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/云端小工程.md) 承担；若两者表述冲突，以本文件对应的收敛执行计划为准
- `Gate B` 的正式记录载体见 [OmniMemora 验证对象登记与验收记录](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)
- 工作区切批方案见 [OmniMemora 工作区分批切割清单](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_工作区分批切割清单_2026-04-18.md)

## 二、总执行规则

## 当前状态（截至 2026-04-18）

- `M1`：**已完成**
- `M2`：**已完成**
- `M3`：**部分实现已存在，但未正式收敛**
- `M4`：**关键闭环已补上，但验收记录未独立沉淀**
- `M5`：**配置语义已补上，但仍需正式验收记录**
- 工作区健康：**红色**
  - 当前分支：`checkpoint/llm-proxy-usage-fix`
  - 当前未提交项：`34`
  - 当前结论：暂停实现扩面，先做工作区治理
- A 批状态：**已完成内容核对，未完成物理收口**
  - 当前物理边界：`6` 个已修改文件 + `5` 个未跟踪文件
  - 当前判断：可作为第一个单独收口对象

### 必须遵守

- [ ] 只按 `M1 -> M2 -> M3 -> M4 -> M5` 顺序推进
- [ ] 每完成一个里程碑，必须留下产出物或验收记录
- [ ] 未通过 gate，不得进入下一个里程碑
- [ ] 任一阶段若发现“正在验证的实例不是当前指定实例”，立即停止
- [ ] 每条验证记录必须写明：`实例分类 / 实例路径或来源 / 结论适用范围`

### 禁止事项

- [ ] 禁止跳过 `M1 / M2` 直接继续控制面实现
- [ ] 禁止把未提交工作区候选现实当作已完成现实
- [ ] 禁止把 `~/.omnimemora/service/current` 的行为直接等同于当前 repo 行为
- [ ] 禁止把仓库代码阅读结论与外部运行实例行为拼接成同一条“已验证”结论
- [ ] 禁止在本轮把 `8765` 收口或自动自愈实现偷偷并入

### Gate B 记录模板

后续所有涉及行为验证的记录，至少包含以下字段：

- `实例分类`：`仓库候选实例` 或 `外部运行实例`
- `实例路径/来源`：例如当前 repo 工作区，或 `~/.omnimemora/service/current`
- `验证动作`：本次观察或验证实际针对的对象
- `结论适用范围`：只能写“候选成立”或“外部运行实例成立”，不得跨对象外推

---

## 三、阶段 1：M1 主基线冻结

## 目标

固定当前产品真相，消除文档入口失真。

### 输入

- `README.md`
- `0_blueprint/PRODUCT_DEFINITION.md`
- `0_blueprint/DEFAULT_IN_CONTROL_PLANE.md`
- `0_blueprint/ROADMAP.md`
- `9_adr/ADR-0003-interface-access-paths.md`
- `7_docs/internal/phase5/audit/OmniMemora_全面审计与下一步决策方案_2026-04-18.md`

### 执行动作

- [x] 冻结主基线文档集合
- [x] 列出历史/冲突来源文档集合
- [x] 清理 README 中不存在的上位真相引用
- [ ] 统一以下术语：
  - [x] `5173/GUI = 用户控制入口`
  - [x] `18011 = 用户开启产品路由后的唯一产品数据入口`
  - [x] `8765 = 内部 memory plane`
  - [x] `接入` 与 `使用` 为不同层级动作

### 输出

- [x] 主基线清单
- [x] 失效文档清单
- [x] 术语统一口径

### Gate A

- [x] README、产品定义、ADR 不再相互矛盾
- [x] 不再引用不存在的上位真相文件

### 停止条件

- 发现主基线之间仍有未决冲突
- 发现 phase5 现行文档无法承载当前产品口径

### 回滚条件

- 若本阶段修改造成主文档口径更分裂，则回退到上一个一致版本，再重新整理

---

## 四、阶段 2：M2 环境现实对位

## 目标

固定“后续所有验证到底验证谁”。

### 输入

- 当前 repo 工作区
- 当前 dirty worktree
- `~/.omnimemora/service/current`

### 当前冻结结论（2026-04-18）

- [x] 当前在线运行实例来自 `~/.omnimemora/service/current`
- [x] 当前在线运行实例不是从当前 repo 直接启动
- [x] 当前 repo / 当前 dirty worktree 只代表仓库现实与候选现实，不自动代表在线实例现实

### 验证对象分类（最小集合）

- [x] `仓库候选实例`
  - [x] 仅在从当前 repo / 当前工作区显式启动后使用
  - [x] 结论只可写成“候选实例成立/不成立”
- [x] `外部运行实例`
  - [x] 当前默认对象为 `~/.omnimemora/service/current`
  - [x] 结论只可写成“外部运行实例成立/不成立”

### 执行动作

- [x] 确认当前在线实例来源
- [x] 确认当前在线实例是否直接来自本仓库工作区
- [x] 明确后续验证对象：
  - [x] `仓库候选实例`
  - [x] `外部运行实例`
- [x] 写清禁止混验规则
- [x] 为当前阶段后的每一条验证补上实例标签与结论适用范围
- [x] 若验证外部运行实例，在记录中明确写明 `~/.omnimemora/service/current`

### 输出

- [x] 运行来源说明
- [x] 验证对象说明
- [x] 禁止混验规则
- [x] Gate B 验证记录模板被后续阶段沿用
- [x] Gate B 正式记录载体已建立

### Gate B

- [x] 验证命令与实例来源固定
- [x] 不再混用外部运行实例和当前仓库结论
- [x] 每条验证记录都写明实例分类、实例路径/来源、结论适用范围
- [x] 若未显式声明实例对象，该条验证不计入 Gate B 及后续 gate

### 停止条件

- 无法明确在线实例来源
- 行为验证仍然依赖多个对象交叉拼接

### 回滚条件

- 若新增验证步骤继续依赖错误实例，撤销该验证结论，不计入阶段产出

---

## 五、阶段 3：M3 控制面正式化

## 目标

把 `/agents/control*` 从候选现实收敛成正式仓库现实。

### 输入

- adapter control API 候选实现
- runtime control API 候选实现
- dashboard 双开关 UI 候选实现

### 执行动作

- [x] 收敛 `/agents/control`
- [x] 收敛 `/agents/control/install`
- [x] 收敛 `/agents/control/uninstall`
- [x] 收敛 `/agents/control/enable`
- [x] 收敛 `/agents/control/disable`
- [ ] 固定双开关语义：
  - [x] `install/uninstall = 接入层`
  - [x] `enable/disable = 路由层`
- [x] 明确 `attach != route on`
- [x] 明确 `uninstall = restore original config`

### 输出

- [ ] 控制面接口正式契约
- [ ] UI / adapter / runtime 一致口径

### Gate C

- [x] `/agents/control*` 在三层语义一致
- [x] enable/disable 不再只是写状态文件

### 停止条件

- UI、adapter、runtime 对同一动作定义不一致
- enable/disable 无法稳定映射到请求路径行为

### 回滚条件

- 若控制面实现引入“自动 attach”或“默认 route on”，立即回退该变更

---

## 六、阶段 4：M4 路由行为闭环

## 目标

把 route 状态与真实请求路径行为绑定起来。

### 输入

- `18011` ingress
- route state 持久化
- compile path
- passthrough path

### 执行动作

- [x] 验证 `route=on -> compile path`
- [x] 验证 `route=off -> passthrough path`
- [x] 验证 `route=off` 不调用 compile
- [ ] 验证 agent 在 `route=on` 时不可自主绕过
- [ ] 验证 `uninstall -> restore original upstream config`

### 输出

- [ ] 行为闭环验证记录
- [ ] 关键接口验收记录

### Gate D

- [x] `route=off = passthrough`
- [x] `route=on = compile path`
- [ ] `uninstall = restore original upstream config`

### 停止条件

- 行为和状态仍然存在断层
- 仍然只能证明“状态写入”，不能证明“行为切换”

### 回滚条件

- 若 route off 仍残留 compile 副作用，则回退该实现到稳定 passthrough 版本

---

## 七、阶段 5：M5 云端策略语义收敛

## 目标

固定纯本地与云端增强的默认配置语义。

### 输入

- cloud config
- policy loader / flags loader / usage reporter
- phase5 云端工程计划

### 执行动作

- [x] 固定 `纯本地模式 = 默认关闭云端策略更新`
- [x] 固定 `纯本地模式 = 默认不上报数据`
- [x] 固定 `开启云端策略更新 = 默认同意最小必要数据上报`
- [ ] 固定最小数据集合边界
- [x] 固定云端边界为“策略下发，本地执行”

### 输出

- [ ] 云端配置口径
- [ ] 最小数据上报口径
- [ ] 默认值说明

### Gate E

- [x] 纯本地默认不上报
- [x] 开启云端策略更新后最小必要数据上报自动生效
- [ ] 上报范围不超出既定元数据集合

### 停止条件

- 云端配置语义仍然和本地模式混淆
- 数据上报范围无法稳定约束为最小元数据

### 回滚条件

- 若云端增强改动影响产品入口定义或 compile 主路径稳定性，回退到 `cloud disabled` 默认状态

---

## 八、每日推进清单

### Day 1：冻结真相

- [x] 完成 M1
- [x] 进入 M2 前，确认 Gate A 已通过

### Day 2：固定验证对象

- [x] 完成 M2
- [x] 写明后续所有验证以哪个实例为准
- [x] 固化 `外部运行实例 = ~/.omnimemora/service/current`
- [x] 固化“仓库候选实例 / 外部运行实例”二分类
- [x] 进入 M3 前，确认 Gate B 已通过

### M3 入口前冻结清单

进入 `M3` 前，先冻结以下高风险改动面，禁止把它们与一般文档清理或低风险修补混做一批：

- [x] 已是候选实现：
  - `5_connectors/adapter/main.py`
  - `5_connectors/adapter/agent_control_api.py`
  - `5_connectors/adapter/agent_routing_state.py`
  - `5_connectors/adapter/llm_proxy.py`
  - `4_core/local-runtime/api/agent_control.go`
  - `6_console/demo-dashboard/src/api.ts`
  - `6_console/demo-dashboard/src/components/AgentsDashboard.tsx`
- [x] 主要配套：
  - `6_console/demo-dashboard/src/types.ts`
  - `4_core/local-runtime/internal/cli/commands.go`
  - `4_core/local-runtime/api/server.go`
- [x] 最容易污染工作区：
  - `5_connectors/adapter/agent_routing_state.py`
  - `5_connectors/adapter/agent_control_api.py`
  - `4_core/local-runtime/internal/cli/commands.go`

### M3 入口前检查项

- [x] 为相关文件建立“候选实现 / 配套改动 / 高污染风险”三分类
- [x] 明确哪些文件是新文件，哪些文件是在已有脏工作区上继续叠加修改
- [x] 当前结论固定为：信息已足够支持 `M3` 入口风险盘点，但**不足以宣告 M3 已具备正式收敛条件**
- [ ] 确认所有运行与校验都经过 `127.0.0.1:18011`，不绕开产品入口
- [ ] 核对前端 `types.ts` 与后端 `/agents/control*` 字段契约一致
- [ ] 明确 `enable/disable` 只处理 adapter 路由状态，不与 runtime install 状态混淆
- [ ] 验证 `install/uninstall/rescan` 的返回语义与前端展示一致，尤其失败与部分成功分支
- [ ] 检查 `agent_routing_state` 的读写路径仅在必要场景触发，避免测试中频繁改状态文件
- [ ] 确认 `llm_proxy.py` 在禁用场景保持 passthrough，不误入 compile 链路
- [x] 已追加入口风险记录，区分新文件与叠加修改
- [ ] 进入 M3 前追加一条新的实例声明记录，写明本次准备用哪个实例做控制面验收
- [ ] 若无法把控制面文件与其他候选改动切开，则暂停 M3，不继续扩大工作区
- [ ] 若需要新的产品裁决，则停在 M3 入口，不得边做边定

### Day 3：控制面收敛

- [ ] 完成 `/agents/control*` 接口正式化
- [ ] 进入 M4 前，确认 Gate C 已通过

### Day 4：路由闭环验证

- [ ] 完成 route on/off 行为验证
- [ ] 进入 M5 前，确认 Gate D 已通过

### Day 5：云端语义收敛

- [ ] 完成纯本地 / 云端增强默认值收敛
- [ ] 确认 Gate E 已通过

---

## 九、执行完成定义

本 runbook 中任何“完成”，都必须同时满足：

- [ ] 仓库现实成立
- [ ] 当前指定实例验证成立
- [ ] 验证记录中已注明实例分类与结论适用范围

只满足其中一条，不得勾选为完成。

## 十、后续不在本轮处理

以下内容只记录为下一轮入口，不在本 runbook 中继续展开：

- [ ] `8765` 对外接口收口
- [ ] 自动自愈 / 自动拉起的正式实现
- [ ] compile / strategy 从 `18011` 中正式拆出
