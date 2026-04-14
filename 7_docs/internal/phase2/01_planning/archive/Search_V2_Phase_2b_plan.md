下面给你一版 **`/memory/search V2 Phase 2b 最终工程大纲`**。这版是承接你们已经完成的 Phase 2a：**不重做 recall/ranking，只在其上加最小可用的 context assembly**。

我会把范围压死，避免又做成一个过大的 retrieval engine。这个设计继续遵守 Runtime 的既有职责边界：`/memory/search` 属于 Local Runtime 核心 API，负责本地检索、scope 治理与计量；完整产品价值要最终对齐 Token Savings，但不应引入云端依赖或突破 Store 抽象。

---

# OmniMemora `/memory/search` V2 Phase 2b 最终工程大纲

## 1. 目标

把 Phase 2a 的：

```text
scope-aware recall + ranking + top-k
```

升级为：

```text
ranked results + lightweight context assembly
```

让 `/memory/search` 不只是返回排好序的结果列表，而是能额外返回一份**可直接供 agent 使用的轻量上下文块**。

---

## 2. 本阶段范围

## 2.1 要做

### A. Excerpt 提取

- 从 top-k 结果中提取与 query 最相关的片段
    
- 不默认返回整条全文作为 assembled context
    

### B. Context Assembly

- 将 3~5 条 excerpt 组装成一个轻量 context block
    
- 保留来源标识，便于审计与解释
    

### C. Token Budget 控制

- 对 assembled context 设置总 token 上限
    
- 超预算时裁剪尾部或缩短 excerpt
    

### D. Search Token Savings 真正落地

- 计算 `raw_tokens`
    
- 计算 `compressed_tokens`
    
- 计算 `saved_tokens`
    

### E. Response 扩展兼容

- 保留 Phase 2a 的 `results/total/scope_applied/took_ms`
    
- 新增 `context` 字段，但不替换旧字段
    

---

## 2.2 不做

### 本阶段明确不做

- sqlite-vss / 向量检索实装
    
- hybrid retrieval
    
- cluster-based assembly
    
- timeline assembly
    
- 多策略自动 assembly 路由
    
- 默认返回完整 explainability
    
- 复杂摘要模型/LLM压缩
    

这些放到后续阶段，否则 Phase 2b 会再次失控。

---

# 3. 阶段定位

## Phase 2a（已完成）

```text
Ranking Search
```

## Phase 2b（当前）

```text
Lightweight Context Assembly
```

## Phase 2c（未来）

```text
Vector / Hybrid Retrieval + Rich Explainability
```

---

# 4. 设计原则

## 原则 1：不重做 Phase 2a

Phase 2b 直接复用已完成的：

- scope-aware candidate recall
    
- ranking
    
- top-k 截断
    
- response 扩展兼容基础
    

不要把 2b 变成“把 2a 再写一遍”。

---

## 原则 2：assembly 是附加能力，不是替代结果列表

`results` 仍然保留。  
`context` 是新增输出，不是强制替代输出。

这样老调用方继续兼容，新调用方可以消费 context block。

---

## 原则 3：只做轻量压缩，不做智能摘要

当前只做：

- excerpt 窗口提取
    
- 去冗余
    
- 拼接
    
- token budget 裁剪
    

不做模型摘要，不引入新依赖。

---

## 原则 4：Token Savings 必须真实

Phase 2a 里 `saved_tokens=0` 是诚实做法。  
到了 Phase 2b，既然有了 excerpt + merge + budget，就应该真正计算 search savings，这与 Token Savings 是核心产品能力的宪法要求一致。

---

# 5. API 兼容策略

## 5.1 Endpoint 不变

继续使用：

```http
POST /memory/search
```

不改 path。

---

## 5.2 Request 扩展

建议在 Phase 2a 基础上新增：

```json
{
  "keyword": "sqlite scope filter",
  "scope": "workspace",
  "agent_id": "claude_code",
  "workspace_id": "proj_alpha",
  "limit": 10,
  "request_id": "req_xxxxx",
  "options": {
    "include_breakdown": false,
    "assemble_context": true,
    "context_limit": 4,
    "max_context_tokens": 800
  }
}
```

---

## 5.3 新增 request 字段说明

### `options.assemble_context`

- 类型：`bool`
    
- 默认：`false`
    
