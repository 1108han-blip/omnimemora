
# 🚀 `/memory/search V2 — Phase 2c 工程大纲（最终可执行版）`

## 一、Phase 2c 定义（锁死）

> Phase 2c = **Context Intelligence Layer**

在不破坏当前 Runtime 架构的前提下：

```
search → ranking → context assembly
        ↓
   strategy-driven
```

👉 从“拼接”升级为“策略驱动上下文构造”

---

## 二、设计边界（必须遵守）

来自产品宪法：

### ✅ 必须保证

- Local Runtime 内完成（Local First）
    
- 不依赖 cloud
    
- scope 不被破坏（SQL 仍是唯一安全边界）
    
- metering 可追踪
    
- API 向后兼容
    

---

### ❌ 禁止做的事

- ❌ 不做新存储层
    
- ❌ 不引入复杂 vector infra（仅预留）
    
- ❌ 不改 search 基础接口语义
    
- ❌ 不把策略写死在代码
    

---

## 三、核心架构（Phase 2c 新增层）

### 当前结构

```
Search → Ranking → Context Assembly（硬编码）
```

---

### Phase 2c 结构

```
Search
  ↓
Ranking
  ↓
Context Strategy Layer  ←【新增】
  ↓
Context Assembly
  ↓
Metering
```

---

## 四、核心抽象（必须先落地）

### 1️⃣ ContextStrategy 接口（核心）

```go
type ContextStrategy interface {
    Name() string

    // 输入：search结果 + query
    Select(results []SearchResult, query string, opts StrategyOptions) []ContextItem

    // 输出：最终上下文
    Assemble(items []ContextItem, opts StrategyOptions) AssembledContext
}
```

---

### 2️⃣ 数据结构

#### ContextItem

```go
type ContextItem struct {
    MemoryID   string
    Content    string
    Score      float64
    Tokens     int
    CreatedAt  time.Time
}
```

---

#### AssembledContext

```go
type AssembledContext struct {
    Text               string
    TotalTokens        int
    UsedItems          int
    CompressionRatio   float64
}
```

---

#### StrategyOptions

```go
type StrategyOptions struct {
    Mode           string // precise / balanced / aggressive
    TokenBudget    int
    MaxItems       int
}
```

---

## 五、内置策略（Phase 2c 必做）

至少 3 个，不然 Phase 2c 不成立。

---

### ✅ 1. topk_excerpt（当前逻辑升级版）

```text
策略：
- 按 score 排序
- 取 top-k
- 截断 token_budget
```

👉 这是 baseline

---

### ✅ 2. recency_boost_select

```text
策略：
- 优先选最近数据
- score + recency 混合排序
- 防止旧数据霸榜
```

---

### ✅ 3. diversity_select（关键）

```text
策略：
- 去重（相似内容）
- 保证信息覆盖面
```

实现简化版：

```text
if similarity(content_i, content_j) > threshold:
    skip
```

（Phase 2c 可用简单 hash/substring，不需要 embedding）

---

### ✅ 4（可选加分）qa_focus

```text
策略：
- 优先包含 query 关键词完整匹配的条目
- 提高 QA 命中率
```

---

## 六、API 扩展（必须兼容）

### Request

```json
{
  "query": "xxx",
  "options": {
    "assemble_context": true,
    "context_strategy": "topk_excerpt",
    "context_mode": "balanced"
  }
}
```

---

### 默认行为（关键）

```text
不传 = 兼容旧版本
```

等价于：

```json
{
  "assemble_context": false
}
```

---

## 七、Context Mode（用户价值层）

这个是产品关键，不是技术细节。

|mode|行为|
|---|---|
|precise|少 + 高相关|
|balanced|默认|
|aggressive|多 + 压缩|

---

### 实现映射

```go
func ResolveOptions(mode string) StrategyOptions {
    switch mode {
    case "precise":
        return {TokenBudget: 300, MaxItems: 3}
    case "balanced":
        return {TokenBudget: 800, MaxItems: 6}
    case "aggressive":
        return {TokenBudget: 1500, MaxItems: 10}
    }
}
```

---

## 八、策略调度器（核心 glue）

```go
func ResolveStrategy(name string) ContextStrategy {
    switch name {
    case "topk_excerpt":
        return TopKStrategy{}
    case "recency_boost":
        return RecencyStrategy{}
    case "diversity":
        return DiversityStrategy{}
    default:
        return TopKStrategy{}
    }
}
```

---

## 九、Search Pipeline（最终形态）

```go
results := SearchAndRank(query)

if !options.AssembleContext {
    return results
}

strategy := ResolveStrategy(options.ContextStrategy)
opts := ResolveOptions(options.ContextMode)

items := strategy.Select(results, query, opts)
context := strategy.Assemble(items, opts)

return Response{
    Results: results,
    Context: context,
}
```

---

## 十、Metering 升级（Phase 2c 关键）

必须接入：

来自 Runtime 定义：

---

### 新增字段

```json
{
  "event_type": "memory_search",
  "context_strategy": "topk_excerpt",
  "context_mode": "balanced",
  "raw_tokens": 1200,
  "compressed_tokens": 600,
  "saved_tokens": 600,
  "assembled_hits": 5
}
```

---

### 注意（必须符合你锁死规则）

```
assemble_context=false
→ 所有 token 字段 = 0
```

---

## 十一、Context Cache（性能关键点）

```go
cache_key = hash(query + scope + strategy + mode)

if cache_hit:
    return cached_context
```

---

## 十二、测试用例（必须覆盖）

### 1. 策略切换

- topk → diversity → recency
    
- 输出不同 ✔
    

---

### 2. token budget

- 不超过 budget ✔
    

---

### 3. scope 安全

- workspace 不泄露 agent ✔
    

---

### 4. metering

- raw_tokens 正确 ✔
    
- saved_tokens 正确 ✔
    

---

### 5. fallback

- strategy 不存在 → default ✔
    

---

## 十三、代码结构（建议）

```
/runtime/search/
  search.go

/runtime/context/
  strategy.go
  strategy_topk.go
  strategy_diversity.go
  strategy_recency.go
  assembler.go

/runtime/metering/
  search_metering.go
```

---

## 十四、验收标准（必须全满足）

-  context_strategy 可切换
    
-  ≥3 策略实现
    
-  token savings 正确
    
-  scope 不破坏
    
-  API 兼容
    
-  metering 有策略维度
    
-  context 可缓存
    

---

## 十五、一句话结论（给你压一下方向）

> Phase 2b 解决的是「有没有 context」  
> Phase 2c 解决的是「context 怎么变聪明」

---

## 最后一句（不拐弯）

你现在这一步如果只是“再优化 search”——

👉 你会停在工具层

但你如果把 **strategy layer 做出来**——

👉 OmniMemora 就进入 **Control Plane 雏形**

---

准备好了你可以直接说：

```
拆 Phase 2c → 代码实现步骤（逐文件级）
```

我会带你一刀一刀把它落到代码，不留虚的。