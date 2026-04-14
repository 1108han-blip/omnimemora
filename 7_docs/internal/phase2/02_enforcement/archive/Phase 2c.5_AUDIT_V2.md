
# OmniMemora Phase 2c.5 修复后复审清单

## 一、复审目标

本次复审只回答一个问题：

```text
Phase 2c.5 的 P0 / P1 修复是否真正完成，
系统是否可以解除 Blocked 状态，进入下一阶段。
```

复审结论只能是三选一：

```text
PASS
PASS WITH FIXES
FAIL
```

---

## 二、复审范围

仅复审以下模块：

```text
app/context/
  - assembler.go
  - strategy_topk.go
  - strategy_recency.go
  - strategy_diversity.go
  - strategy_auto.go
  - cache.go（如仍保留）

app/service.go
pkg/types.go
metering/event.go
```

不扩展到 Phase 3，不讨论 UI，不讨论 Billing。

---

## 三、复审基准

第三方必须以以下文档为准：

- `PRODUCT_CONSTITUTION.md`
    
- `DECISION_LEDGER.md`
    
- `MEMORY_SCOPE_MODEL.md`
    
- 上一轮审计报告 `Phase_2c5_AUDIT_REPORT.md`
    

重点约束：

1. **Decision 10：Search Token Savings via Context Assembly**
    
2. **Decision 09：Runtime Scope Enforcement via SQL**
    
3. **Decision 11：Memory Augmentation Layer**
    
4. **补充条款：弱侵入 / 单能力 / 接口边界**
    

---

# 四、复审检查项

---

## Module A：P0 修复核验

### A1. `raw_tokens` 是否真实计算

检查 `app/service.go` 与 `app/context/assembler.go`：

必须确认不存在以下逻辑：

```go
raw_tokens = compressed_tokens * N
raw_tokens = TotalTokens * N
```

必须确认实际口径为：

```text
raw_tokens = sum(selected_items.tokens)
compressed_tokens = assembled_context.total_tokens
saved_tokens = max(raw_tokens - compressed_tokens, 0)
assembled_hits = len(selected_items)
```

### 判定标准

- 若仍存在任何“反推 raw_tokens”的逻辑 → **FAIL**
    
- 若 raw_tokens 来自 assembler 的真实 item 汇总 → **PASS**
    

---

### A2. `assemble_context=false` 是否严格全 0

必须实测：

请求：

```json
{
  "options": {
    "assemble_context": false
  }
}
```

期望：

```json
{
  "raw_tokens": 0,
  "compressed_tokens": 0,
  "saved_tokens": 0,
  "assembled_hits": 0
}
```

### 判定标准

- 任一字段非 0 → **FAIL**
    
- 全部为 0 → **PASS**
    

---

### A3. `context_strategy=auto` 的 metering 是否记录 resolved strategy

必须核验以下两处口径一致：

1. response 中 `context.strategy`
    
2. metering event 中 `context_strategy`
    

请求：

```json
{
  "options": {
    "assemble_context": true,
    "context_strategy": "auto"
  }
}
```

若 query 被解析成 `diversity_select`，则必须满足：

```text
response.context.strategy = diversity_select
metering.context_strategy = diversity_select
```

### 判定标准

- response 与 metering 不一致 → **FAIL**
    
- metering 仍记录 `"auto"` → **FAIL**
    
- 二者都记录 resolved strategy → **PASS**
    

---

## Module B：P1 修复核验

### B1. `efficiencyScore` 是否已去除极端短文本偏置

检查 `strategy_topk.go`、`strategy_recency.go`：

确认不再是裸公式：

```go
score / float64(tokens)
```

应为带 token floor 或等效保护的版本，例如：

```go
tokens < 80 → 按 80 处理
```

### 实测要求

构造至少 2 组数据：

- A：高分但极短文本
    
- B：略低分但正常长度文本
    

验证系统不会仅因 token 极小而稳定压制正常内容。

### 判定标准

- 仍是裸除法 → **PASS WITH FIXES**
    
- 有 floor/保护，且测试通过 → **PASS**
    

---

### B2. cache 是否已禁用或正确说明未启用

检查 `assembler.go` 与 `cache.go`：

复审目标不是要求 cache 上线，而是确认：

- 当前搜索主流程**没有实际使用 cache**
    
- 或者 cache 已被明确删除
    
- 若保留文件，必须有清晰注释说明“暂不启用，待独立 scope 审计”
    

### 判定标准

- cache 半接入、半未接入，状态不清 → **PASS WITH FIXES**
    
- cache 明确禁用或删除 → **PASS**
    
- cache 被偷偷启用但无 scope 专项复验 → **FAIL**
    

---

### B3. 旧版 `assembleContext()` 路径是否彻底移除

检查 `app/service.go` 以及全项目引用：

确认：

- `SearchMemory()` 只走 `ctxAssembler`
    
- 不再保留旧版 `assembleContext()` 被调用
    
