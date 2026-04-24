---
doc_id: PLAN-CONTROLLED-BETA-NEXT-STEP-2026-04-23
title: OmniMemora Controlled Beta Next Step Engineering Plan
owner: product-arch
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-23
depends_on:
  - PLAN-CONTROLLED-BETA-RELEASE-V1-2026-04-23
  - GOV-AUDIT-SCHEME-001
supersedes: []
last_verified_commit: ""
---

# OmniMemora Controlled Beta Next Step Engineering Plan

**Status:** active  
**Type:** roadmap 外受控 beta + 本机 truth 修补执行线  
**Goal:** 把“轻量对外试用”与“本机直接反馈链修顺”收敛为一条可连续执行的工程主线  
**Phase Note:** 不新增 roadmap phase，不改 `ROADMAP.md` 正式 phase 编号

---

## 1. 主线目标

本主线只做两件事，并且固定主次顺序：

1. 让少量真实用户可以从 `https://doloclaw.com/download` 下载、试用、报错
2. 把本机 `Claude Code / Codex / OpenClaw -> 18011 -> request evidence -> 5173` 的直接反馈链修到可信

这不是一次“beta 运营扩张”，也不是返回基础治理线。

这是一条以**真实错误、真实 request、真实 evidence** 驱动下一轮产品修正的工程线。

### Product North Star

`OmniMemora 的目标是在不侵入、不降质的前提下，把用户跨窗口、跨实例的必要上下文压缩成可验证、可追溯、可控制的最小 token 投入。`

---

## 2. 固定边界

### 2.1 本批必须坚持

- `5173` 仍是用户控制入口
- `18011` 仍是唯一产品数据入口
- `8765` 仍是内部 memory plane
- 对外分发仍只使用 `https://doloclaw.com/download`
- 反馈入口默认只收敛到同域名支持邮箱
- 本批只修最影响判断的 truth surface，不做 `5173` 全量重构
- 本批只扩 `Claude Code / Codex / OpenClaw`，不做 agent marketplace

### 2.2 本批明确不做

- 不开源
- 不做公开社区投放
- 不做公开 issue 收集
- 不做复杂 CRM / 工单 / 用户账号体系
- 不做完整多实例管理
- 不做更多 agent 家族扩张
- 不做压缩策略大改；先验证负面影响 gate

---

## 3. 执行原则

### 3.1 Reality 隔离

每个批次都必须分别记录：

- `repo reality`: 代码与文档是否完成
- `running reality`: `5173 / 18011 / 8765` 与下载页当前在线行为是否完成
- `user-path reality`: 真实用户或本机真实客户端是否能完成下载、接入、发请求、反馈

不得把代码阅读结论和 running reality 混写成一个“已完成”判断。

### 3.2 Promotion 约束

凡是触及以下目录并准备进入 running reality，必须走 `tools/promotion/promotion.sh`：

- `4_core/local-runtime`
- `5_connectors/adapter`
- `6_console/demo-dashboard`

本主线默认只做**单批单主断点推进**。若某批验证失败，不并行修多个面。

### 3.3 Workspace 风险门槛

- `<= 8` 未提交文件：允许正常推进
- `9-12`：只做当前批，不扩新面
- `13-15`：优先收口记录与清理
- `> 15`：默认停止扩面

若触及 ingress / runtime / control API / routing / deployment path，即使文件数未超阈值，也按高风险批处理。

---

## 4. 当前基线（2026-04-23）

已成立：

- `doloclaw.com/download` 已上线 controlled beta 下载页
- beta 包、`SHA256SUMS.txt`、closed beta 文案已存在
- 当前反馈字段口径已经固定为 `version / platform / request_id / error_code / steps`
- `5173` 已有 `Agent Control`、`Live Request Flow`、`Request Evidence` 基础面
- `request_evidence` 已是下半区证据面的后端 truth source
- AccessPlan actual enforcement 已完成 repo 修补、runtime restart-truth 修补与 non-Codex running validation 闭环

