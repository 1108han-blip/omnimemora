下面是交给 CC 的 **`/memory/search V2 Phase 2a 最终工程大纲`**。这版已经按你们刚才的修正意见收缩过：**先做 ranking search，不做完整 context assembly**。

---

# OmniMemora `/memory/search` V2 Phase 2a 最终工程大纲

## 1. 目标

把当前 `/memory/search` 从“关键词命中”升级为“**scope-aware recall + 轻量 ranking + top-k 返回**”，同时满足：

- 不破坏现有 Phase 1.2 闭环
    
- 不改 endpoint path
    
- Response **扩展兼容**，不替换
    
- 不提前做完整 retrieval engine
    
- 为后续 Phase 2b / 2c 预留接口
    

这与 Runtime 已定义的职责一致：`/memory/search` 属于 Local Runtime 核心 API，必须保持 scope-aware、可计量、可演进。

---

## 2. 本阶段范围

## 2.1 要做

### A. Candidate Recall

- 继续使用现有 SQL scope enforcement
    
- 优先走 FTS5 `MATCH`
    
- recall 候选集后进入应用层排序
    

### B. Ranking

- `text_match_score`
    
- `recency_boost`
    
- `access_boost`
    
- `vector_score` 预留字段，当前固定为 `0`
    

### C. Top-k 返回

- 应用层排序后截断到 `limit`
    
- 返回稳定排序结果
    

### D. Response 扩展兼容

- 保留现有字段
    
- 新字段按需增加
    
- `include_breakdown` 控制详细评分输出
    

### E. 最小计量对齐

- 记录 `memory_search` 事件
    
- 记录搜索命中和返回数量
    
- 暂不承诺真实 `saved_tokens`
    

---

## 2.2 不做

### 暂不进入 Phase 2a 的内容

- excerpt 提取
    
- combined context
    
- token budget 控制
    
- compression ratio
    
- 多策略 context assembly
    
- hybrid retrieval
    
- sqlite-vss 实装
    
- 完整 explainability 默认返回
    

这些内容拆到后续阶段更稳，避免一次性把 search 做成半个 retrieval engine。

---

# 3. 阶段拆分

## Phase 2a（当前实现）

```text
FTS5 recall
+ BM25 探测 / fallback
+ recency boost
+ access boost
+ top-k
+ response 扩展兼容
```

## Phase 2b（后续）

```text
excerpt 提取
+ context assembly
+ combined_text
+ token budget
+ 真正 search token savings
```

## Phase 2c（未来）

```text
sqlite-vss / vector similarity
+ hybrid retrieval
+ 完整 score_breakdown
+ 更强 explainability
```

---

# 4. API 兼容策略

## 4.1 Endpoint 不变

继续使用：

```http
POST /memory/search
```

不改 path，不改基本调用方式。

---

## 4.2 Request 结构

在现有基础上扩展，推荐如下：

```json
{
  "keyword": "sqlite scope filter",
  "scope": "workspace",
  "agent_id": "claude_code",
  "workspace_id": "proj_alpha",
  "limit": 10,
  "request_id": "req_xxxxx",
  "options": {
    "include_breakdown": false
  }
}
```

## 4.3 新增 request 字段

### `options.include_breakdown`

- 类型：`bool`
    
- 默认：`false`
    
- 含义：是否返回 `score_breakdown`
    

---

# 5. Response 结构

## 5.1 兼容基线

必须保留现有核心字段：

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

## 5.2 `results[i]` 扩展字段

建议新增以下字段：

```json
{
  "memory_id": "mem_001",
  "content": "...",
  "score": 0.91,
  "vector_score": 0,
  "token_estimate": 42
}
```

### 字段说明

#### `score`

最终排序分数，用于前端/调用方理解排序结果。

#### `vector_score`

- 当前固定返回 `0`
    
- 为后续向量检索预留
    

#### `token_estimate`

- 当前仅做估算
    
