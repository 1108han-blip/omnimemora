# DECISION_LEDGER.md

**Status:** ACTIVE
**Purpose:** 记录所有关键架构决策，确保决策不被丢失，所有文档必须与此一致
**Last Updated:** 2026-04-09

---

# 一、决策总览

| # | Decision | Layer | Must Sync To | Status | 日期 |
| --- | --- | --- | --- | --- | --- |
| 01 | Local First | Architecture | Blueprint, Constitution, Execution Plan, Bootstrap | **ACTIVE** | 2026-04-08 |
| 02 | Cloud Optional | Architecture | Blueprint, Constitution, Execution Plan | **ACTIVE** | 2026-04-08 |
| 03 | Default Isolated / Explicit Sharing | Architecture | Blueprint, Constitution, Scope Model | **ACTIVE** | 2026-04-08 |
| 04 | Memory Scope Model | Architecture | Blueprint, Constitution, Scope Model, Execution Plan, Runtime | **ACTIVE** | 2026-04-08 |
| 05 | Token Savings UI 必须存在 | Product | Blueprint, Constitution, Roadmap, Execution Plan, Console | **ACTIVE** | 2026-04-08 |
| 06 | Single Runtime | Architecture | Blueprint, Bootstrap, Execution Plan | **ACTIVE** | 2026-04-08 |
| 07 | Bootstrap Layer 作为入口 | Architecture | Blueprint, Bootstrap, Execution Plan | **ACTIVE** | 2026-04-08 |
| 08 | Metering 三层职责 | Architecture | Blueprint, Constitution, Execution Plan, Runtime | **ACTIVE** | 2026-08 |
| 09 | Runtime Scope Enforcement via SQL | Runtime | Blueprint, Scope Model, RUNTIME_ARCHITECTURE.md | **ACTIVE** | 2026-04-09 |
| 10 | Search Token Savings via Context Assembly | Runtime | Blueprint, Constitution, ROADMAP_CURRENT.md, RUNTIME_ARCHITECTURE.md | **ACTIVE** | 2026-04-09 |
| 11 | OmniMemora 定位为 Memory Augmentation Layer | Product | Blueprint, Constitution | **ACTIVE** | 2026-04-09 |
| 12 | Context Strategy 仅轻量选择与压缩 | Architecture | Blueprint, Constitution | **ACTIVE** | 2026-04-09 |
| 13 | Context Strategy Resolution & Metering Consistency | Architecture | Blueprint, Constitution | **ACTIVE** | 2026-04-09 |
| 14 | Context Assembly Single Path Enforcement | Architecture | Blueprint, Constitution | **ACTIVE** | 2026-04-09 |
| 15 | Cache Disabled Pending Scope Isolation Audit | Architecture | Blueprint, Constitution | **ACTIVE** | 2026-04-09 |

---

# 二、决策详情

## Decision 01: Local First

**决策**: OmniMemora 默认在本地运行，不要求云端依赖。

**理由**: 用户数据主权、本地优先趋势、离线可用性

**活跃文档**:

- ✅ `0_blueprint/PRODUCT_CONSTITUTION.md`
- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`
- ✅ `0_blueprint/OmniMemora — Execution Plan（Local-First V1）.md`
- ✅ `omni_memora_bootstrap_安装层设计_v_2_...md`

---

## Decision 02: Cloud Optional

**决策**: 云端仅提供可选的 Control Plane 增强能力，不承载主记忆。

**理由**: 云端是增强，不是核心；本地是默认，不是可选

**活跃文档**:

- ✅ `0_blueprint/PRODUCT_CONSTITUTION.md`
- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`
- ✅ `0_blueprint/OmniMemora — Execution Plan（Local-First V1）.md`

---

## Decision 03: Default Isolated / Explicit Sharing

**决策**: 记忆边界默认隔离，共享必须显式配置。

**理由**: 数据安全默认项、隐私优先、最小权限原则

**活跃文档**:

