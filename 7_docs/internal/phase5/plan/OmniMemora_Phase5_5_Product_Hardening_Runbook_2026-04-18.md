---
doc_id: RUNBOOK-PHASE5_5-PRODUCT-HARDENING-2026-04-18
title: OmniMemora Phase 5.5 Product Hardening Runbook
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Product Hardening Runbook

## 一、文档定位

本文件是 [OmniMemora Phase 5.5 Product Hardening 执行计划](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Phase5_5_Product_Hardening_执行计划_2026-04-18.md) 的执行版清单。

当前入口文档：

- [云端小工程](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/云端小工程.md)
- [Phase 5 Docs Index](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/README.md)
- [OmniMemora 验证对象登记与验收记录](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)

## 二、当前状态

- 当前阶段：`Phase 5.5 / Product Hardening`
- 当前 gate：`Track B / 联合恢复优先级 contract`
- 工作区健康：`绿色`
- 当前分支：`master`
- 当前推进焦点：
  - [x] `Track A` 收口批完成
  - [x] `Track B` 入口层与能力层故障状态机主干完成
  - [x] `Track B` 联合恢复策略 bounded scan 完成
  - [x] `Track C` bounded global scan 完成
  - [x] `Track C` 第一批低风险迁移完成
  - [x] `Track C` 第二批中风险表层迁移完成
  - [x] `Track C` 第三批低风险子集迁移完成
  - [x] `Track C` 阶段性完成，`trial / internal admin surface` 后置

## 三、固定总规则

- [x] 每个 track 开始前必须完成 bounded global scan
- [x] scan 结果必须写清四栏：
  - [x] `可复用`
  - [x] `必须避开`
  - [x] `需要清理`
  - [x] `当前实现入口`
- [x] scan 完成后，只允许做定向核对
- [x] 行为验证必须继续绑定验证对象登记文档
- [x] `A/B` 已达到进入 `Track C` 准备与小批迁移的前置条件

## 四、Track A: 8765 对外接口收口

### 当前输入

- [Track A Bounded Scan](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Phase5_5_TrackA_8765_Bounded_Scan_2026-04-18.md)

### 当前结论

- [x] 当前产品主文档已把 `8765` 定义为内部 plane
- [x] runtime README 与 runtime API 已承认 `8765` 仅内部使用
- [x] adapter 控制面已经以 `18011 -> runtime(/agents/control)` 代理方式存在
- [x] 第一批对外文档残留已开始收口：插件 README 已改为只展示 `18011` 为用户可见入口
- [x] runtime README 已补 internal-only 说明并去除失效 `CANONICAL_FACTS.md` 引用
- [x] `README.txt` 中 `8765/dashboard` 的对外展示已收掉
- [x] runtime `README.txt` 已改写为 operator/internal runtime 说明，不再保留“安装即生效 / 自动接入”旧叙事
- [x] runtime CLI 输出已把 dashboard 明确标成 internal/operator surface，并补出 `18011` 作为产品入口
- [x] runtime `README.md` 已明确 runtime HTTP contract 只用于 internal/operator verification，不能当产品控制面证据
- [x] demo dashboard README 已明确 `5173 -> 18011` 的产品边界，排除 `:8765` 直连解释
- [x] runtime dashboard 标题与 handler 注释已收敛为 internal/operator surface，不再暗示产品主控制面
- [x] runtime `/agents/control*` 注释已明确其仅为 low-frequency install layer
- [x] adapter runtime backend/factory 注释已明确 `:8765` 只是 internal runtime plane，不是第二产品入口
- [x] archive / 审计记录之外，活跃文档面未再发现把 `8765` 误写成产品入口或用户直接控制面的叙事
- [ ] runtime HTTP contract 仍需继续检查是否有可被误抬升的内部控制接口叙事

### 下一步动作