- 含义：是否返回 `context`
    

### `options.context_limit`

- 类型：`int`
    
- 默认：`4`
    
- 含义：参与 context assembly 的最大条数
    

### `options.max_context_tokens`

- 类型：`int`
    
- 默认：`800`
    
- 含义：assembled context 的 token 上限
    

---

# 6. Response 结构

## 6.1 保留 Phase 2a 兼容基线

```json
{
  "request_id": "req_xxxxx",
  "results": [...],
  "total": 10,
  "scope_applied": "workspace",
  "took_ms": 5
}
```

---

## 6.2 新增 `context` 字段

仅当 `assemble_context=true` 时返回：

```json
{
  "context": {
    "assembled": true,
    "strategy": "topk_excerpt_merge",
    "items": [
      {
        "memory_id": "mem_001",
        "excerpt": "....",
        "score": 0.91,
        "token_estimate": 48
      },
      {
        "memory_id": "mem_008",
        "excerpt": "....",
        "score": 0.86,
        "token_estimate": 55
      }
    ],
    "combined_text": "【Memory mem_001】...\n【Memory mem_008】...",
    "raw_tokens": 640,
    "compressed_tokens": 220,
    "saved_tokens": 420
  }
}
```

---

## 6.3 字段说明

### `assembled`

是否成功组装 context。

### `strategy`

当前固定为：

```text
topk_excerpt_merge
```

### `items`

进入最终 context 的条目列表。

### `combined_text`

最终交给 agent 的轻量上下文文本。

### `raw_tokens`

若把入选结果全文直接交给 agent，需要的估算 token。

### `compressed_tokens`

实际 assembled context 的 token 估算值。

### `saved_tokens`

`raw_tokens - compressed_tokens`

---

# 7. Context Assembly 方案

## 7.1 总体流程

```text
Phase 2a top-k results
→ choose context candidates
→ excerpt extraction
→ dedup / trim
→ token budget enforcement
→ combine text
→ compute search savings
```

---

## 7.2 候选条目选择

不要直接拿全部 `results` 组装。

建议：

```text
assembly_candidate_count = min(context_limit, len(results), 5)
```

默认取前 3~5 条。

---

## 7.3 Excerpt 提取规则

这是 Phase 2b 最核心的能力。

### 规则 A：优先命中窗口

如果 keyword 在 content 中命中：

- 取命中位置前后窗口
    
- 建议窗口大小：`120 ~ 300` 字符
    
- 如果多次命中，优先第一处或最密集处
    

### 规则 B：短文本直接保留

如果全文本身很短，例如：

```text
len(content) <= 300 chars
```

则直接使用全文。

### 规则 C：无明确命中时取首段

如果是 fallback 场景、命中位置不稳定，取首段或前 200~300 字。

### 规则 D：去首尾空白与无意义重复换行

避免 assembled text 难看。

---

## 7.4 excerpt 长度建议

先定一个简单上限：

```text
max_excerpt_chars_per_item = 280
```

后续如需更细化，再扩。

---

## 7.5 去冗余规则

只做轻量版。

### 规则

若两个 excerpt：

- 完全相同
    
- 或归一化后高度接近
    

则只保留分数更高的一条。

### Phase 2b 不做

- 复杂语义聚类
    
- LSH/embedding redundancy detection
    

---

# 8. Token Budget 控制

## 8.1 目标

assembled context 必须受控，不能为了“多给点上下文”反而吞掉 token savings。

---

## 8.2 默认配置

建议默认：

```text
context_limit = 4
max_context_tokens = 800
```

可放入 request options，后续也可进入 config。

---

## 8.3 token 估算方式

沿用 Runtime 当前粗估口径：

```text
estimated_tokens = len(text) / 4
```

这和 Runtime 当前 token 粗估逻辑一致，足够做 Phase 2b。

---

## 8.4 裁剪顺序

当总 token 超过 `max_context_tokens` 时：

### 第一步

先裁剪最后一条 excerpt 长度

### 第二步

仍超限，则移除最低分条目

### 第三步

直到不超预算

---

## 8.5 保底规则

即使预算很紧，也至少保留：

```text
top 1 excerpt
```

避免 `assembled=true` 但 `combined_text` 为空。

---

# 9. `combined_text` 结构

## 9.1 推荐格式