- 用于后续 Phase 2b context assembly 预热
    
- 估算方式先用：
    

```text
len(content) / 4
```

与 Runtime 当前 token 粗估思路一致。

---

## 5.3 breakdown 可选返回

仅当 `options.include_breakdown = true` 时返回：

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

否则不返回，避免接口膨胀。

---

# 6. Ranking 设计

## 6.1 总体公式

```text
final_score =
  text_match_score
+ recency_boost
+ access_boost
+ vector_score
```

其中：

```text
vector_score = 0
```

当前只占位，不参与真实排序差异。

---

## 6.2 `text_match_score`

来源优先级：

```text
bm25() if available
否则 fallback_text_score
```

---

## 6.3 BM25 探测策略

### 原则

不能假设 `bm25()` 一定可用。必须在运行时或初始化阶段探测。

### 建议探测方式

Runtime 启动或 store 初始化后执行一次能力探测：

```sql
SELECT bm25(memories_fts) FROM memories_fts LIMIT 1;
```

或在代码中做等价试探查询。

### 探测结果记录

建议增加 store/runtime 内部能力标记：

```go
type SearchCapabilities struct {
    FTS5Enabled    bool
    BM25Available  bool
}
```

---

## 6.4 BM25 可用时的评分

注意：FTS5 的 BM25 通常是**越小越相关**，因此必须转成“越大越好”。

建议应用层做归一化：

```text
text_match_score = 1 / (1 + raw_bm25)
```

或：

```text
text_match_score = clamp(1 - normalized_bm25, 0, 1)
```

不要把原始 bm25 直接当分数。

---

## 6.5 BM25 不可用时的 fallback

建议使用简单、稳定、可解释的文本评分：

```text
exact phrase hit      = 1.00
all terms matched     = 0.80
partial terms matched = 0.50
LIKE only             = 0.30
```

### 规则建议

- 完整短语命中：最高
    
- 分词全命中：次高
    
- 部分词命中：中
    
- 仅模糊 LIKE 命中：低
    

这样就算没有 bm25，也能先把 Phase 2a 稳稳落地。

---

## 6.6 `recency_boost`

先做分层，不做复杂衰减函数。

建议：

```text
≤ 1 day     +0.10
≤ 7 days    +0.07
≤ 30 days   +0.04
≤ 90 days   +0.01
> 90 days   +0
```

依据字段：

- `updated_at` 优先
    
- 没有则用 `created_at`
    

---

## 6.7 `access_boost`

建议使用轻量分层版：

```text
access_count = 0      -> +0.00
1 ~ 3                -> +0.02
4 ~ 10               -> +0.05
> 10                 -> +0.08
```

如果 `access_count` 已经稳定维护，可后续切换到对数函数。

---

## 6.8 `vector_score`

当前：

```text
vector_score = 0
```

用途仅为响应结构和评分模型预留，不要在 Phase 2a 实装向量路径。

---

# 7. SQL + Scoring 方案

## 7.1 两阶段设计

必须坚持：

```text
SQL recall
→ app layer scoring
→ sort
→ top-k
```

不要试图用单条 SQL 做完整排序模型。

---

## 7.2 Scope Enforcement

继续沿用现有规则：

- `tenant_id` 必过滤
    
- `scope` 必精确匹配
    
- `agent/workspace/user` 按各自 identity 过滤
    

这和当前 Runtime 的 SQL scope enforcement 决策必须保持一致。

---

## 7.3 Recall 路径

### 主路径

FTS5 `MATCH`

### 退化路径

`LIKE`

---

## 7.4 Candidate 数量

不要直接拿 `limit` 作为候选数。

建议：

```text
candidate_limit = max(limit * 3, 20)
```

这样应用层 ranking 才有空间。

---

## 7.5 SQL 示例

### Workspace scope + FTS5 recall