当前缺口：

- runtime agent detection 仍是家族级粗探测，`rescan` 只是重新返回列表，未体现真实本机变体
- `Claude Code` 本机变体/包装链仍可能“机器上存在但产品里搜不到”
- 压缩负面影响尚未通过当前主线对象的最小对照 gate
- Codex is product-compatible in principle, but protected/deferred as a local validation client.
- 轻量外触达（Batch 5）尚未启动

## 4.1 Batch A-B Execution Snapshot (2026-04-23)

### Batch A

**Result:** pass

- `support@doloclaw.com` 已作为 controlled beta 支持邮箱口径进入发行脚本、下载页和反馈入口
- `doloclaw.com/download` 已提供预填 "Report an issue" 动作
- `5173` 已提供基于真实 request evidence 的反馈按钮

### Batch B

**Result:** pass (closed by Batch 4)

已验证的真实 CLI 请求：

- 默认 Claude Code
  - profile: `~/.claude/settings.json`
  - request_id: `b9e9708bfa94`
  - route: `/llm/v1/messages`
  - request evidence: available
  - judgement: `acceptable with caveat`
- Claude Code `cc-haha`
  - profile: `~/.claude/cc-haha/settings.json`
  - request_id: `14675f1f0f95`
  - route: `/llm/v1/messages`
  - request evidence: available
  - judgement: `acceptable with caveat`
- Codex
  - profile: default Codex CLI
  - request_id: `7ca36c16c4b7`
  - route: `/v1/responses`
  - request evidence: available
  - judgement: `acceptable`

本批已完成的实现修补：

- Claude attach 现在不仅写 `memory.provider=omnimemora`，也会把 `ANTHROPIC_BASE_URL` 指向 `http://127.0.0.1:18011/llm`
- `/v1/responses` 现在会持久化 meter，因此 Codex 请求可进入 `request_evidence`
- 已完成 `runtime+adapter` promotion，并在 running reality 下复验

**Batch 4 关闭的 truth caveat：**

- `cc-haha` 现在正确归类为 family-aggregate truth，control card 带有 `scope_note` 明确说明独立 profile 不会作为单独控制卡出现
- `/agents/control` 对 `codex_cli` 的 `traffic_truth` 现在正确反映 `real_request_observed`（当 `real_meter_count > 0` 时）
- `5173` 前端消费后端返回的 `identity_scope` 和 `scope_note`，不再自行推导 profile 语义

**Batch 4 修改的文件：**

- `5_connectors/adapter/application/status_read_model.py`：
  - `derive_traffic_truth()` 修复 non-openclaw 家族的优先级
  - `build_control_cards()` 添加 `identity_scope` 和 `scope_note`
  - 新增 `_derive_scope_note()` 辅助函数
- `6_console/demo-dashboard/src/types.ts`：添加 `identity_scope` 和 `scope_note` 字段
- `6_console/demo-dashboard/src/components/AgentsDashboard.tsx`：渲染 `scope_note`
- `5_connectors/adapter/__tests__/test_status_read_model.py`：新增测试

**Batch B 最终结论：**

CLI/product-path verified，control truth aligned within family-scope boundary。

### D1 Non-Codex Closeout Snapshot (2026-04-24)

**Result:** pass

- 范围固定为：
  - Claude Code default
  - Claude Code `cc-haha`
  - OpenClaw
- Codex live validation 继续排除在该 D1 gate 之外（该 gate 只覆盖非-Codex 客户端验证）

已成立的 running/user-path 结果：

- Claude default：
  - real request + `request_evidence` pass
- Claude `cc-haha`：
  - family-scope contract preserved
  - no standalone control card
- OpenClaw：
  - post-restart aligned request: `21c8ad3c8dd8`
  - `request_evidence` pass
  - control card aligned:
    - `traffic_truth=real_request_observed`
    - `last_request_at=2026-04-23T17:19:22.300286Z`
    - `integration_truth=attached_with_backup`

