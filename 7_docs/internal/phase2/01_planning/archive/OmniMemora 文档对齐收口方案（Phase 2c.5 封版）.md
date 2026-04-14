
系统治理级
---
# OmniMemora 文档对齐收口方案（Phase 2c.5 封版）

## 一、收口目标（必须达成）

```text
让所有文档对齐到“唯一真实系统状态”
并冻结 Phase 2 的语义
```

最终结果：

```text
任何人只看文档，就能知道系统现在“真实怎么运行”
```

不是：

```text
“可能是这样 / 未来会这样 / 设计是这样”
```

---

## 二、对齐原则（必须执行）

### 1. DECISION_LEDGER 为最高事实源

```text
DECISION_LEDGER > Blueprint > Architecture > Roadmap > README
```

任何冲突：

```text
以 DECISION_LEDGER 为准，其他全部改
```

---

### 2. 文档必须描述“现在”，不是“计划”

禁止出现：

```text
- future
- planned
- will be
- TODO（除非明确 Phase 3）
```

---

### 3. 一处定义，全局引用

例如：

- token metering 规则
    
- strategy 列表
    
- context mode
    

只能定义在一个地方，其它文档引用，不重复描述。

---

### 4. Phase 冻结

```text
Phase 2 = 已完成系统
Phase 3 = 新能力
```

禁止：

```text
在 Phase 2 文档中混入 Phase 3 内容
```

---

# 三、需要对齐的核心文档

你当前体系：

---

## Tier 0（必须对齐）

1. `DECISION_LEDGER.md`
    
2. `PRODUCT_CONSTITUTION.md`
    
3. `MEMORY_SCOPE_MODEL.md`
    

---

## Tier 1（强一致）

4. `RUNTIME_ARCHITECTURE.md`
    
5. `ROADMAP_CURRENT.md`
    

---

## Tier 2（同步更新）

6. `README.md`
    
7. `Execution Plan（Local-First V1）.md`
    

---

# 四、逐文件对齐清单（可执行）

---

# 1. DECISION_LEDGER.md（第一优先）

## 必须新增/确认

---

### Decision 10（必须更新为最终版）

```text
Search Token Savings via Context Assembly（FINAL）
```

必须明确：

```text
raw_tokens = sum(selected_items.tokens)
compressed_tokens = assembled_context.total_tokens
saved_tokens = max(raw_tokens - compressed_tokens, 0)
assembled_hits = len(selected_items)
```

以及：

```text
assemble_context=false → 全部为 0
```

---

### Decision 12（新增）

```text
Context Strategy Resolution & Metering Consistency
```

内容：

```text
- context_strategy=auto 时：
  - 必须先 resolve
  - response 与 metering 均使用 resolved strategy
- 禁止记录原始 "auto" 作为 metering 结果
```

---

### Decision 13（新增）

```text
Context Assembly Single Path Enforcement
```

内容：

```text
- 所有 context assembly 必须通过 ctxAssembler
- 禁止多实现（legacy assembleContext 已移除）
```

---

### Decision 14（新增）

```text
Cache Disabled Pending Scope Isolation Audit
```

内容：

```text
- 当前版本不启用 cache
- 原因：scope 安全优先
- 后续需独立审计才能上线
```

---

# 2. PRODUCT_CONSTITUTION.md（加一条红线）

新增：

---

### Clause X：Context Strategy Boundary

```text
OmniMemora 不得演化为：

- query understanding system
- retrieval pipeline（多阶段）
- orchestration layer
- adaptive learning system

Context Strategy 仅允许：
→ 对已召回结果进行选择与压缩
```

---

# 3. MEMORY_SCOPE_MODEL.md（只确认，不扩展）

确认三点：

```text
1. SQL 强制过滤在最前
2. strategy / assembler 只能在 recall 后执行
3. cache 不参与 scope（当前版本）
```

不需要新增复杂内容。

---

# 4. RUNTIME_ARCHITECTURE.md（核心收口）

## 必须重写 2 个部分

---

### A. `/memory/search`（必须是最终形态）

结构必须是：

```text
1. SQL recall（scope enforcement）
2. scoring（已有）
3. context assembly（ctxAssembler）
   - strategy
   - mode
   - token budget
4. metering
```

必须明确：

```text
- assembler 是唯一入口
- strategy 在 recall 后执行
- cache 未启用
```

---

### B. Context Assembly Pipeline（新增一节）

```text
Context Assembly = Strategy-driven selection + token-bounded compression
```

包含：

- strategy 列表
    
- mode（precise/balanced/aggressive）
    
- token budget
    
- deterministic 输出
    

---

# 5. ROADMAP_CURRENT.md（必须改）

## Phase 状态必须写死：

```text
Phase 2a: ✅ PASSED
Phase 2b: ✅ PASSED
Phase 2c: ✅ PASSED
Phase 2c.5: ✅ PASSED（Post-Audit Fix）
```

---

## Phase 3（只写目标，不写实现）

```text
Phase 3: Productization & Adoption

Focus:
- Observability
- Integration simplicity
- Stability

Explicitly NOT:
- Retrieval pipeline evolution
- Agent orchestration
- Query understanding
```

---

# 6. README.md（外部认知收口）

必须体现：

```text
OmniMemora = Memory Augmentation Layer
```

并强调：

```text
- 不替代 Agent memory
- 不接管推理
- 仅优化 context + token
```

---

# 五、统一术语表（必须加一个 Glossary）

建议放在：

```text
docs/glossary.md（或 README 尾部）
```

---

必须定义：

```text
Context Assembly
Context Strategy
Resolved Strategy
Token Savings
Raw Tokens / Compressed Tokens
Scope
```

避免：

```text
同一个词在不同文档含义不同
```

---

# 六、收口执行顺序（不要乱）

按这个顺序做：

---

### Step 1

改：

```text
DECISION_LEDGER.md
```

（定义最终事实）

---

### Step 2

改：

```text
PRODUCT_CONSTITUTION.md
```

（加边界）

---

### Step 3

改：

```text
RUNTIME_ARCHITECTURE.md
```

（系统真实运行方式）

---

### Step 4

改：

```text
ROADMAP_CURRENT.md
```

（阶段状态）

---

### Step 5

改：

```text
README.md
```

（对外表述）

---

### Step 6（可选）

补：

```text
glossary.md
```

---

# 七、收口完成判定标准

你只需要检查 4 件事：

---

### 1

```text
所有文档对 token metering 描述一致
```

---

### 2

```text
所有文档只出现一个 assembly 路径
```

---

### 3

```text
没有任何文档暗示“未来会有更复杂 pipeline”
```

---

### 4

```text
产品定位在所有文档中一致：
Memory Augmentation Layer
```

---

# 八、一句话总结

```text
这次收口不是整理文档，而是锁死系统边界
```