```text
[Memory mem_001 | score=0.91]
excerpt text...

[Memory mem_008 | score=0.86]
excerpt text...
```

或更简化：

```text
【Memory mem_001】
...

【Memory mem_008】
...
```

---

## 9.2 原则

- 结构清晰
    
- 保留来源 ID
    
- 不要太花
    
- 便于 agent 直接消费
    

---

# 10. Token Savings 计算

## 10.1 这是 Phase 2b 的关键闭环

当前 Blueprint / Constitution / Runtime Architecture 都要求 Token Savings 是核心产品能力，且 Runtime 需要为后续聚合提供可信来源。

---

## 10.2 定义

### `raw_tokens`

定义为：

```text
sum(full_content_token_estimate of selected context items)
```

也就是：如果把参与 assembly 的这些结果全文直接给 agent，要花多少 token。

---

### `compressed_tokens`

定义为：

```text
token_estimate(combined_text)
```

---

### `saved_tokens`

定义为：

```text
raw_tokens - compressed_tokens
```

最小值为 0，不允许负值。

---

## 10.3 注意

`raw_tokens` 的基数必须只取**参与 assembly 的条目**，不要拿全部 recall candidates，否则数会虚高。

---

# 11. Metering 对齐

## 11.1 事件模型

Phase 2a 已有 `memory_search` 事件。Phase 2b 继续复用，但这次要把 savings 算真。

建议事件结构：

```json
{
  "event_type": "memory_search",
  "request_id": "req_xxxxx",
  "user_id": "u_xxxxx",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "scope": "workspace",
  "query_count": 1,
  "recall_hits": 12,
  "returned_hits": 5,
  "assembled_hits": 4,
  "input_tokens": 5,
  "raw_tokens": 640,
  "compressed_tokens": 220,
  "saved_tokens": 420,
  "assembly_mode": "topk_excerpt_merge",
  "timestamp": "2026-04-09T00:00:00Z"
}
```

---

## 11.2 字段补充说明

### `assembled_hits`

最终进入 context assembly 的条数。

### `raw_tokens`

全文输入成本。

### `compressed_tokens`

组装后上下文成本。

### `saved_tokens`

真实节省量。

---

## 11.3 无 assembly 的情况

如果 `assemble_context=false`：

- 仍可发 `memory_search` 事件
    
- `assembled_hits = 0`
    
- `raw_tokens = 0`
    
- `compressed_tokens = 0`
    
- `saved_tokens = 0`
    

这样事件口径统一。

---

# 12. Go 数据结构建议

## 12.1 Request Options 扩展

```go
type SearchOptions struct {
    IncludeBreakdown bool `json:"include_breakdown,omitempty"`
    AssembleContext  bool `json:"assemble_context,omitempty"`
    ContextLimit     int  `json:"context_limit,omitempty"`
    MaxContextTokens int  `json:"max_context_tokens,omitempty"`
}
```

---

## 12.2 Context Item

```go
type ContextItem struct {
    MemoryID      string  `json:"memory_id"`
    Excerpt       string  `json:"json:"excerpt"`
    Score         float64 `json:"score"`
    TokenEstimate int     `json:"token_estimate"`
}
```

注意：这里实现时修正标签，不要把 `json:"json:"excerpt"` 这种笔误带进去。应为：

```go
Excerpt string `json:"excerpt"`
```

---

## 12.3 Context Block

```go
type AssembledContext struct {
    Assembled        bool          `json:"assembled"`
    Strategy         string        `json:"strategy"`
    Items            []ContextItem `json:"items"`
    CombinedText     string        `json:"combined_text"`
    RawTokens        int           `json:"raw_tokens"`
    CompressedTokens int           `json:"compressed_tokens"`
    SavedTokens      int           `json:"saved_tokens"`
}
```

---

## 12.4 Response 扩展

```go
type SearchResponse struct {
    RequestID    string             `json:"request_id"`
    Results      []SearchResultItem `json:"results"`
    Total        int                `json:"total"`
    ScopeApplied string             `json:"scope_applied"`
    TookMs       int64              `json:"took_ms"`
    Context      *AssembledContext  `json:"context,omitempty"`
}
```

---

# 13. 处理流程伪代码

