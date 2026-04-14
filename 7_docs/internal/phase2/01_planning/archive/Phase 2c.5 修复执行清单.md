基于这次交叉审计，**Phase 2c.5 现在不是继续扩功能，而是做一次“止血式修复”**。  
因为当前已经明确有 2 个 P0：`raw_tokens` 伪造，以及 `auto strategy` 在 response / metering 的口径不一致；而 search token savings 的诚实口径已经在 Decision 10 被写死：assembly 打开时，`raw_tokens` 必须来自全文估算总和，`saved_tokens = raw - compressed`；assembly 关闭时四个字段都必须为 0。同时，scope 隔离仍然必须由 SQL 强制执行，`tenant_id` 必过滤、`scope` 精确匹配、workspace 不得混入 agent 数据。

下面这份就是 **Phase 2c.5 修复执行清单（CC 可直接落代码）**。

---

# Phase 2c.5 修复执行清单

## 0. 本轮目标

只做 5 件事：

1. 修复 `raw_tokens` 诚实口径
    
2. 修复 `auto strategy` metering 口径
    
3. 处理 cache 半成品问题
    
4. 收敛 `efficiencyScore` 的偏移风险
    
5. 删除旧 assembly 遗留，避免双轨并存
    

**本轮禁止新增任何新策略、新接口、新 pipeline。**

---

## 1. P0-1：修复 `raw_tokens` 伪造

### 问题

审计已确认，当前存在：

```go
rawTokens = ctxResult.Context.TotalTokens * 2
```

这违反 Decision 10 的诚实口径要求。

### 要改什么

在 `app/service.go` 中，**删除所有 `compressed * N`、`TotalTokens * 2` 之类的反推逻辑**。

### 正确口径

当 `assemble_context=true` 且确实 assembled 后：

- `raw_tokens = sum(selected_items.full_content_token_estimate)`
    
- `compressed_tokens = assembled_context.total_tokens`
    
- `saved_tokens = max(raw_tokens - compressed_tokens, 0)`
    
- `assembled_hits = len(selected_items)`
    

当 `assemble_context=false` 时：

- `raw_tokens = 0`
    
- `compressed_tokens = 0`
    
- `saved_tokens = 0`
    
- `assembled_hits = 0`
    

### 代码级改法

在 assembler 返回值里补全原始 token 汇总，不要在 service 层猜。

#### 修改 `app/context/assembler.go`

给 `AssemblyResult` 增加：

```go
type AssemblyResult struct {
    Context          *pkg.StrategyAssembledContext
    Items            []pkg.StrategyContextItem
    Effectiveness    *pkg.StrategyEffectiveness
    ResolvedStrategy string
    RawTokens        int
    AssembledHits    int
}
```

在 assembly 完成后：

```go
rawTokens := 0
for _, item := range selectedItems {
    rawTokens += item.Tokens
}

result := AssemblyResult{
    Context:          assembled,
    Items:            selectedItems,
    Effectiveness:    effectiveness,
    ResolvedStrategy: resolvedStrategy,
    RawTokens:        rawTokens,
    AssembledHits:    len(selectedItems),
}
```

#### 修改 `app/service.go`

禁止再自行推导 raw tokens：

```go
rawTokens := 0
compressedTokens := 0
savedTokens := 0
assembledHits := 0

if ctxResult != nil && ctxResult.Context != nil {
    rawTokens = ctxResult.RawTokens
    compressedTokens = ctxResult.Context.TotalTokens
    if rawTokens > compressedTokens {
        savedTokens = rawTokens - compressedTokens
    }
    assembledHits = ctxResult.AssembledHits
}
```

### 验收测试

必须新增：

- `assemble_context=false` → 四个字段全 0
    
- `assemble_context=true` 且 2 条 item，各自 tokens=100/120，assembled=150  
    → `raw=220`, `compressed=150`, `saved=70`, `assembled_hits=2`
    

---

## 2. P0-2：修复 `auto strategy` 的 metering 口径不一致

### 问题

审计确认：response 里用了 resolved strategy，但 metering 里仍记录原始 `"auto"`，这属于口径不一致。

### 要改什么

**metering 一律记录实际执行的 resolved strategy，不记录用户输入的 `"auto"`。**

### 修改点

#### `app/service.go`

当前大概率类似：

```go
contextStrategy := req.Options.ContextStrategy // "auto"
...
s.recordSearchMetering(..., contextStrategy, ...)
```

改为：

