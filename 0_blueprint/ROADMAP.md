# ROADMAP.md

**Status:** FINAL
**Role:** 阶段目标描述 - 只描述阶段目标，不定义架构

---

# 一、Roadmap 原则

每个 Phase 必须回答：
1. 验证哪条宪法
2. 完善哪一层能力
3. 建立哪种商业能力
4. 如何满足 LLM 最小暴露原则（仅结果进入模型）

Roadmap 愿景一致性锚点：

> Keep it on, or things get worse.

---

# 二、Phase 结构

## Phase 0（已完成）

**目标**：建立 Control Plane 概念，分离 Control / Memory

**对应宪法**：Control Plane ≠ Memory Plane

---

## Phase 1（已完成）

**目标**：验证本地 Runtime 可独立运行

**状态**：✅ PASSED (2026-04-09)

**验证**：
- 本地模式无需 API key ✅
- connector 默认接入本地 runtime ✅
- memory 读写可在本地完成 ✅
- scope 隔离默认生效 ✅ (agent/workspace/tenant)
- runtime 产生 metering events ✅
- SQL scope enforcement 验证通过 ✅

**对应宪法**：
- Local First
- Default Isolated / Explicit Sharing
- Single Runtime

---

## Phase 2（已完成）

**目标**：Bootstrap Layer 成为产品入口

**状态**：✅ PASSED (2026-04-09)

**验证**：
- Phase 2a: scope-aware keyword recall + ranking ✅
- Phase 2b: Lightweight Context Assembly + token savings ✅
- Phase 2c: Context Strategy Layer（可插拔策略）✅
- Phase 2c.5: Post-Audit Fix & Documentation Lock ✅

**对应宪法**：
- Token Savings 是核心产品能力
- Context Strategy 仅轻量选择与压缩
- Minimal Exposure to LLM（Context 是结果，不是决策过程）

---

## Phase 3（已完成）

**目标**：Productization & Adoption

**Focus**：
- Observability
- Integration simplicity
- Stability

**Explicitly NOT**：
- Retrieval pipeline evolution
- Agent orchestration
- Query understanding

**验证**：
- Console 展示总 token savings ✅
- 今日 / 本周 / 本月 token savings ✅
- 按 workspace breakdown ✅
- 按 agent breakdown ✅
- token savings 趋势图 ✅
- scope 模型完整（user / workspace / agent / custom）✅
- sharing mode 完整（isolated / shared / shared_read_only）✅

**对应宪法**：
- Token Savings 是核心产品能力
- Scope Governance
- Minimal Exposure to LLM（策略/候选/评分/控制面元信息不入 LLM）

**收口日期**：2026-04-20（commit `7894b89`）

---

## Phase 4（已完成）

**目标**：Metering → Billing 闭环成立

**验证**：
- token savings 可计费 ✅
- usage 可观测 ✅
- billing plan 可切换 ✅
- Pro / Enterprise 商业模式跑通 ✅

**对应宪法**：
- Billing
- token savings + usage + governance

**收口日期**：2026-04-20（commit `045c3a5`）

---

## Phase 5（已完成 — 可选）

**目标**：Cloud Control 增强能力（可选）

**验证**：
- 本地 Runtime + Cloud Control Plane 组合可运行 ✅
- policy / metering / billing 可在云端增强 ✅
- 不影响本地独立运行 ✅

**对应宪法**：
- Cloud Optional

**收口日期**：2026-04-20（commit `d9959e1`）

> Phase 5 is explicitly optional. The repo defaults to local-first operation. Cloud control enhancements are only pursued when explicitly prioritized.

---

## Phase 6（内部治理工作流，已收口）

**目标**：把受控 beta、本地 promotion、运行证据、cloud-local sync、桌面分发表面收口为可操作产品线。

**定位**：Phase 6 是 internal historical workstream，不作为产品价值能力扩张阶段。

**验证**：
- promotion workflow 和 evidence routing 已收口 ✅
- desktop beta 受控发布链路已收口 ✅
- `18011` / `8765` / Desktop GUI 边界已固定 ✅
- `5173` 已降为 legacy/dev surface ✅

**对应宪法**：
- Local First
- Explicit User Control
- Product Path Truth

**收口日期**：2026-05-13

---

## Phase 7（当前主线）：Structured Compile MVP

**目标**：真正实现 OmniMemora 的协议安全结构化编译能力，在真实 agent 请求中节省 token 和成本，同时保持上游协议语义不变。