本轮关键结论：

- 先前 OpenClaw control/evidence mismatch 的主因是 adapter promotion restart-truth 不足
- `tools/promotion/promotion.sh` 现已要求 adapter pre/post fingerprint 发生真实变化，不能再只靠 API 可达判定 promotion success
- D1 non-Codex 现已收口；下一条执行线转为 Batch 3 non-Codex negative-impact gate

证据记录：

- `OmniMemora_D1_NonCodex_Promotion_Record_2026-04-24.md`
- `OmniMemora_D1_NonCodex_Claude_UserPath_Record_2026-04-24.md`
- `OmniMemora_D1_NonCodex_OpenClaw_UserPath_Record_2026-04-24.md`
- `OmniMemora_D1_OpenClaw_Minimal_Fix_Record_2026-04-24.md`
- `OmniMemora_D1_Restart_Truth_Repair_Record_2026-04-24.md`
- `OmniMemora_D1_NonCodex_Closeout_Note_2026-04-24.md`

### Batch 3 Non-Codex Negative-Impact Gate Snapshot (2026-04-24)

**Result:** conditional pass

范围：

- Claude Code default
- Claude Code `cc-haha`
- OpenClaw
- Codex deferred to a separate sub-batch

已完成的对照方式：

- baseline:
  - route disabled through `/agents/control`
  - request evidence remained queryable
  - request status presented as `bypassed`
- product path:
  - route enabled through `/agents/control`
  - request evidence remained queryable
  - request status presented as `warning` with non-zero savings evidence

非-Codex结论：

- Claude Code default: pass
- Claude Code `cc-haha`: pass
- OpenClaw: pass
- aggregate gate: `conditional pass`

保留 `conditional` 的原因：

- request path 本身未观察到明显负面影响
- 但 `/agents/control` 路由切换在执行窗口内表现出明显延迟，因此不把本轮写成 full pass

证据记录：

- `OmniMemora_Batch3_NonCodex_Negative_Impact_Gate_2026-04-24.md`

### AccessPlan Projection Layer Snapshot (2026-04-24)

**Result:** pass (projection layer scope)

已成立：

- `18011` ingress/application 侧可生成并持久化 `identity + access_plan` projection
- `request_evidence` 可稳定呈现 `request.identity` 与顶层 `access_plan`
- legacy `tenant/user` 聚合语义未被新 `tenant_id` 破坏
- `adapter+ui` promotion 后 adapter fingerprint 已换代
- OpenClaw live request 在 running reality 下可回查 `identity/access_plan`
- OpenClaw control truth 最终对齐为 `real_request_observed`
- Codex 未进入本批 live gate（protected/deferred boundary preserved）
- Codex is product-compatible in principle, but protected/deferred as a local validation client.

精确定义：

`Identity Spine + AccessPlan projection is available in meter/request_evidence and verified in running reality; runtime multi-domain read/write enforcement remains a later batch.`

证据记录：

- `OmniMemora_AccessPlan_Projection_Layer_Closeout_2026-04-24.md`

### AccessPlan Runtime Evidence Repo Snapshot (2026-04-24)

**Result:** repo reality advanced; running reality pending

已成立（repo-only, commit `fad9498`）：

- planned `access_plan` 已接入 adapter -> runtime `/memory/search`/`/memory/write` 调用链
- runtime 返回的 `enforcement_trace` 已回收并写入 meter
- `request_evidence` 已可分离呈现 planned `access_plan` 与 actual `enforcement_trace`
- legacy meter 仍保持兼容；当 runtime trace 缺失时，actual enforcement 明确标注 unavailable

固定口径：

`Repo reality: planned AccessPlan is wired into runtime calls and actual enforcement_trace is captured into meter/request_evidence. Running reality: promotion and non-Codex live validation remain pending.`