- ✅ `0_blueprint/PRODUCT_CONSTITUTION.md`
- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`
- ✅ `0_blueprint/MEMORY_SCOPE_MODEL.md`

---

## Decision 04: Memory Scope Model

**决策**: OmniMemora 必须支持基于 scope 的记忆边界治理。

**Scope 类型**:

| Scope | 说明 | 默认行为 |
| --- | --- | --- |
| user | 用户级记忆 | 跨 workspace 隔离 |
| workspace | 项目/工作空间记忆 | 同 workspace 内共享 |
| agent | Agent 私有记忆 | 仅 agent 自身可访问 |
| custom | 自定义共享域 | 显式配置后共享 |

**Sharing Mode**:

| Mode | 说明 |
| --- | --- |
| isolated | 完全隔离，不可共享 |
| shared | 同 scope 内可读写共享 |
| shared_read_only | 同 scope 内仅可读 |
| custom | 按 custom_policy 规则共享 |

**活跃文档**:

- ✅ `0_blueprint/PRODUCT_CONSTITUTION.md`
- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`
- ✅ `0_blueprint/MEMORY_SCOPE_MODEL.md`
- ✅ `0_blueprint/RUNTIME_ARCHITECTURE.md`

---

## Decision 05: Token Savings UI 必须存在

**决策**: Token Savings 是核心产品能力，必须在 Console 中完整展示。

**三层职责**:

| Layer | 职责 |
| --- | --- |
| Runtime | 产生 metering events（raw_tokens, compressed_tokens, saved_tokens） |
| Control Plane | 聚合 token savings（按 user/workspace/agent/scope） |
| Console | 展示总览、今日/本周/本月、按 workspace/agent breakdown、趋势图 |

**活跃文档**:

- ✅ `0_blueprint/PRODUCT_CONSTITUTION.md`（第五节）
- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`
- ✅ `0_blueprint/ROADMAP_CURRENT.md`（Phase 3）
- ✅ `0_blueprint/OmniMemora — Execution Plan（Local-First V1）.md`（Phase 3）

---

## Decision 06: Single Runtime

**决策**: 每个用户/workspace 运行单一 Local Runtime 实例。

**活跃文档**:

- ✅ `0_blueprint/PRODUCT_CONSTITUTION.md`
- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`

---

## Decision 07: Bootstrap Layer 作为入口

**决策**: Bootstrap Layer 负责安装编排，是用户接触产品的第一层。

**职责范围**:

- ✅ runtime 下载/安装/升级
- ✅ config 生成与注入
- ✅ connector 自动注册
- ❌ 不承担 metering / billing / UI 逻辑

**活跃文档**:

- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`
- ✅ `omni_memora_bootstrap_安装层设计_v_2_...md`

---

## Decision 08: Metering 三层职责

**决策**: Metering 必须在 Runtime / Control Plane / Console 三层全部落地。

**Runtime 层**: 产生原始 metering event

```json
{
  "event_type": "token_savings",
  "raw_tokens": 1000,
  "compressed_tokens": 200,
  "saved_tokens": 800,
  "scope": "workspace",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "user_id": "u_001",
  "timestamp": "2026-04-08T00:00:00Z"
}
```

**Control Plane 层**: 聚合

- 按 user / workspace / agent / scope 聚合
- 支持多维度统计查询

**Console 层**: 展示

- Token Savings 总览
- 今日 / 本周 / 本月
- 按 workspace breakdown
- 按 agent breakdown
- 趋势图

**活跃文档**:

- ✅ `0_blueprint/PRODUCT_CONSTITUTION.md`
- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`
- ✅ `0_blueprint/OmniMemora — Execution Plan（Local-First V1）.md`

---

## Decision 09: Runtime Scope Enforcement via SQL

**决策**: Scope 隔离在 Runtime 层通过 SQL WHERE 子句强制执行，tenant_id 作为第一过滤条件。

**理由**: 防止 scope 串读、确保多租户隔离、SQL 层面强制治理而非应用层软判断

**SQL Scope Filter 模式**:

```sql
-- Agent Scope
WHERE tenant_id = ? AND scope = 'agent' AND agent_id = ?

-- Workspace Scope
WHERE tenant_id = ? AND scope = 'workspace' AND workspace_id = ?
```

**关键约束**:

1. `tenant_id` 必过滤，无例外
2. `scope` 使用字面量（非变量）
3. workspace 查询不混入 agent 记录

**活跃文档**:

- ✅ `0_blueprint/RUNTIME_ARCHITECTURE.md` (8.5 节)
- ✅ `0_blueprint/MEMORY_SCOPE_MODEL.md`
- ✅ `4_core/local-runtime/store/sqlite_store.go`