- 旧 helper 已删除，或完全无引用
    

### 判定标准

- 新旧两套路径都可能被调用 → **FAIL**
    
- 旧函数还在，但完全无引用 → **PASS WITH FIXES**
    
- 已彻底收口为单一路径 → **PASS**
    

---

## Module C：Scope / 安全复核

### C1. strategy 执行是否仍在 SQL recall 之后

必须确认：

- SQL scope enforcement 仍在前
    
- strategy / assembler / effectiveness 都只作用于已过滤后的结果
    
- 不存在绕过 SQL scope 的预筛选或缓存命中
    

### 判定标准

- 任何 strategy 在 SQL filter 前执行 → **FAIL**
    
- 全部发生在 recall 后 → **PASS**
    

---

### C2. 若 cache 保留文件，是否未造成任何 scope 路径影响

即便 cache 未启用，也要确认：

- 主流程不会误走 cache 分支
    
- 不存在默认初始化 cache 导致未来误命中的可能
    

### 判定标准

- 代码路径不清 → **PASS WITH FIXES**
    
- 主流程完全不依赖 cache → **PASS**
    

---

## Module D：Metering 口径复核

### D1. `StrategyEffectiveness` 是否只在真实 assembly 后出现

必须实测：

#### 场景 1：`assemble_context=false`

期望：

```json
"strategy_effectiveness": null
```

或字段省略。

#### 场景 2：`assemble_context=true`

期望：

- `tokens_per_item` 有值
    
- `compression_ratio` 有值
    
- `avg_score` 有值
    

### 判定标准

- 无 assembly 也返回 effectiveness → **FAIL**
    
- 仅真实 assembly 后返回 → **PASS**
    

---

### D2. `saved_tokens` 是否永不为负

必须确认：

```text
saved_tokens = max(raw_tokens - compressed_tokens, 0)
```

### 判定标准

- 允许负值 → **FAIL**
    
- 已做下界保护 → **PASS**
    

---

## Module E：架构边界复核

### E1. 是否仍为 Memory Augmentation Layer

检查本轮修复后是否引入以下任一行为：

- query understanding
    
- task routing
    
- orchestration
    
- multi-stage pipeline
    
- adaptive learning
    

### 判定标准

- 出现任一项 → **FAIL**
    
- 仍仅是 `/memory/search` 内部增强 → **PASS**
    

---

### E2. 是否仍保持接口边界

必须确认：

- 无新增 endpoint
    
- 无新公开执行接口
    
- 仍只围绕 `/memory/search` 的内部增强
    

### 判定标准

- 新增接口或暴露新系统能力 → **FAIL**
    
- 完全保持接口边界 → **PASS**
    

---

# 五、必跑测试清单

第三方必须实际跑完以下测试，而不是只读代码。

## 1. Token 口径测试

- `assemble_context=false` → 4 个 token 字段全 0
    
- `assemble_context=true` → `raw_tokens = sum(item.tokens)`
    

## 2. Auto strategy 口径测试

- `context_strategy=auto`
    
- response / metering 均记录 resolved strategy
    

## 3. 排序风险测试

- 极短高分文本 vs 正常长度中高分文本
    
- 验证不会被 token 极小完全劫持
    

## 4. 单一路径测试

- `SearchMemory()` 只走新 assembler
    
- 无旧 assembly 调用残留
    

## 5. Scope 顺序测试

- SQL recall 在前，strategy 在后
    

## 6. Build / Test 回归

- build 通过
    
- 原有 2b / 2c 测试不回退
    

---

# 六、输出格式要求

第三方复审报告必须包含：

## 1. 复审结论

```text
PASS / PASS WITH FIXES / FAIL
```

## 2. P0 / P1 是否清零

必须单独写：

```text
P0: cleared / not cleared
P1: cleared / remaining
```

## 3. 每个残留问题必须写清

- 文件位置
    
- 触发路径
    
- 是否违反宪法 / Decision
    
- 是否阻断进入 Phase 3
    

## 4. 最终放行建议

只能二选一：

```text
允许进入 Phase 3
暂不允许进入 Phase 3
```

---

# 七、你自己的拍板规则

你最后只看这 4 条：

### 1.

如果 **P0 未清零** → 不允许进入 Phase 3

### 2.

如果仍有 **宪法违规** → 不允许进入 Phase 3

### 3.

如果仍有 **双口径 metering** → 不允许进入 Phase 3

### 4.

如果仍有 **双 assembly 路径** → 不允许进入 Phase 3

---

# 八、一句话给第三方的附言

你可以直接附在任务里：

```text
本次复审不是做新建议，也不是扩展设计讨论。
只验证修复是否完成，以及系统是否解除 Blocked 状态。
如发现新的结构性问题，可补充，但不得偏离本轮修复范围。
```

如果你愿意，我下一条可以继续给你一版 **“第三方复审打分表”**，让对方按分数出结果。