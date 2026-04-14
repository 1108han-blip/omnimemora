

# OmniMemora Phase 2c / 2c.5 审计计划（第三方执行版）

## 一、审计目标（必须达成）

本次审计的唯一目标：

```text
验证 Phase 2c / 2c.5 是否：

1. 不违反 PRODUCT_CONSTITUTION
2. 不破坏 Scope 安全模型
3. 不伪造 Token Savings / Metering 数据
4. 不引入架构方向性漂移（变成 Agent / Retrieval Engine）
```

结论必须是三选一：

```text
PASS / PASS WITH FIXS / FAIL
```

---

## 二、审计范围（强约束）

仅限以下模块：

```text
app/context/
  - strategy.go
  - strategy_topk.go
  - strategy_recency.go
  - strategy_diversity.go
  - strategy_auto.go
  - assembler.go
  - cache.go

app/service.go
pkg/types.go
metering/event.go
```

禁止扩展审计范围（防止无限发散）。

---

## 三、审计原则（必须遵守）

### 1. 宪法优先级最高

所有判断以：

- PRODUCT_CONSTITUTION.md
    
- DECISION_LEDGER.md
    

为最高标准。

---

### 2. 不接受“设计合理但不符合宪法”

任何实现：

```text
即使工程上合理
但违反宪法 / 决策记录
→ 直接判 FAIL
```

---

### 3. 不接受“未来会修”

```text
审计只看当前实现
不能用 roadmap / future justify
```

---

# 四、审计模块（核心）

---

# Module A：宪法一致性审计（最高优先级）

## A1. 非接管原则检查

依据：Decision 11【Memory Augmentation Layer】

检查：

- 是否出现以下行为：
    

```text
- 自动决策 agent 行为（而非仅优化 context）
- 替 agent 选择 memory 使用策略（超出 search 范围）
- 引入 task-level routing / orchestration 逻辑
```

### 判定

```text
若存在 → FAIL
```

---

## A2. 单能力原则检查

依据：宪法补充条款 3

检查所有新增能力是否满足：

```text
必须直接服务：
- context optimization
- token savings
```

重点检查：

- strategy_auto.go 是否变成 query classifier / intent engine
    
- effectiveness.go 是否变成 analytics 系统，而非辅助指标
    

### 判定

```text
若出现“泛智能能力” → FAIL
```

---

## A3. 接口边界检查

依据：宪法接口边界

检查：

```text
是否仍只通过：

/memory/search
/memory/write
```

是否出现：

```text
- 新内部 routing 层暴露
- 新 execution / pipeline 抽象泄露
```

---

# Module B：Scope 安全审计（必须 100% 通过）

依据：

- MEMORY_SCOPE_MODEL.md
    
- Decision 09（SQL 强制隔离）
    

---

## B1. Cache Key 隔离检查（致命项）

检查 `assembler.go`：

```text
cache_key 是否包含：

- tenant_id
- user_id
- workspace_id
- agent_id
- scope
- query
- strategy
- mode
```

### 判定

```text
任一缺失 → FAIL
```

---

## B2. Cache 污染测试（必须实测）

构造：

```text
Agent A / workspace X
Agent B / workspace Y
同 query
```

验证：

```text
是否命中同一个 cache
```

### 判定

```text
若跨 scope 命中 → FAIL
```

---

## B3. Strategy 执行路径检查

检查：

```text
strategy_auto / diversity / recency
是否在 SQL recall 之后执行
```

禁止：

```text
绕过 SQL scope filter
```

---

## B4. Metering Scope 一致性

检查：

```text
metering event 中：

tenant / workspace / agent / scope
是否与实际查询一致
```

---

# Module C：Token Savings / Metering 审计（严禁造假）

依据：

Decision 10（search token savings 必须真实）

---

## C1. assemble_context=false 场景

验证：

```json
{
  "raw_tokens": 0,
  "compressed_tokens": 0,
  "saved_tokens": 0,
  "assembled_hits": 0
}
```

### 判定

```text
任一非 0 → FAIL
```

---

## C2. StrategyEffectiveness 合法性

检查：

```text
tokens_per_item
compression_ratio
avg_score
```

是否：

```text
只在真实 assembly 后计算
```

### 判定

```text
若在无 context 情况返回 → FAIL
```

---

## C3. efficiencyScore 风险检查（关键）

当前改动：

```text
score / tokens
```

检查：

```text
是否导致：

- 故意选择更短文本 → 表面 token savings 更高
- 实际语义质量下降
```

### 判定

```text
若优化目标偏离“信息密度” → PASS WITH FIXES
```

---

## C4. Auto Strategy + Metering 一致性

检查：

```json
"context_strategy": "auto"
```

vs

```text
ResolvedStrategy
```

必须明确：

```text
metering记录哪一个？
```

### 判定

```text
口径不一致 → FAIL
```

---

# Module D：架构复杂度与方向漂移审计

---

## D1. Strategy 系统复杂度

检查：

```text
ContextStrategy 是否：

- 可插拔 ✔
- 轻量 ✔
- 无跨层依赖 ✔
```

是否出现：

```text
- 策略间依赖
- 状态共享
- pipeline chaining
```

---

## D2. 是否演化为 Retrieval Engine

检查是否出现：

```text
- 多阶段 pipeline（recall → rerank → refine → assemble → optimize）
- query understanding / classification
- adaptive learning
```

### 判定

```text
若出现 → FAIL
```

---

## D3. 是否影响 Local First

依据：

Execution Plan

检查：

```text
是否引入：

- 云端依赖
- 外部模型
- API key 依赖
```

---

# 五、测试用例要求（必须执行）

第三方必须跑：

### 1. Scope 隔离测试（4 组）

- agent ↔ agent
    
- workspace ↔ workspace
    
- tenant ↔ tenant
    
- custom（如实现）
    

---

### 2. Strategy 行为测试

```text
topk / recency / diversity / auto
```

验证：

```text
返回是否稳定
是否 deterministic
```

---

### 3. Cache 命中测试

- 同 query 同 scope → 命中
    
- 同 query 不同 scope → 不命中
    

---

### 4. Metering 正确性测试

- assembly on/off
    
- strategy=auto / explicit
    
- 不同 mode
    

---

# 六、输出要求（必须按此格式）

第三方必须交付：

---

## 1. 审计结论

```text
PASS / PASS WITH FIXES / FAIL
```

---

## 2. 问题清单（分级）

|等级|定义|
|---|---|
|P0|必须修复，否则禁止上线|
|P1|强烈建议修复|
|P2|优化项|

---

## 3. 每个问题必须包含

```text
- 文件位置
- 触发路径
- 风险说明
- 是否违反宪法（必须写）
- 修复建议（必须具体）
```

---

## 4. 架构评价（必须写）

第三方必须给出：

```text
- 是否存在方向性漂移
- 是否仍是 Memory Augmentation Layer
- 是否有过度设计风险
```

---

# 七、验收标准（你用来拍板）

你只需要看三件事：

---

### 1. 有没有 P0

```text
有 → 不允许进入 Phase 3
```

---

### 2. 有没有“宪法违规”

```text
有 → 直接回滚
```

---

### 3. 有没有“架构漂移”

```text
有 → 立即收缩设计
```

