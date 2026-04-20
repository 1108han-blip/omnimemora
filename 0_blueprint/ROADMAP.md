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

## Phase 5（当前 — 可选）

**目标**：Cloud Control 增强能力（可选）

**验证**：
- 本地 Runtime + Cloud Control Plane 组合可运行
- policy / metering / billing 可在云端增强
- 不影响本地独立运行

**对应宪法**：
- Cloud Optional

> Phase 5 is explicitly optional. The repo defaults to local-first operation. Cloud control enhancements are only pursued when explicitly prioritized.

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