证据记录：

- `OmniMemora_AccessPlan_Runtime_Evidence_Repo_Sync_2026-04-24.md`

### AccessPlan Actual Enforcement Running Validation Snapshot (2026-04-24)

**Result:** Passed for non-Codex running validation

闭环链路：

- `8975395` repo repair: adapter preserved runtime enforcement trace in evidence
- `51b268a` runtime restart truth repair: promotion verified runtime process rollover
- `69f6f49` running revalidation passed: non-Codex actual enforcement evidence complete

验证对象：

- Claude Code default: `941a65ec4c90`
- Claude Code `cc-haha`: `5fd005303f09`
- OpenClaw: `89e922878065`

已成立：

- promotion restart-truth precondition passed for runtime and adapter
- all three non-Codex objects produced live product-path requests
- all three request_ids are queryable in `request_evidence`
- all three meters contain planned `access_plan` plus actual `actual_enforcement` / `enforcement_trace`
- no target emitted `actual_enforcement.status=unavailable`
- `/agents/control` did not materially contradict request evidence

边界：

- no Codex install/run/live validation
- no new UI/product logic changes
- `5173` remains display/control only, not data logic
- Codex product-compatible in principle; local validation protected/deferred

固定口径：

`AccessPlan actual enforcement passed for non-Codex running validation. Historical failure records are not rewritten; the later restart-truth repair and running revalidation supersede the previous pending/failure state.`

证据记录：

- `OmniMemora_AccessPlan_Actual_Enforcement_Running_Revalidation_After_Restart_Repair_2026-04-24.md`

### Token Saving Effectiveness Gate Snapshot (2026-04-24)

**Result:** Passed for non-Codex token-saving effectiveness gate

Gate record commit:

- `ba46b22 docs(phase6): record token saving effectiveness gate`

Validation objects and savings:

- Claude Code default `5b827a546f74`: saved `124`
- Claude Code `cc-haha` `e9bd3b614702`: saved `124`
- OpenClaw `86c8bea8faf4`: saved `2519`

Boundary:

- no code changes
- no promotion
- no Codex validation
- no UI/data-logic expansion

### Product North Star Evidence Closeout (2026-04-24)

**Result:** Passed for non-Codex product north-star evidence

Gate commits:

- Token saving effectiveness: `ba46b22`
- Quality no-regression: `06bd9e5`
- Non-interference: `eb4a6e2`

Boundary:

- non-Codex only
- no Codex install/run/live validation
- no UI/data-logic expansion
- no thick memory-product expansion

### Evidence Reliability Hardening Snapshot (2026-04-24)

Commit:

- `fc8d658 test(adapter): harden evidence reliability contracts`

Protected contracts:

- planned `access_plan` visibility
- planned/actual separation
- unavailable actual trace fallback
- meter/request_evidence consistency
- token-saving readability
- quality/non-interference template recordability

Boundary:

- repo-only tests/docs
- no promotion/live validation
- no Codex validation
- no UI/data-logic expansion

### Current Gate Override (2026-04-24)

- `Codex is product-compatible in principle, but protected/deferred as a local validation client.`
- 本文第 5-10 节中凡是要求 Codex 进入测试链/验收链的条目，视为历史原始计划基线，不代表当前执行 gate。

---

## 5. 主线拆批

本主线固定拆成五个批次，必须按顺序推进。

### Batch 0: Support Channel Baseline

**目标**

- 把反馈入口从私人邮箱切到同域名支持邮箱
- 让下载页、发行脚本、安装包说明统一引用同一个支持地址

**代码范围**

- `6_console/control-entry/worker.js`
- `4_core/local-runtime/scripts/release/build_release.sh`
- `4_core/local-runtime/scripts/release/publish_beta_release.py`
- `4_core/local-runtime/scripts/release/README.txt`
- `4_core/local-runtime/scripts/release/KNOWN_ISSUES.txt`
- `4_core/local-runtime/scripts/release/RELEASE_NOTES.txt`
- `4_core/local-runtime/scripts/release/BETA_TERMS.txt`
- `7_docs/internal/phase6/plan/OmniMemora_Controlled_Beta_Release_v1_2026-04-23.md`