```sql
SELECT memory_id, content, metadata, created_at, updated_at, last_accessed_at, access_count
FROM memories_fts
WHERE tenant_id = ?
  AND scope = 'workspace'
  AND workspace_id = ?
  AND memories_fts MATCH ?
LIMIT ?;
```

### Agent scope + FTS5 recall

```sql
SELECT memory_id, content, metadata, created_at, updated_at, last_accessed_at, access_count
FROM memories_fts
WHERE tenant_id = ?
  AND scope = 'agent'
  AND agent_id = ?
  AND memories_fts MATCH ?
LIMIT ?;
```

### User scope + FTS5 recall

```sql
SELECT memory_id, content, metadata, created_at, updated_at, last_accessed_at, access_count
FROM memories_fts
WHERE tenant_id = ?
  AND scope = 'user'
  AND user_id = ?
  AND memories_fts MATCH ?
LIMIT ?;
```

---

## 7.6 LIKE fallback 示例

```sql
SELECT memory_id, content, metadata, created_at, updated_at, last_accessed_at, access_count
FROM memories
WHERE tenant_id = ?
  AND scope = 'workspace'
  AND workspace_id = ?
  AND content LIKE ?
LIMIT ?;
```

---

# 8. Go 数据结构建议

## 8.1 Request

```go
type SearchOptions struct {
    IncludeBreakdown bool `json:"include_breakdown,omitempty"`
}

type SearchRequest struct {
    Keyword     string        `json:"keyword"`
    Scope       string        `json:"scope,omitempty"`
    AgentID     string        `json:"agent_id,omitempty"`
    WorkspaceID string        `json:"workspace_id,omitempty"`
    Limit       int           `json:"limit,omitempty"`
    RequestID   string        `json:"request_id,omitempty"`
    Options     SearchOptions `json:"options,omitempty"`
}
```

---

## 8.2 Candidate

```go
type SearchCandidate struct {
    MemoryID       string
    Content        string
    Metadata       map[string]any
    CreatedAt      time.Time
    UpdatedAt      time.Time
    LastAccessedAt *time.Time
    AccessCount    int
    RawTextScore   float64
}
```

---

## 8.3 Breakdown

```go
type ScoreBreakdown struct {
    TextMatchScore float64 `json:"text_match_score"`
    RecencyBoost   float64 `json:"recency_boost"`
    AccessBoost    float64 `json:"access_boost"`
    VectorScore    float64 `json:"vector_score"`
}
```

---

## 8.4 Result

```go
type SearchResultItem struct {
    MemoryID       string          `json:"memory_id"`
    Content        string          `json:"content"`
    Score          float64         `json:"score"`
    VectorScore    float64         `json:"vector_score"`
    TokenEstimate  int             `json:"token_estimate"`
    ScoreBreakdown *ScoreBreakdown `json:"score_breakdown,omitempty"`
    CreatedAt      time.Time       `json:"created_at,omitempty"`
    UpdatedAt      time.Time       `json:"updated_at,omitempty"`
}
```

---

## 8.5 Response

```go
type SearchResponse struct {
    RequestID    string             `json:"request_id"`
    Results      []SearchResultItem `json:"results"`
    Total        int                `json:"total"`
    ScopeApplied string             `json:"scope_applied"`
    TookMs       int64              `json:"took_ms"`
}
```

---

## 8.6 Capabilities

```go
type SearchCapabilities struct {
    FTS5Enabled   bool
    BM25Available bool
}
```

---

# 9. 处理流程伪代码

```text
handleSearch(request):
  1. validate request
  2. resolve scope context
  3. build scope-aware SQL filter
  4. determine candidate_limit = max(limit * 3, 20)

  5. if FTS5 enabled:
       run MATCH recall
     else:
       run LIKE fallback recall

  6. if BM25 available:
       compute text_match_score from normalized inverse bm25
     else:
       compute fallback_text_score in app layer

  7. for each candidate:
       recency_boost = calcRecencyBoost(...)
       access_boost  = calcAccessBoost(...)
       vector_score  = 0
       final_score   = text_match_score + recency_boost + access_boost + vector_score

  8. sort by:
       final_score desc
       updated_at desc
       memory_id asc

  9. truncate to limit

  10. map to response:
        score
        vector_score=0
        token_estimate=len(content)/4
        score_breakdown only if requested

  11. emit memory_search metering event

  12. return response
```

