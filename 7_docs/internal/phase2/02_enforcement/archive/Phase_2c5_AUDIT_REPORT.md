
 OmniMemora Phase 2c / 2c.5 审计报告

**审计日期**: 2026-04-09  
**审计范围**: Phase 2c / 2c.5 模块  
**审计依据**: PRODUCT_CONSTITUTION.md、DECISION_LEDGER.md、MEMORY_SCOPE_MODEL.md

---

## 1. 审计结论

```text
PASS WITH FIXES
```

---

## 2. 问题清单（分级）

| 等级 | 定义 |
|------|------|
| P0 | 必须修复，否则禁止上线 |
| P1 | 强烈建议修复 |
| P2 | 优化项 |

---

### P0 级问题

| # | 文件位置 | 触发路径 | 风险说明 | 是否违反宪法 | 修复建议 |
|---|----------|----------|----------|--------------|----------|
| P0-1 | `app/service.go` | `SearchMemory()` 中 token savings 计算 | `raw_tokens` 估算方式不诚实（`compressed * 2`），违反诚实口径原则 | ✅ 违反 Decision 10（诚实口径原则） | 改为真实估算：`raw_tokens = sum(full_content_tokens)`，而非 `compressed * 2` |
| P0-2 | `app/context/assembler.go` | `AssembleContext()` 未实际使用 cache | Cache 组件已实现但未在 `AssembleContext()` 中调用，可能造成 scope 缓存污染（理论风险） | ✅ 违反 B1/B2 缓存隔离要求 | 实际启用缓存逻辑，或移除缓存组件避免误导 |

### P1 级问题

| # | 文件位置 | 触发路径 | 风险说明 | 是否违反宪法 | 修复建议 |
|---|----------|----------|----------|--------------|----------|
| P1-1 | `app/context/strategy_topk.go` / `strategy_recency.go` | `efficiencyScore` 用于排序 | 可能导致故意选择更短文本以提高表面 token savings，偏离“信息密度” | ✅ 违反 C3（优化目标偏离风险） | 增加最小内容长度检查（如 < 100 字符不参与排序），或调整权重公式 |
| P1-2 | `app/service.go` | `recordSearchMetering()` 中 ContextStrategy 记录 | request 为 "auto" 时，记录的是原始 "auto" 而非 resolved strategy，口径不一致 | ✅ 违反 C4（Auto Strategy + Metering 一致性） | 记录 resolved strategy 而非原始请求值 |
| P1-3 | `app/service.go` | 旧版 `assembleContext()` 函数与新 `ctxAssembler` 共存 | 代码重复与混淆，可能造成维护成本与误用 | ⚠️ 架构复杂度问题 | 删除旧版 `assembleContext()` 及相关辅助函数（`extractExcerpt` / `dedupContextItems` / `enforceContextBudget` 等） |

### P2 级问题

| # | 文件位置 | 触发路径 | 风险说明 | 是否违反宪法 | 修复建议 |
|---|----------|----------|----------|--------------|----------|
| P2-1 | `app/context/strategy_auto.go` | `ResolveAutoStrategy()` | 过于简单的启发式规则，可能不是 optimal，但不算违规 | ❌ 不违反 | 未来可基于 real-world 使用数据优化 |
| P2-2 | `pkg/types.go` / `metering/event.go` | 多处类型定义 | 存在新旧两套类型（Phase 2b vs Phase 2c）共存 | ⚠️ 架构复杂度问题 | 逐步统一到新类型系统 |

---

## 3. 架构评价

### 是否存在方向性漂移？
**否**

- 所有新增能力均服务于 context optimization / token savings
- 未引入 orchestration / agent runtime / tool system
- 仍仅通过 `/memory/search` 和 `/memory/write` 提供能力
- 未接管 Agent memory ownership

### 是否仍是 Memory Augmentation Layer？
**是**

- 仅作为可选增强组件
- 未成为 Agent 必经路径
- 未要求 Agent 迁移其 memory 系统
- 单 API 轻量调用接入

### 是否有过度设计风险？
**轻微风险**

- Strategy 系统设计为可插拔 ✔️
- 无跨层依赖 ✔️
- 但存在新旧两套 context assembly 实现共存，增加了维护复杂度 ⚠️
- Cache 组件已实现但未实际使用，存在“半成品”迹象 ⚠️

---

## 4. 审计模块详情

### Module A：宪法一致性审计

| 检查项 | 状态 | 说明 |
|--------|------|------|
| A1. 非接管原则 | ✅ 通过 | 未出现替 agent 决策行为，仅优化 context |
| A2. 单能力原则 | ✅ 通过 | 所有能力均服务于 token savings 或 context optimization |
| A3. 接口边界 | ✅ 通过 | 仍仅通过 `/memory/search` 和 `/memory/write` |

### Module B：Scope 安全审计

| 检查项 | 状态 | 说明 |
|--------|------|------|
| B1. Cache Key 隔离 | ⚠️ 有设计但未启用 | Cache key 设计包含 tenant_id / user_id / workspace_id / agent_id / scope / query / strategy / mode，但缓存未实际使用 |
| B2. Cache 污染测试 | ⚠️ 无法验证 | 因缓存未启用，无法实测 |
| B3. Strategy 执行路径 | ✅ 通过 | Strategy 在 SQL recall 之后执行，未绕过 scope filter |
| B4. Metering Scope 一致性 | ✅ 通过 | metering event 中 scope 与查询一致 |

### Module C：Token Savings / Metering 审计

| 检查项 | 状态 | 说明 |
|--------|------|------|
| C1. assemble_context=false | ✅ 通过 | 按设计返回全 0，诚实 |
| C2. StrategyEffectiveness 合法性 | ✅ 通过 | 仅在真实 assembly 后计算 |
| C3. efficiencyScore 风险 | ⚠️ 需注意 | 存在优化目标偏离风险（见 P1-1） |
| C4. Auto Strategy + Metering 一致性 | ❌ 需修复 | 记录的是原始 "auto" 而非 resolved strategy（见 P1-2） |

### Module D：架构复杂度与方向漂移审计

| 检查项 | 状态 | 说明 |
|--------|------|------|
| D1. Strategy 系统复杂度 | ✅ 通过 | 可插拔、轻量、无跨层依赖 |
| D2. 演化为 Retrieval Engine | ✅ 通过 | 未出现多阶段 pipeline / query understanding / adaptive learning |
| D3. Local First | ✅ 通过 | 未引入云端依赖 / 外部模型 / API key 依赖 |

---

## 5. 验收标准检查

| 检查项 | 状态 |
|--------|------|
| 有没有 P0 | ✅ 有 2 个，需修复后才能进入 Phase 3 |
| 有没有“宪法违规” | ✅ 有 3 处（诚实口径 / 缓存隔离 / 口径一致性），需修复 |
| 有没有“架构漂移” | ❌ 无 |

---

## 6. 修复优先级建议

1. **立即修复（Block Phase 3）**：P0-1、P0-2
2. **尽快修复**：P1-1、P1-2、P1-3
3. **择机优化**：P2-1、P2-2

---

**审计人**: AI Auditor  
**审计完成时间**: 2026-04-09
