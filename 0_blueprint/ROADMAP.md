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

# 三、禁止偏移

Roadmap 不允许：
- ❌ 引入 storage 作为核心
- ❌ 绑定某个 backend
- ❌ 绕过 control plane
- ❌ 强制云端为默认路径
- ❌ 削弱 Token Savings UI
- ❌ 跳过 Scope 治理落地

---

# 四、版本治理

Roadmap 只能由 Constitution 推导，不允许反向定义产品
