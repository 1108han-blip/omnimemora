
## 需要立刻修正的点

### 1. BM25 不能先写进主设计

这个必须改。

你现在的 Runtime 蓝图里只明确了 **SQLite FTS5** 是默认全文索引，`sqlite-vss` 只是“可选 / Future”，不是当前已锁定能力。  
所以 `/memory/search V2` 设计里不能把 `bm25()` 当既成事实。

正确写法应该是：

```text
FTS5 MATCH = 主召回路径
BM25 = 优先使用（若驱动支持）
否则退化到应用层文本匹配评分
```

也就是说，**BM25 是优化项，不是前提项**。

---

### 2. Context Assembly 确实超范围

这个判断也对。

如果现在把这些一起做进去：

- excerpt 提取
    
- token budget
    
- combined context
    
- compression ratio
    
- assembly strategy
    

那已经不是“search V2”，而是半个 retrieval engine 了。  
对你当前阶段来说，会把 Phase 2 拉长，而且容易把接口一次性做重。

更稳的切法应该是：

```text
Phase 2a = recall + ranking
Phase 2b = context assembly
Phase 2c = vector / explainability
```

这也更符合 Runtime 现阶段已经落地的 MVP API 路径：先把 `/memory/search` 做成更强的关键词检索，再逐步向上下文组装演进。

---

### 3. “不改接口”这个表述要收回

CC说得对。

我之前说“不改接口”，准确意思本来是：

```text
不改 endpoint path，不改基本调用方式
```

但**响应结构扩展了，就已经是接口行为变化**。  
所以应该改成：

```text
保持 endpoint 兼容，Response 扩展而非替换
```

这是更严谨的说法。

---

## 可以吸收，但先只做预留的点

### 4. 向量检索路径

这个建议方向是对的，但别提前把 Phase 2 搞复杂。

因为 Runtime Architecture 里确实把 `sqlite-vss` 写成了可选方向，MVP 可跳过。  
所以现在最合理的处理不是“做向量检索”，而是：

```text
在评分结构里预留 vector_score 字段
当前固定为 0 或 nil
```

这样后面接入向量路径时，不需要再推翻返回模型。

---

# 修正版路线图

我建议你把 `/memory/search V2` 正式收敛成下面这个版本。

---

# `/memory/search V2` 修正版大纲

## Phase 2a：Ranking Search

目标：

```text
在不破坏现有接口兼容性的前提下，
把 search 从“命中即可”升级为“命中 + 排序更合理”
```

### 范围

只做三件事：

1. scope-aware candidate recall
    
2. recency/access ranking
    
3. top-k 返回
    

### 暂不做

- excerpt
    
- combined context
    
- token budget
    
- score_breakdown 默认返回
    
- 向量检索实装
    

---

## 一、Ranking 公式（Phase 2a）

采用可落地的轻量模型：

```text
final_score =
  text_match_score
+ recency_boost
+ access_boost
+ vector_score_reserve
```

其中：

```text
vector_score_reserve = 0
```

当前只是占位。

### 1. `text_match_score`

来源优先级：

```text
bm25() if available
否则应用层 fallback_text_score
```

#### BM25 可用时

- 使用 FTS5 `MATCH`
    
- 取 BM25 分数做归一化
    
- 注意 BM25 越小越相关，应用层需转成“分数越高越好”
    

例如：

```text
text_match_score = normalize_inverse_bm25(raw_bm25)
```

#### BM25 不可用时

fallback 评分建议：

```text
exact phrase hit      = 1.00
all terms matched     = 0.80
partial terms matched = 0.50
LIKE only             = 0.30
```

这样就不依赖具体驱动特性。

---

### 2. `recency_boost`

建议先做分层，不做指数函数。

```text
≤ 1 day     +0.10
≤ 7 days    +0.07
≤ 30 days   +0.04
≤ 90 days   +0.01
> 90 days   +0
```

---

### 3. `access_boost`

```text
access_boost = min(log(1 + access_count) / 10, 0.08)
```

如果当前 `access_count` 还没被稳定更新，也可以先做简化版：

```text
0 hit  -> 0
1-3    -> +0.02
4-10   -> +0.05
10+    -> +0.08
```

---

### 4. `vector_score_reserve`

```json
{
  "vector_score": 0
}
```

只做字段预留，不做计算。

因为 Blueprint/Roadmap 方向允许未来扩展，但当前 MVP 仍以 SQLite/FTS5 为主。

---

## 二、SQL + scoring 方案（Phase 2a）

### 方案原则

坚持两阶段：

```text
SQL recall
→ app layer scoring
→ sort
→ top-k
```

不要把所有逻辑塞进 SQL。

---

### 1. Candidate Recall

#### 主路径

```sql
... WHERE tenant_id = ?
      AND scope = 'workspace'
      AND workspace_id = ?
      AND memories_fts MATCH ?
LIMIT ?
```

这必须继续沿用你已经落地的 SQL scope enforcement 原则：`tenant_id` 必过滤，scope 精确匹配。