**核心验证**：
- 真实用户请求进入 `:18011` 后可被结构化解析、保护、压缩、重建。
- tool graph、role 顺序、tool id、tool result 对应关系不被破坏。
- 结构化编译成功时，`real_input_saved_tokens` 和 compile token delta 均为正。
- passthrough / skipped / structured_compile_success 的真实流量分布可观测。
- 编译热路径只使用本地确定性逻辑，不依赖 LLM summarization、云端策略拉取、历史文件扫描或慢持久化。

**第一批能力**：
- SC-010：真实编译分布统计。
- SC-011：provider tokenizer 或更接近 provider 的 token 估算。
- SC-012：按搜索结果、文件读取、日志、diff、测试输出分型压缩。
- SC-013：匿名最小失败样本机制。
- SC-014：离线候选压缩评估，LLMLingua 类方法不得进入上游前热路径。

**对应宪法**：
- Token Savings 是核心产品能力
- Minimal Exposure to LLM
- Transparent Forwarding
- MVP first; token saving first; no complexity expansion

**当前计划入口**：`7_docs/internal/structured_compile/README.md`

---

## Phase 8（下一正式阶段）：Token Intelligence Lite

**目标**：把 OmniMemora 从“能节省 token 的编译层”推进到“能解释 token 花费、定位浪费、推荐优化并证明实际节省的本地智能分析层”。

Phase 8 不是普通 token 统计。它必须回答：

- Token 花在哪；
- 为什么花；
- 哪些浪费；
- 如何优化；
- 哪些 Agent 最烧钱；
- 哪些 Prompt 最低效；
- 哪些上下文重复；
- 哪些 Memory 命中失败；
- 哪些模型性价比最低；
- 哪些工作流 ROI 最高。

**核心验证**：

- 本地轻量入口可审计真实 OpenAI/Anthropic-compatible 请求，不要求先安装完整桌面包或付费云服务器。
- `doloclaw.com`、Cloudflare、Railway 仍是可用产品资源，但 Phase 8 首发不得假设云端容量、存储成本、隐私边界和运行费用已经被验证；云端 Token Intelligence 托管必须在本地 MVP 证明价值后单独评估。
- 记录 provider/model/request/block-level token breakdown，并标注 confidence class。
- 默认不存 raw prompt、完整 tool output 或完整 provider response。
- 小型用户数据库只保存 compact audit/user-pattern metadata，并提供查看、删除、过期、导出路径。
- Potential Savings 可从真实请求中计算，Actual Savings 可与 structured compile 的真实节省闭环。
- User Pattern Lite 当前只记录可减少重复提示的轻量用户习惯，不做用户画像；未来若要升级为用户画像，必须作为新阶段重新通过用户控制、隐私、存储、禁用、导出和删除设计。
- Token Intelligence recommendation 必须连接到 concrete optimization path：structured compile、prompt reduction、memory repair、model/workflow selection 或 User Pattern Lite。

**第一批能力**：

- TI-001：local proxy / CLI audit-only 轻量入口。
- TI-002：provider-aligned token counters and confidence labels。
- TI-003：block-level token spend breakdown。
- TI-004：waste detectors for duplicate context, tool-result/log inflation, retry waste, weak prompt ROI, and memory miss signals。
- TI-005：small SQLite audit/user data plane with retention/delete/export controls。
- TI-006：Potential Savings report。
- TI-007：Actual Savings proof by connecting recommendations to Phase 7 structured compile.
- TI-008：optional local MCP companion for agents to query audit and optimization summaries.

**对应宪法**：

- Token Savings 是核心产品能力
- Token Intelligence 是 Token Savings 的解释层和商业价值面
- Minimal Exposure to LLM
- Local First
- User Pattern Lite Boundary
- MVP first; token saving first; no complexity expansion

**计划入口**：`7_docs/internal/token_intelligence/README.md`

---

# 三、禁止偏移

Roadmap 不允许：
- ❌ 引入 storage 作为核心
- ❌ 绑定某个 backend
- ❌ 绕过 control plane
- ❌ 强制云端为默认路径
- ❌ 削弱 Token Savings UI
- ❌ 把 Token Intelligence 降级为普通 usage dashboard
- ❌ 在 Phase 8 内把 User Pattern Lite 偷偷扩张为用户画像或隐藏行为监控
- ❌ 跳过 Scope 治理落地

---

# 四、版本治理

Roadmap 只能由 Constitution 推导，不允许反向定义产品