**非代码操作**

- 在 Cloudflare Email Routing 建立 `support@doloclaw.com`
- 转发到当前实际收信邮箱
- 保存一条 operator record：目标地址、转发地址、创建时间、验证时间

**交付物**

- 下载页显示 `support@doloclaw.com`
- 构建脚本默认支持邮箱切换为 `support@doloclaw.com`
- 安装包文本材料与下载页口径一致
- controlled beta 文档更新为同域名支持邮箱

**验收**

- `https://doloclaw.com/download` 页面可见同域名邮箱
- 重新构建出的 release 文本包不再包含私人邮箱
- `mailto:` 打开后主题固定到 beta support / feedback

**停住条件**

- Cloudflare Email Routing 未完成
- 下载页与发行包文案出现双口径

### Batch 1: Minimal Feedback Action

**目标**

- 下载页和 `5173` 都提供“最小立即可用”的预填反馈动作
- 不引入新的服务端工单系统

**代码范围**

- `6_console/control-entry/worker.js`
- `6_console/demo-dashboard/src/App.tsx`
- `6_console/demo-dashboard/src/components/ContextComparison.tsx`
- `6_console/demo-dashboard/src/components/CallChainViz.tsx`
- `6_console/demo-dashboard/src/types.ts`

**实现要求**

- 下载页增加显式 “Report an issue” 入口
- `5173` 在 request evidence 可见区域增加 “提交反馈” 按钮
- 按钮默认走 `mailto:` 预填，不先做 POST intake
- 预填字段最少包含：
  - `version`
  - `platform`
  - `request_id`
  - `error_code`
  - `agent_family`
  - `steps`

**数据来源**

- `request_id / agent_family`: `request_evidence.request`
- `error_code`: `request_evidence.status` 或现有系统状态面
- `version`: 当前 UI 可见版本或 release 版本常量
- `platform`: 浏览器/本机环境最小识别

**交付物**

- 下载页可一键发出预填反馈邮件
- `5173` 在选中请求后可一键生成预填反馈
- 无请求证据时按钮进入受限态，不能伪造 diagnostics

**验收**

- 从 `5173` 选中一条真实请求后，反馈动作带出可信 `request_id`
- 若请求有错误，反馈动作带出 `error_code`
- 未选中请求时，不显示伪 diagnostics 字段

**停住条件**

- 前端需要“猜” request truth 才能拼 feedback
- 反馈按钮与后端 evidence 字段对不上

### Batch 2: Local Agent Detection and Access Repair

**目标**

- 修掉“本机真实可用客户端存在，但 rescan/控制面看不见”的真实缺口
- 让 `Claude Code / Codex / OpenClaw` 至少进入可解释、可验证的控制链

**代码范围**

- `4_core/local-runtime/internal/attach/detect.go`
- `4_core/local-runtime/api/agent_control.go`
- `4_core/local-runtime/internal/attach/attach.go`
- `4_core/local-runtime/internal/cli/validate.go`
- `6_console/demo-dashboard/src/components/AgentsDashboard.tsx`
- 必要时补充对应测试

**实现要求**

- detection 不再只依赖“标准 config 文件存在”这一条
- 对 `Claude Code` 增加更贴近本机 reality 的检测信号：
  - CLI in PATH
  - wrapper / launcher 存在
  - `~/.claude` 变体配置存在
  - 能明确给出未发现原因
- `rescan` 不能继续只是“重新返回原列表”；至少要返回：
  - 新增/移除的 family 或 instance 变化
  - 未发现原因或提示
- UI 至少能解释：
  - detected
  - installed
  - active
  - route truth
  - 为何未发现