#### 退化路径

如果：

- FTS5 不可用
    
- query 语法不合法
    
- BM25 不可用但 MATCH 仍可用
    

则退回：

```sql
content LIKE ? 
```

但 recall 数量要放大。

---

### 2. Candidate 数量

建议：

```text
candidate_limit = max(limit * 3, 20)
```

然后应用层再排序截断。

---

### 3. 应用层评分

应用层统一计算：

- `text_match_score`
    
- `recency_boost`
    
- `access_boost`
    
- `vector_score`
    

然后：

```text
final_score = text_match_score + recency_boost + access_boost + vector_score
```

---

### 4. 排序

按：

```text
final_score DESC
created_at DESC
memory_id ASC
```

第二、第三排序键用于稳定结果，避免相同分数乱跳。

---

## 三、Response 兼容方案

这个点要写死：

```text
扩展，不替换
```

### 当前兼容基线

保留现有核心字段：

```json
{
  "request_id": "req_xxxxx",
  "results": [...],
  "total": 10,
  "scope_applied": "workspace",
  "took_ms": 5
}
```

### 新增字段

在 `results[i]` 内可选增加：

```json
{
  "memory_id": "mem_001",
  "content": "...",
  "score": 0.91,
  "vector_score": 0,
  "token_estimate": 42
}
```

### breakdown 控制

增加请求参数：

```json
{
  "options": {
    "include_breakdown": false
  }
}
```

只有显式开启时，才返回：

```json
{
  "score_breakdown": {
    "text_match_score": 0.8,
    "recency_boost": 0.07,
    "access_boost": 0.04,
    "vector_score": 0
  }
}
```

这样兼容性最好。

---

## 四、Context Assembly 调整

这里正式拆出去，不再塞进 Phase 2a。

---

### Phase 2a 只保留最小对齐字段

每条结果增加：

```json
{
  "token_estimate": 42
}
```

这就够了。

作用是：

1. 给后续 Phase 2b 的 context assembly 预热
    
2. 让 search 已经能初步和 token savings 对齐
    

---

### Phase 2b 再做完整 Context Assembly

Phase 2b 再上：

- excerpt 提取
    
- top-k merge
    
- combined_text
    
- token budget
    
- compression ratio
    
- assembled context block
    

这样拆最稳。

---

## 五、Token Savings 对齐（Phase 2a 版）

这里也要缩范围，不做完整 assembly savings，而做**可计量基础版**。

### Phase 2a 计量方式

search 事件先记录：

- `query_count`
    
- `recall_hits`
    
- `returned_hits`
    
- `estimated_result_tokens`
    

建议事件模型扩成：

```json
{
  "event_type": "memory_search",
  "request_id": "req_xxxxx",
  "scope": "workspace",
  "query_count": 1,
  "recall_hits": 12,
  "returned_hits": 5,
  "input_tokens": 5,
  "compressed_tokens": 210,
  "saved_tokens": 0
}
```

这里注意：

### 当前不要硬算 `saved_tokens`

因为没有 context assembly，所谓“节省”还不成立。  
所以更稳的做法是：

```text
Phase 2a:
saved_tokens = 0
或字段缺省
```

等到 Phase 2b 有 excerpt / budget / combined context 后，再真正算：

```text
raw_tokens - compressed_tokens
```

这才不自欺。

---

# 修正版阶段拆分

## Phase 2a（现在做）

- FTS5 MATCH recall
    
- BM25 可用性探测
    
- bm25 可用则用 bm25
    
- 不可用则 fallback_text_score
    
- recency boost
    
- access boost
    
- top-k 排序返回
    
- response 扩展兼容
    
- vector_score 字段预留
    
- token_estimate 字段预留
    

---

## Phase 2b（下一步做）

- excerpt 提取
    
- context assembly
    
- combined_text
    
- token budget 控制
    
- 真正的 search token savings 计算
    

---

## Phase 2c（未来）

- sqlite-vss / vector similarity
    
- hybrid retrieval
    
- score_breakdown 完整解释
    
- assembly strategy 多模式
    

---

# 你现在应该改写成的一句话版本

```text
/memory/search V2 不再一次性做完整 retrieval engine。
Phase 2a 先完成：FTS5 recall + BM25/fallback ranking + recency/access boost + top-k。
Context assembly、真实 token savings、向量相似度放入后续阶段。
```

---

# 最后判断

CC这次不是在“保守”，而是在帮你**收缩战线，避免过度设计**。

这对你现在是好事。  
因为你当前最重要的不是把图画满，而是：

> **先把 ranking search 稳稳落地，且不破坏现有闭环。**

下一步你可以先形成大纲，再一一分步执行，直到完成：

**`/memory/search V2 Phase 2a` 的最终工程大纲**  
包含：

- request/response 结构
    
- Go struct
    
- scoring 伪代码
    
- BM25 探测与 fallback 流程
    
- 测试用例清单