```go
requestedStrategy := req.Options.ContextStrategy
resolvedStrategy := requestedStrategy

if requestedStrategy == "auto" {
    resolvedStrategy = context.ResolveAutoStrategy(query)
}
...
ctxResult, err := s.ctxAssembler.Assemble(..., resolvedStrategy, ...)
...
s.recordSearchMetering(..., resolvedStrategy, ...)
```

### Response 口径

保留 response 中 `context.strategy = resolvedStrategy`。  
不要同时返回 `"auto"` 和 resolved，避免双口径。

### 可选增强

如果你想保留用户输入，**只能另加一个 optional 字段**，比如：

```json
"context_strategy_requested": "auto"
"context_strategy_resolved": "diversity_select"
```

但这不是本轮必需。本轮最小修复只要保证 **metering = resolved**。

### 验收测试

新增：

- 输入 `context_strategy=auto`
    
- query 命中 auto 规则，解析到 `diversity_select`
    
- response.context.strategy == `diversity_select`
    
- metering.context_strategy == `diversity_select`
    

---

## 3. P1-2：处理 cache 半成品

### 我的判断

这个问题现在**不建议“立刻启用 cache”**。  
因为 scope 安全是硬约束，tenant / workspace / agent 不能有任何缓存串读风险。

### 本轮建议

**直接禁用或移除 cache 接入点，先不要上线缓存。**

这是最稳的，不会引入新的 P0。

### 具体做法

二选一，推荐 A：

#### A. 推荐：保留文件，但不初始化、不注入、不调用

- `assembler.go` 中移除 `cache.Get()` / `cache.Set()` 的预留分支
    
- 注释写清：`// cache intentionally disabled pending dedicated scope-isolation audit`
    

#### B. 或者更狠：直接删除 `cache.go` 和相关字段

如果你想代码更干净，直接删也行。

### 不建议

本轮不要启用 cache。  
因为一旦启用，必须同时补全：

- scope-aware cache key
    
- cache invalidation
    
- cross-scope tests
    

这会扩大修复面。

### 验收标准

- 搜索路径中无 cache 命中逻辑
    
- 无任何 response / metering 依赖 cache
    
- 注释明确“暂不启用，待独立审计”
    

---

## 4. P1-1：收敛 `efficiencyScore` 偏向短文本的问题

### 问题

当前：

```go
score / float64(tokens)
```

会天然偏向很短的片段，可能把“更省 token”误优化成“更短但更差”。

### 本轮不要复杂化

不要引入学习、rerank、query understanding。  
只做一个**保守修正**。

### 推荐公式

把纯除法改成“带下限的长度惩罚”：

```go
func normalizedTokenCost(tokens int) float64 {
    if tokens <= 0 {
        return 1.0
    }
    if tokens < 80 {
        return 80.0
    }
    return float64(tokens)
}

func efficiencyScore(tokens int, score float64) float64 {
    return score / normalizedTokenCost(tokens)
}
```

这样不会让 10-token 的碎片把正常内容打爆。

### 更稳一点

只在 `topk` 和 `recency` 使用这个修正，`diversity` 先不碰。

### 验收测试

新增 1 个单测：

- item A: score=0.9, tokens=20
    
- item B: score=0.8, tokens=120
    

在旧公式下 A 一定压死 B；  
在新公式下，两者差距被收敛，不能极端偏向碎片。

---

## 5. P1-3：删除旧版 `assembleContext()` 遗留

### 问题

现在新旧两套 assembly 并存，后面很容易出现“修了 A 没修 B”的维护事故。

### 要改什么

在 `app/service.go`：

- 删除旧版 `assembleContext()`
    
- 删除相关旧 helper：
    
    - `extractExcerpt`
        
    - `dedupContextItems`
        
    - `enforceContextBudget`
        
    - 其他仅旧逻辑使用的私有函数
        

### 约束

确保 `SearchMemory()` 只通过 `ctxAssembler` 进入 Phase 2c 路径。

### 验收测试

代码搜索确认：

- `assembleContext(` 仅剩新 assembler 路径
    
- 无旧 helper 的引用
    
- build 通过
    
- 原有 2b / 2c 测试不回退
    

---

## 6. 类型系统收敛：先不统一全部，但要止血

### 问题

新旧类型并存，但这不是本轮 blocker。

### 本轮动作

只做最小约束：

- `pkg/types.go` 成为 strategy / assembler / service 共享类型唯一入口
    
- 不再在 `metering/event.go` 或 `service.go` 重复定义 `StrategyEffectiveness` 结构
    