---

## Decision 10: Search Token Savings via Context Assembly（FINAL）

**决策**: `/memory/search` 通过可选的 context assembly 产生真实的 search token savings，使 search 从"排序检索"升级为"轻量 context retrieval"。

**理由**: Token Savings 是核心产品能力，search 必须与 Token Savings 链路真实挂钩，而非形式字段。

**最终口径（FINAL）**：

```text
raw_tokens = sum(selected_items.tokens)
compressed_tokens = assembled_context.total_tokens
saved_tokens = max(raw_tokens - compressed_tokens, 0)
assembled_hits = len(selected_items)
```

**诚实口径原则（强制）**：

```text
assemble_context=false → raw_tokens=0, compressed_tokens=0, saved_tokens=0, assembled_hits=0
```

不允许在非 assembly 场景下伪造 `compressed_tokens`，也不允许使用 `raw_tokens = compressed * N` 反推逻辑。

**活跃文档**:

- ✅ `0_blueprint/ROADMAP_CURRENT.md`（Phase 2b）
- ✅ `0_blueprint/RUNTIME_ARCHITECTURE.md`（7.2 节 / 5.4 节 / 10.1 节）
- ✅ `4_core/local-runtime/app/service.go`
- ✅ `4_core/local-runtime/pkg/types.go`
- ✅ `4_core/local-runtime/store/sqlite_store.go`（migration）

---

## Decision 11: OmniMemora 定位为 Memory Augmentation Layer

**决策**: OmniMemora 必须严格定位为 Memory Augmentation Layer，不接管 Agent 的 memory ownership。

**理由**: 避免产品向 Agent / Memory System 漂移，确保 OmniMemora 仅作为增强组件存在。

**核心约束**:

| 约束 | 说明 |
| --- | --- |
| 非接管原则 | 不替代 Agent 原生 memory，不作为主 memory storage，不要求 Agent 迁移 memory 系统 |
| 弱侵入原则 | Agent 可不接入 OmniMemora 正常运行，OmniMemora 不得成为 Agent 必经路径，接入成本必须最小化 |
| 单能力原则 | 只解决提升 context 质量和降低 token 使用，所有功能必须直接服务于 token savings 或 context optimization |
| 接口边界原则 | 只通过 `/memory/search` 和 `/memory/write` 提供能力，不扩展为 orchestration / agent runtime / tool system |

**Impact**:

- 限制未来功能边界
- 任何设计必须先问：这个功能是不是在“替 Agent 做事”？如果是，砍。

**活跃文档**:

- ✅ `0_blueprint/PRODUCT_CONSTITUTION.md`（第十二节）
- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`

---

## Decision 12: Context Strategy 仅轻量选择与压缩

**决策**: OmniMemora 在任何阶段不得引入复杂智能能力，Context Strategy 只能是对已召回结果的轻量选择与压缩。

**禁止清单（红线）**:

| # | 禁止项 | 说明 |
|---|--------|------|
| 1 | query understanding / intent classification | 不解析查询意图、不做分类器 |
| 2 | task routing / orchestration | 不做任务路由、不做编排层 |
| 3 | multi-stage pipeline | 不引入 recall → rerank → refine 多阶段流水线 |
| 4 | 学习型策略 | 不引入 feedback loop、不做 adaptive learning |

**允许范围（轻量选择与压缩）**:

- 基于 score / recency / diversity 的排序
- 固定阈值或启发式规则
- 摘要/截取/合并
- Token budget 控制

**理由**:

- 防止产品向“检索引擎”或“Agent”方向漂移
- 保持定位为 Memory Augmentation Layer
- 避免过度设计和 scope creep

**Impact**:

- 任何新增 Strategy 必须先对照此清单
- 若功能超出“轻量选择与压缩”范围，直接拒绝

**活跃文档**:

- ✅ `0_blueprint/PRODUCT_CONSTITUTION.md`（第十二节）
- ✅ `0_blueprint/Global Product Blueprint（Unified V2）.md`

---

## Decision 13: Context Strategy Resolution & Metering Consistency

**决策**: `context_strategy=auto` 时必须先 resolve，response 与 metering 均使用 resolved strategy，禁止记录原始 "auto"。

**规则**:

```text
1. 收到 context_strategy="auto" 时，先调用 ResolveAutoStrategy()
2. resolved strategy 必须同时用于：
   - response.context.strategy
   - metering.event.context_strategy