---

# 10. Metering 对齐

## 10.1 Phase 2a 原则

只做**基础搜索计量**，不假装已经有真实 token savings。

因为当前还没有：

- excerpt
    
- context assembly
    
- token budget
    

所以现在不能严肃声称已经算出了 search savings。

---

## 10.2 建议事件结构

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
  "input_tokens": 5,
  "compressed_tokens": 210,
  "saved_tokens": 0,
  "timestamp": "2026-04-09T00:00:00Z"
}
```

---

## 10.3 字段解释

### `input_tokens`

可先粗估为 query token 数。

### `compressed_tokens`

当前可临时表示“返回结果内容总估算 token”，但只是过渡口径。

### `saved_tokens`

Phase 2a 建议固定为：

```text
0
```

或缺省，不要伪造节省值。

真正的 search token savings 放到 Phase 2b 再做。

---

# 11. 测试用例清单

## 11.1 能力探测

### Case 1

FTS5 可用，BM25 可用  
预期：走 MATCH + BM25

### Case 2

FTS5 可用，BM25 不可用  
预期：走 MATCH + fallback_text_score

### Case 3

FTS5 不可用  
预期：走 LIKE fallback

---

## 11.2 Scope 隔离

### Case 4

workspace A 写入，workspace B search  
预期：查不到

### Case 5

agent A 写入，agent B search（agent scope）  
预期：查不到

### Case 6

user A 写入，user B search（user scope）  
预期：查不到

这必须继续保持与现有 SQL enforcement 一致。

---

## 11.3 排序正确性

### Case 7

同关键词下，新记录与旧记录同时命中  
预期：新记录因 recency boost 更靠前

### Case 8

同关键词下，高 access_count 记录与低 access_count 记录同时命中  
预期：高 access_count 更靠前

### Case 9

同分数时  
预期：按 `updated_at DESC`，再按 `memory_id ASC`

---

## 11.4 响应兼容

### Case 10

不传 `include_breakdown`  
预期：不返回 `score_breakdown`

### Case 11

传 `include_breakdown=true`  
预期：返回 breakdown

### Case 12

老客户端只读取 `results/total`  
预期：不受影响

---

## 11.5 计量

### Case 13

一次正常 search  
预期：产生 `memory_search` 事件

### Case 14

无结果 search  
预期：事件仍产生，`recall_hits=0`，`returned_hits=0`

---

# 12. 验收标准

## 功能验收

- `/memory/search` 保持可用
    
- FTS5 recall 正常
    
- BM25 可用则启用，不可用则自动 fallback
    
- 排序结果明显优于 Phase 1.2 的简单命中返回
    
- top-k 返回稳定
    

## 兼容验收

- 不改 endpoint path
    
- Response 是扩展兼容，不是替换
    
- 老调用方不需要修改也能继续使用
    

## 架构验收

- 不绕过 SQL scope enforcement
    
- 不引入云端依赖
    
- 不把 Phase 2a 做成完整 context assembly
    
- 为后续 vector/context 路径预留但不抢跑
    

---

# 13. 交付给 CC 的一句话施工指令

```text
实现 /memory/search V2 Phase 2a：
保持 endpoint 与响应兼容；先做 scope-aware candidate recall、BM25 能力探测与 fallback_text_score、recency/access ranking、top-k 返回；新增 score/vector_score/token_estimate 字段；score_breakdown 仅在 include_breakdown=true 时返回；emit memory_search metering event，但 saved_tokens 暂不做真实计算。
```