```text
handleSearch(request):
  1. execute existing Phase 2a search flow
     - scope resolve
     - candidate recall
     - ranking
     - top-k results

  2. if !request.options.assemble_context:
       emit basic memory_search event
       return response without context

  3. determine context_limit
     - default 4
     - clamp to [1, 5]

  4. determine max_context_tokens
     - default 800
     - clamp to sane min/max

  5. select top context candidates from ranked results

  6. for each candidate:
       excerpt = extractExcerpt(candidate.content, request.keyword)
       excerpt_tokens = estimateTokens(excerpt)
       full_tokens = estimateTokens(candidate.content)

  7. dedup excerpts lightly

  8. assemble combined text in order

  9. enforce token budget
       - trim last excerpt
       - if still over, drop lowest ranked tail item
       - keep at least one item

  10. compute:
        raw_tokens = sum(full_tokens of assembled items)
        compressed_tokens = estimateTokens(combined_text)
        saved_tokens = max(raw_tokens - compressed_tokens, 0)

  11. attach context block to response

  12. emit memory_search event with assembled_hits/raw/compressed/saved

  13. return response
```

---

# 14. 核心函数建议

## 14.1 `extractExcerpt(content, keyword) string`

职责：

- 找命中窗口
    
- 返回 excerpt
    

---

## 14.2 `estimateTokens(text) int`

职责：

- `len(text) / 4`
    

---

## 14.3 `dedupContextItems(items []ContextItem) []ContextItem`

职责：

- 去掉重复 excerpt
    

---

## 14.4 `enforceContextBudget(items []ContextItem, maxTokens int) ([]ContextItem, string)`

职责：

- 控制预算
    
- 返回最终 items 与 combined_text
    

---

## 14.5 `buildCombinedText(items []ContextItem) string`

职责：

- 用统一格式拼接
    

---

# 15. 测试用例清单

## 15.1 Excerpt 提取

### Case 1

keyword 在正文中部命中  
预期：返回命中窗口，而不是整篇全文

### Case 2

短文本命中  
预期：返回全文

### Case 3

无明确命中位置  
预期：返回首段

---

## 15.2 Context Assembly

### Case 4

`assemble_context=false`  
预期：无 `context` 字段

### Case 5

`assemble_context=true`  
预期：返回 `context`

### Case 6

`context_limit=2`  
预期：最多 2 条 item 进入 assembly

---

## 15.3 Token Budget

### Case 7

assembled context 未超预算  
预期：完整保留

### Case 8

超预算  
预期：裁剪 excerpt 或减少条目，最终不超限

### Case 9

预算极小  
预期：仍至少保留 1 条 item

---

## 15.4 Savings 计算

### Case 10

assembled context 成功  
预期：`saved_tokens = raw_tokens - compressed_tokens`

### Case 11

压缩收益很低  
预期：`saved_tokens >= 0`，不出现负数

### Case 12

`assemble_context=false`  
预期：`saved_tokens=0`

---

## 15.5 Scope 不回退

### Case 13

workspace A 数据在 workspace B search 中  
预期：即使 assembly 开启，也绝不能混入

### Case 14

agent scope 下跨 agent  
预期：绝不泄漏

这必须继续遵守 Runtime 的 SQL scope enforcement 原则。

---

# 16. 验收标准

## 功能验收

- `assemble_context=true` 时可返回 context block
    
- excerpt 基本合理
    
- token budget 有效
    
- savings 计算真实且非负
    

## 兼容验收

- 老客户端不受影响
    
- `results` 结构仍可用
    
- 新字段为扩展，不替换旧字段
    

## 架构验收

- 不改 endpoint path
    
- 不引入云端依赖
    
- 不绕过现有 ranking/scope enforcement
    
- 不提前引入向量检索
    

## 产品验收

- `/memory/search` 从“排序检索”进入“轻量 context retrieval”
    
- search 终于能与 Token Savings 核心能力真实挂钩
    

---

# 17. 交给 CC 的一句话施工指令

```text
实现 /memory/search V2 Phase 2b：在现有 Phase 2a recall/ranking/top-k 基础上，新增可选 context assembly；支持 excerpt 提取、top-k excerpt merge、token budget 控制、真实 raw/compressed/saved token 计算；通过 options.assemble_context/context_limit/max_context_tokens 控制行为；保持 response 扩展兼容，不替换 results 结构；继续遵守现有 scope enforcement 与 memory_search metering 链路。
```
