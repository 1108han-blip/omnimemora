# ROADMAP_CURRENT.md

**Status:** FINAL
**Source of Truth:** Global Product Blueprint
**Last Updated:** 2026-04-09
**Role:** Blueprint 的时间演进

---

# 一、Roadmap 原则

每个 Phase 必须回答：

1. 验证哪条宪法
2. 完善哪一层能力
3. 建立哪种商业能力

---

# 二、Phase 结构

## Phase 0（已完成）

目标：建立 Control Plane 概念，分离 Control / Memory

对应宪法：Control Plane ≠ Memory Plane

---

## Phase 1（当前）

目标：**验证本地 Runtime 可独立运行**

**状态**: ✅ PASSED (2026-04-09)

验证：

- 本地模式无需 API key ✅
- connector 默认接入本地 runtime ✅
- memory 读写可在本地完成 ✅
- scope 隔离默认生效 ✅ (agent/workspace/tenant)
- runtime 产生 metering events ✅
- SQL scope enforcement 验证通过 ✅

对应宪法：

- Local First
- Default Isolated / Explicit Sharing
- Single Runtime

### Phase 1.2 任务

- `/memory/delete` 端点
- `/memory/search` 端点
- `/scope/context` 端点
- 统一 scope 来源优先级文档口径

---

## Phase 2

目标：**Bootstrap Layer 成为产品入口**

验证：

- 下载 → 双击 → 完成（无手动配置）
- scope 配置可用
- 单用户多 agent 隔离跑通
- workspace 共享跑通
- connector 自动注册

对应宪法：

- Bootstrap Layer 为第一公民
- Local First / Cloud Optional

### Phase 2a 任务（Ranking Search）

**状态**: ✅ PASSED (2026-04-09)

- scope-aware keyword recall
- ranking（text match + recency + access boost）
- top-k 截断
- FTS5 / BM25 fallback

对应宪法：Scope Governance

### Phase 2b 任务（Lightweight Context Assembly）

**状态**: ✅ PASSED (2026-04-09)

- 可选 `assemble_context` 开关
- excerpt 提取（命中窗口 / 短文本 / 首段 fallback）
- top-k excerpt merge
- token budget 控制（trim → drop → keep 1）
- 真实 `raw_tokens / compressed_tokens / saved_tokens` 计算
- response 扩展兼容（`context` 字段，`results` 结构不变）
- scope enforcement 不回退
- metering schema migration 自动补列（`raw_tokens`, `assembled_hits`）

对应宪法：Token Savings 是核心产品能力

---

### Phase 2c 任务（Context Strategy Layer）

**状态**: ✅ PASSED (2026-04-09)

- Strategy 接口（可插拔）
- 3 种策略：`topk_excerpt` / `recency_boost_select` / `diversity_select`
- `context_strategy=auto` 自动选择
- `context_mode`（precise/balanced/aggressive）
- `ctxAssembler` 统一入口

对应宪法：Context Strategy 仅轻量选择与压缩

---

### Phase 2c.5 任务（Post-Audit Fix & Documentation Lock）

**状态**: ✅ PASSED (2026-04-09)

- honest token accounting（`raw_tokens = sum(item.tokens)`，禁止反推）
- `assemble_context=false` 全 0（诚实口径）
- `context_strategy=auto` 记录 resolved strategy（response & metering 一致）
- `efficiencyScore` 增加 token floor（防止短文本偏置）
- cache 禁用并标注（pending scope-isolation audit）
- 旧版 `assembleContext()` 完全移除
- 所有文档对齐到 DECISION_LEDGER.md

对应宪法：DECISION_LEDGER.md 为最高事实源

---

## Phase 3

目标：**Productization & Adoption**

Focus:
- Observability
- Integration simplicity
- Stability

Explicitly NOT:
- Retrieval pipeline evolution
- Agent orchestration
- Query understanding

验证：

- Console 展示总 token savings
- 今日 / 本周 / 本月 token savings
- 按 workspace breakdown
- 按 agent breakdown
- token savings 趋势图
- scope 模型完整（user / workspace / agent / custom）
- sharing mode 完整（isolated / shared / shared_read_only）

对应宪法：

- Token Savings 是核心产品能力
- Scope Governance

---

## Phase 4

目标：**Metering → Billing 闭环成立**

验证：

- token savings 可计费
- usage 可观测
- billing plan 可切换
- Pro / Enterprise 商业模式跑通

对应宪法：

- Billing
- token savings + usage + governance

---

## Phase 5

目标：**Cloud Control 增强能力（可选）**

验证：

- 本地 Runtime + Cloud Control Plane 组合可运行
- policy / metering / billing 可在云端增强
- 不影响本地独立运行

对应宪法：

- Cloud Optional

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

Roadmap 只能由 Blueprint 推导，不允许反向定义产品
