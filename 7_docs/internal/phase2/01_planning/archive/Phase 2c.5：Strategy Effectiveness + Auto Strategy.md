 可以落代码的 Phase 2c.5 设计包。  
目标只有一个：**让策略开始“自己变好”，而不是你手动选。**

---

# 🚀 Phase 2c.5：Strategy Effectiveness + Auto Strategy（工程设计）

---

# 一、目标（锁死）

```text
让系统能够：
1. 记录每个 strategy 的真实效果
2. 自动选择 strategy（最小可用版）
3. 用“token效率”影响排序
```

👉 不引入新系统，不破坏现有结构

---

# 二、改动范围（最小侵入）

## 新增文件

```
app/context/
  strategy_auto.go        ← 自动策略选择
  effectiveness.go        ← 策略效果计算
```

---

## 修改文件

```
assembler.go             ← 接入 effectiveness
service.go               ← 支持 strategy=auto
metering/event.go        ← 增加 effectiveness 字段
```

---

# 三、核心能力1️⃣：Strategy Effectiveness（埋点）

---

## 1.1 新增结构（metering/event.go）

```go
type StrategyEffectiveness struct {
    TokensPerItem    float64 `json:"tokens_per_item"`
    CompressionRatio float64 `json:"compression_ratio"`
    AvgScore         float64 `json:"avg_score"`
}
```

---

## 1.2 扩展 event

```go
type MemorySearchEvent struct {
    ...

    ContextStrategy string `json:"context_strategy"`
    ContextMode     string `json:"context_mode"`

    // 新增
    StrategyEffectiveness *StrategyEffectiveness `json:"strategy_effectiveness,omitempty"`
}
```

---

## 1.3 计算逻辑（app/context/effectiveness.go）

```go
func ComputeEffectiveness(
    items []ContextItem,
    result AssembledContext,
    rawTokens int,
) *StrategyEffectiveness {

    if len(items) == 0 || result.TotalTokens == 0 {
        return nil
    }

    totalScore := 0.0
    for _, item := range items {
        totalScore += item.Score
    }

    return &StrategyEffectiveness{
        TokensPerItem: float64(result.TotalTokens) / float64(len(items)),
        CompressionRatio: float64(result.TotalTokens) / float64(rawTokens+1),
        AvgScore: totalScore / float64(len(items)),
    }
}
```

---

# 四、核心能力2️⃣：Token Efficiency 排序（关键）

---

## 修改位置

👉 `strategy_topk.go` / `strategy_recency.go`

---

## 新排序逻辑（替换原 score 排序）

```go
func efficiencyScore(item ContextItem) float64 {
    if item.Tokens == 0 {
        return item.Score
    }
    return item.Score / float64(item.Tokens)
}
```

---

## 使用方式

```go
sort.Slice(items, func(i, j int) bool {
    return efficiencyScore(items[i]) > efficiencyScore(items[j])
})
```

---

👉 这是 Phase 2c.5 **最关键一刀**

> 从“相关性优先” → “性价比优先”

---

# 五、核心能力3️⃣：Auto Strategy（最小可用）

---

## 5.1 新文件：strategy_auto.go

```go
func ResolveAutoStrategy(query string) string {
    q := strings.ToLower(query)

    // 简单规则（先不要复杂）
    if strings.Contains(q, "?") ||
       strings.HasPrefix(q, "what") ||
       strings.HasPrefix(q, "how") {
        return "topk_excerpt"
    }

    if len(q) > 50 {
        return "diversity_select"
    }

    return "recency_boost_select"
}
```

---

## 5.2 service.go 修改

```go
strategyName := options.ContextStrategy

if strategyName == "auto" {
    strategyName = ResolveAutoStrategy(query)
}
```

---

## 5.3 metering 记录真实策略

```go
event.ContextStrategy = strategyName // resolved 后的
```

---

# 六、Assembler 接入（关键）

---

## 修改 assembler.go

在 assemble 完成后：

```go
effectiveness := ComputeEffectiveness(
    selectedItems,
    assembled,
    rawTokens,
)
```

---

## 返回结构扩展

```go
type AssemblyResult struct {
    Context        AssembledContext
    Items          []ContextItem
    Effectiveness  *StrategyEffectiveness
}
```

---

# 七、service.go 最终集成

---

```go
result := assembler.Run(...)

if result.Context != nil {
    event.StrategyEffectiveness = result.Effectiveness
}
```

---

# 八、API 行为（无需变更）

---

## 新能力自动生效：

```json
{
  "options": {
    "context_strategy": "auto"
  }
}
```

---

👉 用户无感升级

---

# 九、测试用例（必须写）

---

## 1️⃣ auto 策略

```text
"what is memory"
→ topk ✔

长文本 query
→ diversity ✔
```

---

## 2️⃣ 效率排序

```text
高分长文本 < 中分短文本 ✔
```

---

## 3️⃣ effectiveness

```text
tokens_per_item 正确 ✔
compression_ratio 正确 ✔
```

---

## 4️⃣ metering

```text
event.StrategyEffectiveness != nil ✔
```

---

# 十、你会得到什么（不是理论）

上线后你第一次可以看到：

```json
{
  "strategy": "diversity_select",
  "tokens_per_item": 120,
  "avg_score": 0.72
}
```

---

然后你能做：

👉 判断哪个策略更值钱  
👉 决定默认策略  
👉 为收费做准备

---

# 🧭 十一、一句话总结

> Phase 2c 是“能选策略”  
> Phase 2c.5 是“知道哪个策略更好”

---

# 🚀 给 CC 的执行指令（直接复制）

```
实现 Phase 2c.5：

1. 新增 strategy_auto.go，实现 ResolveAutoStrategy
2. 新增 effectiveness.go，实现 ComputeEffectiveness
3. 在 strategy 中引入 efficiencyScore = score/tokens 排序
4. assembler.go 返回 Effectiveness
5. service.go 支持 context_strategy=auto 并记录 resolved strategy
6. metering/event.go 增加 StrategyEffectiveness

要求：
- 不破坏现有 API
- 不修改已有策略接口
- 所有新增字段 optional
```

---