- [x] 第一轮收敛剩余对外文档中的 `8765` 展示面
- [x] 列出需要继续保留的内部 runtime HTTP contract
- [x] 列出应从“正式产品接口叙事”中退场的 `8765` 路径
- [x] 为 `Track A` 建立过渡兼容说明
- [x] 收紧 runtime 自身 README/CLI 文案中的 internal/operator 边界

### 停止条件

- 若发现 `18011` 当前仍无法承接某个被用户依赖的正式对外行为，暂停收口

### 回滚条件

- 若收口动作会破坏当前 `18011 -> runtime` 内部调用链，回滚该动作并补兼容说明

## 五、Track B: 自动自愈 / 自动拉起状态机

### 当前输入

- [Track B Bounded Scan](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Phase5_5_TrackB_自愈状态机_Bounded_Scan_2026-04-18.md)
- [Track B 联合恢复策略 Bounded Scan](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Phase5_5_TrackB_联合恢复策略_Bounded_Scan_2026-04-18.md)
- [Track B 自愈状态机定义](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Phase5_5_TrackB_自愈状态机定义_2026-04-18.md)

### 当前结论

- [x] install/uninstall 与 backup/restore 语义已固定
- [x] `route=off -> passthrough` / `route=on -> compile path` 已有候选实例证据
- [x] 当前已有健康检查入口：adapter `/health`、runtime `/health`
- [x] 自愈状态机定义文档已建立
- [x] `18011` 入口故障与能力层故障已在文档层分层建模
- [x] `user-decision-required` 已有正式状态定义
- [x] `B2` 候选实例故障基线已建立
- [x] `Track B` 最小统一状态输出接口已落地
- [x] 已明确 `restore backup` 当前只存在于显式 `uninstall/detach` 路径
- [x] `Track B` override 写入入口与控制面消费路径已落地
- [x] `Track B` 能力层最小自愈闭环已在候选实例上成立
- [x] `Track B` 入口层故障最小 `user-decision-required` 承载面已在候选实例上成立
- [x] `Track B` 已具备最小用户动作接口（disable-route via runtime internal plane）
- [x] `Track B` 已具备最小用户动作接口（uninstall via runtime internal plane），且与 `route state -> off` 语义对齐
- [x] `Track B` 已具备最小 UI 动作承载（runtime dashboard -> /gateway/decision/*）
- [x] `Track B` 已把最小状态写入责任方落到运行时状态面（`status_source / transition_reason`）
- [x] `Track B` 已把 `user-decision-required` 固定成自动化不可自行清除的终态
- [x] `Track B` 已把 `route=off` 下的能力层故障收敛为诊断信号，不再升级成顶层故障
- [x] `Track B` 最小编排器已落地，`main / status_api / agent_control_api` 统一走单一状态决策入口
- [x] `Track B` 状态机本体已拆成独立模块，状态、来源、转移与 override 应用不再混在读写层
- [x] `Track B` 已具备“用户动作 -> 决策文件 -> gateway 重启编排 -> 成功/失败转移”的完整高层编排路径（当前为代码与单元级成立）
- [x] 候选实例重测阻塞已定位为 adapter 运行依赖缺失，`start.sh` 已补前置依赖预检
- [x] 候选实例已补齐 `gateway failure -> user action -> gateway restart` 的在线闭环证据
- [x] `start.sh` 已补 runtime 二进制陈旧检测，避免源码更新后继续复用旧 runtime 造成假阴性
- [x] gateway 入口故障的自动修复窗口与有限重试策略已落地
- [x] 自动修复关闭分支已具备候选实例证据，并能输出明确 `transition_reason`
- [x] `window_expired` 与 `attempts_exhausted` 两类失败分支已具备候选实例证据
- [x] 退避策略已落地为指数回退并受上限约束
- [x] 联合恢复优先级 contract 已写入状态机定义

### 下一步动作

- [x] 固定状态机输入源：入口健康、能力层健康、route 状态、attach 状态
- [x] 明确自动修复动作边界
- [x] 明确自动降级到 passthrough 的触发条件
- [x] 明确 `user-decision-required` 的最小状态定义
- [x] 建立 healthy / capability failure / gateway failure 的候选实例基线
- [x] 明确 `user-decision-required` 的最小接口输出
- [x] 明确禁止自动 restore backup 的代码约束点
- [x] 明确 override 写入约束与控制面消费路径
- [x] 建立 capability failure -> recovering-gateway -> healthy 的候选实例证据
- [x] 建立 gateway failure -> user-decision-required 的候选实例证据
- [x] 建立 gateway failure -> disable-route 用户动作的候选实例证据
- [x] 建立 gateway failure -> uninstall 用户动作的候选实例证据
- [x] 建立 gateway failure -> dashboard 最小动作承载的候选实例证据
- [x] 建立 gateway failure -> `status_source / transition_reason` 责任边界的候选实例证据
- [x] 建立 gateway failure -> user action decision file -> gateway restart orchestration 的代码与单元级证据
- [x] 定位候选实例重测阻塞的真实根因，并将其从状态机逻辑问题中分离出来
- [x] 在 adapter 运行依赖满足后，补一条 gateway failure -> user action -> gateway restart 的候选实例级闭环记录
- [x] 避免 runtime 二进制陈旧导致候选实例验证读取旧行为
- [x] 建立 gateway failure -> auto recovery window -> healthy 的候选实例证据
- [x] 建立 gateway failure + self-heal disabled -> user-decision-required 的候选实例证据
- [x] 建立 gateway failure + recovery window expired -> user-decision-required 的候选实例证据
- [x] 建立 gateway failure + retry attempts exhausted -> user-decision-required 的候选实例证据
- [x] 联合恢复策略 bounded scan 已完成

### 下一步候选

- [ ] 将联合恢复优先级 contract 落到实现：
  - `gateway unreachable` 优先于能力层故障
  - `disable-route` 后恢复到 `healthy + routing_effective=false`
  - `uninstall` 后不再回到产品增强路径
- [ ] 暂不继续扩新接口或新状态字段

### 停止条件

- 若实现方案需要自动 uninstall/detach 才能成立，则停止并回到计划层

### 回滚条件

- 若实现引入“故障处理自动替用户退出产品”，立即回滚

## 六、Track C: 18011 纯接入编排层拆分准备

- [x] Track C bounded global scan 已完成
- [x] 当前 `18011` / compile / strategy / V2 遗产散点已完成第一轮责任盘点
- [x] Track C 责任边界图与迁移顺序草案已建立
- [x] `main.py` slimming candidate 清单已建立
- [x] 第一批低风险迁移已落地：`startup probe` 与 `quota-path observation helper` 已从 `main.py` 外移
- [x] 第二批中风险表层迁移已落地：`MCP/SSE surface` 与 diagnostics surface 已从 `main.py` 外移为独立 router
- [x] 第三批定向风险判断已完成：`token-savings / meter query surface` 可继续小批次迁移，`trial / internal admin surface` 后置
- [x] 第三批子集已落地：`token-savings / meter query surface` 已从 `main.py` 外移为独立 router
- [x] 当前不进入高耦合迁移
- [x] `Track C` 当前按阶段性完成收口；`trial / internal admin surface` 不并入当前入口瘦身批次

## 七、Track D: 候选实例补强验证

- [ ] 暂不扩大验证面
- [ ] 仅在 `Track A/B` 需要新证据时补充候选实例记录

## 八、批次顺序

1. `A1` 文档/接口叙事收口批
2. `A2` runtime 内部 contract 标注批
3. `B1` 故障状态机建模批
4. `B2` 候选实例故障场景验证批
5. `C1` 责任边界图批

当前下一步：`Track B` 已完成联合恢复优先级 contract；应决定是否把这三条优先级规则落到 `start.sh / orchestrator / runtime decision flow`