**本批不做**

- 不做真正多实例管理
- 不做 agent marketplace
- 不把 transient wrapper 单独升级为长期产品对象

**交付物**

- `Claude Code` 本机变体能被发现，或 UI 中明确给出未发现原因
- `Codex` 能进入相同检测/接入链
- `OpenClaw` 继续维持现有 attach truth，不被回退

**验收**

- `POST /agents/control/rescan` 后结果与本机 shell/config reality 对齐
- `5173` 中 agent card 不再出现“机器上明明有，但产品完全看不见”
- 检测失败时能给出可执行解释，而不是静默 `detected=false`

**停住条件**

- 修检测时误改 attach/uninstall 语义
- 为了适配变体而破坏现有 `OpenClaw` 稳定 attach truth

### Batch 3: Compression Negative-Impact Gate

**目标**

- 在扩更多 agent 前，先验证产品路径不会明显伤害结果

**验证对象**

- `OpenClaw`
- `Claude Code`
- `Codex`

**验证方式**

- 每个 agent 至少跑 1 条真实任务
- 每条任务至少保留两组结果：
  - baseline: 关闭产品压缩/路由或等价 passthrough 路径
  - product path: 开启产品压缩/路由后的真实路径

**强制记录字段**

- `agent_family`
- `task_name`
- `baseline result`
- `product-path result`
- `request_id`
- `error_code`
- `request evidence`
- `negative impact judgement`

**判定规则**

- 若错误显著增加，判定 fail
- 若任务完成能力明显变差，判定 fail
- 若只有个别 agent 受损，冻结该 agent 扩测，不冻结全线

**交付物**

- 一份最小验证记录，按 agent 分桶列出真实请求与判断

**验收**

- 三个 agent 各至少一条真实请求证据
- 每条都能回查 `request_id`
- 若失败，存在唯一主断点，不并行开第二条实现线

**停住条件**

- 只做主观描述，没有 request evidence
- 混淆 baseline 与 product path

### Batch 4: 5173 Truth Repair for Testing and Feedback

**目标**

- 只修会直接误导当前测试与反馈的 truth surface

**代码范围**

- `5_connectors/adapter/application/status_read_model.py`
- `6_console/demo-dashboard/src/App.tsx`
- `6_console/demo-dashboard/src/components/AgentsDashboard.tsx`
- `6_console/demo-dashboard/src/utils/familyNormalization.ts`
- 必要时补充 `types.ts` / `api.ts`

**固定优先级**

1. Agent control truth
2. Error / request evidence truth
3. 首页/汇总卡片中的明显误导项

**实现要求**

- `5173` 关键状态优先消费后端 truth source
- 前端不再自行推导关键 control truth
- 凡是可以从 `/debug/request_evidence`、`/agents/control`、现有 system status contract 获取的，就不在前端补脑
- `rescan` 反馈、agent card、request evidence、feedback action 必须使用同一组 canonical 字段

**本批不做**

- 不重写 overview 全部统计
- 不重做整体视觉
- 不扩 skill advisory 以外的新模块

**交付物**

- agent card 的关键状态与本机 reality 对齐
- feedback 按钮带出的 diagnostics 与 request evidence 对齐
- overview 仅修明显误导当前测试判断的卡片/标签

**验收**

- `rescan` 后 UI 状态与 runtime control API 返回一致
- 选中请求后的反馈动作与 request evidence 内容一致
- 当前测试人员不会再被首页或 agent card 明显带偏

**停住条件**

- 为修显示而新增第二套 truth 口径
- 为修 overview 重新打开整套 dashboard 改版

### Batch 5: Lightweight Outreach Run

**目标**

- 在前四批通过后，开始最小真实用户投放

**操作范围**

- GitHub 定向小范围手动触达
- 每轮 `3-10` 个真实用户
- 仅给 `https://doloclaw.com/download`