3. 禁止在任一位置记录原始 "auto"
```

**理由**:

- 确保数据口径一致
- 便于后续分析和归因
- 避免 "auto" 在不同上下文中含义不同

**活跃文档**:

- ✅ `0_blueprint/RUNTIME_ARCHITECTURE.md`
- ✅ `4_core/local-runtime/app/service.go`

---

## Decision 14: Context Assembly Single Path Enforcement

**决策**: 所有 context assembly 必须通过 ctxAssembler，禁止多实现路径。

**规则**:

```text
1. SearchMemory() 只走 s.ctxAssembler.AssembleContext()
2. 旧版 assembleContext() 及相关 helper 必须完全移除
3. 不允许存在两套 assembly 逻辑
```

**理由**:

- 避免维护成本和行为不一致
- 确保 token accounting 只有单一真实源
- 简化测试和验证

**活跃文档**:

- ✅ `0_blueprint/RUNTIME_ARCHITECTURE.md`
- ✅ `4_core/local-runtime/app/service.go`

---

## Decision 15: Cache Disabled Pending Scope Isolation Audit

**决策**: 当前版本不启用 cache，后续需独立 scope 隔离审计才能上线。

**规则**:

```text
1. Cache 组件保留，但在 AssembleContext() 中不调用
2. 代码中必须有清晰注释说明：
   "Cache is intentionally disabled pending dedicated scope-isolation audit"
3. 主流程完全不依赖 cache
```

**理由**:

- Scope 安全优先于性能优化
- Cache 需单独专项审计确保无 scope 污染
- 避免半成品状态导致误上线

**活跃文档**:

- ✅ `0_blueprint/RUNTIME_ARCHITECTURE.md`
- ✅ `4_core/local-runtime/app/context/assembler.go`

---

# 三、禁止出现的旧架构

以下模式**严禁**在任何活跃文档或实现中出现：

| 旧架构 | 禁止原因 |
| --- | --- |
| connector 直连云端 memory backend | 违反 Local First |
| 云端作为主记忆存储 | 违反 Cloud Optional |
| API key 作为前置条件 | 违反 Local First |
| 本地 Runtime 作为可选附件 | 违反 Single Runtime |
| Token Savings UI 可选 | 违反 Decision 05 |
| 默认共享 | 违反 Default Isolated |

---

# 四、版本治理

本文档是所有架构决策的唯一权威来源。

任何文档与本文档冲突，以本文档为准，并向决策者确认是否需要更新本文档。

## 四.1 Patch 合法性规则

**任何 PATCH / Implementation Guide 文档中出现的结构性要素（scope / runtime / backend / identity），必须在 Blueprint 或 RUNTIME_ARCHITECTURE 中找到对应定义，否则视为非法扩展。**

| 结构性要素 | 必须溯源的 Blueprint 文档 |
| --- | --- |
| scope 类型 / sharing_mode | MEMORY_SCOPE_MODEL.md |
| Runtime 架构 / 端口 / 目录结构 | RUNTIME_ARCHITECTURE.md |
| Backend 接口 / Store 抽象 | RUNTIME_ARCHITECTURE.md（第八节） |
| identity（user_id / workspace_id / tenant_id） | RUNTIME_ARCHITECTURE.md（5.2 ScopeRef） |

**判断流程：**

```text
PATCH 文档出现新的 scope 行为？
  → 在 MEMORY_SCOPE_MODEL.md 查找定义
  → 无定义 → 非法扩展，禁止合入

PATCH 文档出现新的 Backend 替换策略？
  → 在 RUNTIME_ARCHITECTURE.md 第八节查找接口
  → 无定义 → 非法扩展，禁止合入

PATCH 文档修改 ScopeRef 字段结构？
  → 在 RUNTIME_ARCHITECTURE.md 5.2 节查找定义
  → 与 Blueprint 不一致 → 以 Blueprint 为准，强制对齐
```

> **例外**：明确标注为 "Future 扩展" 的内容不受此规则约束，但必须在 Future 阶段补齐 Blueprint 定义。
