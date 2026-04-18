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
- 当前 gate：`启动控制层落地`
- 工作区健康：`绿色`
- 当前分支：`master`
- 当前起步目标：
  - [x] phase5.5 管理版计划落地
  - [x] phase5.5 runbook 落地
  - [x] `workspace-governance` skill 写入 bounded global scan 规则
  - [x] `Track A` bounded global scan 初版完成
  - [x] `Track B` bounded global scan 初版完成
  - [ ] 进入 `Track A` 具体实现批次

## 三、固定总规则

- [ ] 每个 track 开始前必须完成 bounded global scan
- [ ] scan 结果必须写清四栏：
  - [ ] `可复用`
  - [ ] `必须避开`
  - [ ] `需要清理`
  - [ ] `当前实现入口`
- [ ] scan 完成后，只允许做定向核对
- [ ] 行为验证必须继续绑定验证对象登记文档
- [ ] `A/B` 未完成前，不进入 `Track C` 的实际拆分

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
- [ ] archive / 审计记录之外，仍需确认是否还有活跃对外文档把 `8765` 误写成产品面
- [ ] runtime HTTP contract 仍暴露可被误抬升的内部控制接口叙事

### 下一步动作

- [x] 第一轮收敛剩余对外文档中的 `8765` 展示面
- [x] 列出需要继续保留的内部 runtime HTTP contract
- [x] 列出应从“正式产品接口叙事”中退场的 `8765` 路径
- [x] 为 `Track A` 建立过渡兼容说明

### 停止条件

- 若发现 `18011` 当前仍无法承接某个被用户依赖的正式对外行为，暂停收口

### 回滚条件

- 若收口动作会破坏当前 `18011 -> runtime` 内部调用链，回滚该动作并补兼容说明

## 五、Track B: 自动自愈 / 自动拉起状态机

### 当前输入

- [Track B Bounded Scan](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Phase5_5_TrackB_自愈状态机_Bounded_Scan_2026-04-18.md)

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
- [ ] 还没有正式的故障状态机实现

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

### 停止条件

- 若实现方案需要自动 uninstall/detach 才能成立，则停止并回到计划层

### 回滚条件

- 若实现引入“故障处理自动替用户退出产品”，立即回滚

## 六、Track C: 18011 纯接入编排层拆分准备

- [ ] 暂不进入实现
- [ ] 只允许做责任盘点和边界图草案

## 七、Track D: 候选实例补强验证

- [ ] 暂不扩大验证面
- [ ] 仅在 `Track A/B` 需要新证据时补充候选实例记录

## 八、批次顺序

1. `A1` 文档/接口叙事收口批
2. `A2` runtime 内部 contract 标注批
3. `B1` 故障状态机建模批
4. `B2` 候选实例故障场景验证批
5. `C1` 责任边界图批

当前下一步：`Track B` 入口层故障的最小 user-decision-required 承载面前置