**准入条件**

- Batch 0-4 全部完成
- 支持邮箱链路可用
- 本机主反馈链可用
- 至少一个 beta 包与下载页文案同步

**执行要求**

- 只找高度相关用户/讨论场
- 不在无关 repo 批量留言
- 不暴露源码仓
- 不开公开 issue 支持面

**每轮记录**

- 触达对象链接
- 触达日期
- 是否回应
- 是否下载
- 是否出现安装/连接/请求错误
- 是否产生 `request_id / error_code / evidence`

**停住条件**

- 反馈链尚未可用
- 本机验证链还不能稳定产出 request evidence

---

## 6. 默认实施顺序

默认顺序固定为：

1. Batch 0: 同域名支持邮箱统一
2. Batch 1: 下载页 + `5173` 预填反馈动作
3. Batch 2: 本机 `Claude Code / Codex / OpenClaw` 检测与接入修补
4. Batch 3: 压缩负面影响 gate
5. Batch 4: `5173` truth 最小修补
6. Batch 5: GitHub 定向小范围触达

不得把 Batch 5 提前到 Batch 2/3 之前。

---

## 7. 验收矩阵

### 7.1 Beta 分发验收

- `doloclaw.com/download` 可访问
- 下载页显示 `support@doloclaw.com`
- 下载页可一键发起预填反馈
- 不暴露源码仓
- 不开启公开 issue 支持面

### 7.2 本机 agent 验收

- `Claude Code` 被发现，或未发现原因可解释
- `Codex` 被发现并进入测试链
- `OpenClaw / Claude Code / Codex` 各至少一条真实请求
- 每条真实请求都有：
  - `request_id`
  - `error_code`（如有）
  - `request evidence`

### 7.3 Compression Gate 验收

- 开启产品路径后，没有明显错误增加
- 没有出现“任务完成能力显著变差”的直观负反馈
- 若某 agent 受损，已冻结该 agent 的继续扩测

### 7.4 5173 Truth 验收

- `rescan` 后本机真实 agent 显示正确
- agent card 关键状态不再违背本机现实
- 从 `5173` 发起反馈时带出的 diagnostics 可信
- 不要求所有统计卡片完美，只要求不误导当前测试和反馈

---

## 8. 执行记录要求

本主线每个批次至少产出一条记录，记录模板固定为：

```md
## Batch Record

- batch: <0|1|2|3|4|5>
- date: <YYYY-MM-DD>
- validation target: <repo reality|running reality|user-path reality>
- scope: <本批范围>
- result: <pass|conditional pass|fail>
- primary breakpoint: <none|具体断点>
- evidence:
  - <command / endpoint / screenshot / request_id / doc>
- next action:
  - <下一步>
```

若是运行面验证，必须写明：

- 观察端口
- 观察命令
- 请求 ID
- 结论适用范围

---

## 9. 默认责任分工

- **主线程执行者**：保留 gate 决策、truth 判定、promotion、收口结论
- **低风险辅助工作**：允许用于文案统一、记录补齐、对照表整理
- **禁止委托的事项**：
  - promotion 结论
  - running reality 最终判定
  - negative-impact gate 结论
  - `5173 / 18011 / 8765` 主 truth 决策

---

## 10. 完成定义

本主线只有在以下条件同时成立时才算完成：

1. 下载页、beta 包、支持邮箱口径统一为同域名支持入口
2. 下载页与 `5173` 都能发出最小预填反馈
3. `Claude Code / Codex / OpenClaw` 的本机测试链可解释且可产出真实 request evidence
4. 压缩负面影响 gate 已完成，且未发现未处理的明显伤害
5. `5173` 当前用于测试与反馈的 truth surface 已不再误导
6. 至少完成一轮 `3-10` 个真实用户的 GitHub 定向触达，并回收到真实错误或真实确认

只有满足以上条件，才允许讨论扩大分发范围或扩到更多 agent。