如果已经重复，就删副本，只保留 `pkg.StrategyEffectiveness`。

---

## 7. CC 实施顺序

按这个顺序做，不要乱：

### Step 1

修 `app/context/assembler.go`

- `AssemblyResult` 增加 `RawTokens`、`AssembledHits`、`ResolvedStrategy`
    
- assembly 内真实汇总 raw tokens
    

### Step 2

修 `app/service.go`

- 删除 `compressed * 2` 推导
    
- metering 用 `resolvedStrategy`
    
- assembly off 时四字段清零
    

### Step 3

修 `strategy_topk.go` / `strategy_recency.go`

- 替换 `efficiencyScore` 为带最小 token floor 的版本
    

### Step 4

处理 cache

- 彻底禁用当前 cache 接入点
    
- 留清晰注释，不启用
    

### Step 5

删除旧版 assembly helper

- 清理 service 内旧函数
    
- 保证只走 `ctxAssembler`
    

### Step 6

补测试

---

## 8. 必加测试清单

### A. Metering 诚实口径

1. `assemble_context=false` → `raw/compressed/saved/assembled_hits = 0`
    
2. `assemble_context=true` → `raw = sum(item.tokens)`
    

### B. Auto strategy 口径

3. request=`auto`，resolved=`topk_excerpt`  
    → response.strategy=`topk_excerpt`  
    → metering.context_strategy=`topk_excerpt`
    

### C. Scope 不回退

4. 不同 workspace 相同 query，不得共享任何 assembler 结果
    
5. strategy 逻辑始终发生在 SQL recall 之后
    

### D. 排序风险回归

6. 短文本不会因为 token 极小而稳定压制正常内容
    

### E. 旧逻辑移除

7. 全项目无旧 `assembleContext()` 调用残留
    

---

## 9. 给 CC 的直接执行指令

把下面这段直接丢给 CC：

```text
执行 Phase 2c.5 修复，仅修复，不新增功能。

目标：
1. 修复 raw_tokens 诚实口径
2. 修复 auto strategy 的 metering 口径
3. 禁用当前半成品 cache
4. 收敛 efficiencyScore 对短文本的极端偏置
5. 删除旧版 assembleContext 遗留

具体要求：

A. app/context/assembler.go
- 扩展 AssemblyResult:
  - RawTokens int
  - AssembledHits int
  - ResolvedStrategy string
- 在 assembly 完成后：
  - RawTokens = sum(selectedItems.Tokens)
  - AssembledHits = len(selectedItems)

B. app/service.go
- 删除任何 raw_tokens = compressed * N 或 TotalTokens * N 的逻辑
- 当 assemble_context=true:
  - raw_tokens = ctxResult.RawTokens
  - compressed_tokens = ctxResult.Context.TotalTokens
  - saved_tokens = max(raw_tokens - compressed_tokens, 0)
  - assembled_hits = ctxResult.AssembledHits
- 当 assemble_context=false:
  - raw_tokens = 0
  - compressed_tokens = 0
  - saved_tokens = 0
  - assembled_hits = 0
- recordSearchMetering 必须记录 resolved strategy，不记录原始 "auto"

C. strategy_topk.go / strategy_recency.go
- 将 efficiencyScore 改为带 token floor 的版本：
  - tokens < 80 时按 80 处理
- 不引入新排序系统

D. cache
- 本轮不要启用 cache
- 删除或禁用 assembler 中所有 cache 调用路径
- 注释说明：cache postponed pending dedicated scope-isolation audit

E. cleanup
- 删除 app/service.go 中旧版 assembleContext 及其仅旧逻辑使用的 helper
- 确保 SearchMemory 只走 ctxAssembler

F. tests
新增以下测试：
1. assemble_context=false → token fields all zero
2. assemble_context=true → raw_tokens = sum(item.tokens)
3. context_strategy=auto → metering records resolved strategy
4. short text does not dominate ranking purely due to tiny token count
5. no old assembleContext path remains in use

要求：
- 不改 API path
- 不新增新策略
- 不引入 cache
- 不引入 query understanding / reranker / pipeline
- build + tests 全通过
```

---

## 10. 这轮修完后的判定标准

修完后，才允许重新审计。  
重审只看 4 件事：

- P0 是否清零
    
- `raw_tokens` 是否真实
    
- metering 是否记录 resolved strategy
    
- 是否只剩单一 assembly 路径
    

只要这 4 个过了，Phase 2c.5 才算真正收口。

