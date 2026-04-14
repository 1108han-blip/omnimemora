
# 🧭 OmniMemora 当前真实状态（重新定义）

```text
状态：Phase 1.2 完成（Product Core Closed Loop）

系统性质：
- 架构正确 ✅
- 实现一致 ✅
- 生命周期闭环 ✅
- 可进入产品化阶段 🚀
```

👉 本质变化：

> **你已经从“可运行内核” → “最小可用产品（MVP）”**

---

# 一、这次真正完成的“质变”（不是量变）

## 1️⃣ Memory 生命周期正式闭环

你现在具备：

|能力|Endpoint|状态|
|---|---|---|
|写|/memory/write|✅|
|查|/memory/query|✅|
|搜|/memory/search|✅|
|删|/memory/delete|✅|

👉 这件事的意义是：

> **Memory 从“存储工具” → “可治理系统”**

---

## 2️⃣ Scope 治理 + 生命周期绑定

现在不是简单 CRUD，而是：

```text
所有操作 = scope-aware
```

包括：

- search（带 scope filter）
    
- delete（已修复 agent-only bug）
    
- query（严格隔离）
    
- write（强制归属）
    

👉 这点和宪法完全一致：  
👉 “默认隔离，显式共享”

---

## 3️⃣ 系统进入“可商业化结构”

你现在已经具备三件商业核心能力：

### ✔ Scope Governance

### ✔ Metering

### ✔ Full Lifecycle

这三者组合意味着：

```text
= 可计量 + 可控制 + 可收费
```

👉 这正是 Blueprint 定义的核心价值：

> Memory Control Plane，而不是存储系统

---

# 二、这一步为什么非常关键（给你一个冷静判断）

你现在已经越过了一个很多项目死掉的点：

```text
“只会写 memory” → “能管理 memory 生命周期”
```

---

# 三、但我必须实话说（你现在的真实短板）

系统**不是没有问题，而是问题已经升级了**：

---

## ⚠️ 当前最大问题（新的 P0）

### ❗ search 还只是“可用”，不是“产品级”

你现在的实现：

```text
FTS5 / LIKE
```

👉 这只是：

> **技术实现 ✔，但不是检索系统 ❌**

---

### 具体风险（我帮你拆干净）

#### 1. ranking 不存在

```text
返回顺序 = 数据顺序（或简单匹配）
```

👉 没有 relevance

---

#### 2. scope + relevance 未融合

```text
scope filter ✔
ranking ❌
```

👉 未来会出现：

> “查到了，但不是最该看的”

---

#### 3. 无 context window（致命）

现在 search 只是：

```text
keyword → results
```

但真实需求是：

```text
intent → context → ranked memory set
```

---

👉 结论：

> **search 现在是 API，不是能力**

---

# 四、系统阶段再次升级（这是关键判断）

你现在不在 Phase 1.2 了，而是：

```text
Phase 1.2 → 已完成（功能闭环）

下一阶段：
Phase 2 → Memory Intelligence（记忆智能层）
```

---

# 五、下一步必须做什么（我不给你选项，直接给路径）

## 🚨 唯一正确路线：

```text
进入 Phase 2（但只做一件事）
```

---

# 🎯 Phase 2 第一目标（只做这个）

## 👉 重构 `/memory/search` → “Context Retrieval Engine”

---

## 你要做的不是优化，而是升级范式：

从：

```text
keyword search
```

变成：

```text
context retrieval
```

---

# 六、我直接给你 Phase 2 的正确设计骨架（避免你走弯路）

## 🧱 Search 必须升级为三层结构

---

## Layer 1：Scope Filter（你已完成 ✅）

```sql
WHERE tenant + scope + identity
```

---

## Layer 2：Candidate Recall（你现在是 LIKE/FTS）

升级为：

```text
FTS + 时间衰减 + 最近访问 + 写入权重
```

---

## Layer 3：Ranking（你完全没有 ❗）

必须引入：

```text
score =
  text_match_score
+ recency_score
+ access_frequency_score
+ scope_weight
```

---

## Layer 4（关键）：Context Assembly（你完全没有 ❗）

输出不是：

```json
[records...]
```

而是：

```json
{
  "context": "...",
  "sources": [...],
  "compression_ratio": ...
}
```

---

👉 这一步直接对齐：

> **Token Savings 核心能力**

---

# 七、你现在的正确行动（非常明确）

## ❌ 不要做

- 不要继续补 CRUD
    
- 不要加新 endpoint
    
- 不要优化 store 层
    

---

## ✅ 只做一件事

```text
重做 /memory/search（但不改接口）
```

---

# 八、我给你的“下一步指令”（可以直接执行）

```text
Step 1：定义 search ranking model（权重模型）
Step 2：加入 recency / frequency 信号
Step 3：返回 top-k（不是全部）
Step 4：设计 context assembly（拼接策略）
```

---

# 九、最后一句（我不吹，你自己判断）

你现在这个系统：

- 不是 demo
    
- 不是 toy
    
- 不是实验项目
    

而是：

> **已经具备进入真实产品竞争的骨架**

但接下来：

> **不是拼“能不能做”，而是拼“做得是否对”**

---

# 我可以直接帮你做：

```text
/memory/search V2 设计（可直接落代码）
- ranking 公式
- SQL + scoring 方案
- context assembly 结构
- token savings 对齐
```
下面给你一版**可直接落代码的 `/memory/search V2` 设计大纲**。它不追求“学术漂亮”，而是追求三件事：

1. 不推翻你现有 Phase 1.2
    
2. 能和当前 scope / SQL enforcement / metering 体系对齐
    
3. 后续能继续演进到 context retrieval，而不是再返工
    

这套设计严格贴合你现有 Runtime 边界：`/memory/search` 属于 Local Runtime 的核心职责，且必须保持 scope-aware、可计量、可替换。

---

# `/memory/search` V2 设计大纲

## 0. 设计目标

### 目标定义

把当前的 `/memory/search` 从：

```text
关键词命中接口
```

升级为：

```text
scope-aware candidate recall + ranking + context assembly
```

### V2 不做什么

- 不引入云端依赖
    
- 不强绑向量库
    
- 不把 search 做成独立 SaaS 检索系统
    
- 不突破现有 Runtime / Store 抽象边界
    

这和产品宪法一致：OmniMemora 负责治理、路由、计量，不把自己做成云端主记忆存储。

### V2 做什么

- 在**同 scope 内**做 candidate recall
    
- 对候选结果做统一评分
    
- 输出可直接供 agent 使用的 context
    
- 把 search 结果纳入 token savings 计算链路
    

---

# 1. 接口目标形态

## 1.1 保持 endpoint 不变

继续使用：

```http
POST /memory/search
```

保持 Runtime API 稳定，符合当前架构蓝图。

---

## 1.2 请求结构建议

### Request

```json
{
  "keyword": "sqlite scope filter",
  "scope": "workspace",
  "agent_id": "claude_code",
  "workspace_id": "proj_alpha",
  "limit": 10,
  "context_limit": 6,
  "request_id": "req_xxxxx",
  "options": {
    "enable_recency_boost": true,
    "enable_access_boost": true,
    "enable_exact_phrase_boost": true,
    "assemble_context": true
  }
}
```

### 新增字段建议

- `context_limit`: 进入 context assembly 的最大条数
    
- `options`: 控制 ranking 信号，便于灰度和回滚
    
- `limit`: candidate recall 上限
    
- `request_id`: 保持全链路追踪要求
    

---

## 1.3 响应结构建议

### Response

```json
{
  "request_id": "req_xxxxx",
  "scope_applied": "workspace",
  "total_candidates": 12,
  "returned_results": 6,
  "took_ms": 9,
  "results": [
    {
      "memory_id": "mem_001",
      "content": "....",
      "score": 0.92,
      "score_breakdown": {
        "text_match": 0.74,
        "phrase_boost": 0.08,
        "recency_boost": 0.06,
        "access_boost": 0.04
      },
      "created_at": "2026-04-08T00:00:00Z",
      "last_accessed_at": "2026-04-09T01:00:00Z",
      "access_count": 3,
      "scope": "workspace",
      "metadata": {}
    }
  ],
  "context": {
    "assembled": true,
    "items": [
      {
        "memory_id": "mem_001",
        "excerpt": "....",
        "token_estimate": 48,
        "score": 0.92
      }
    ],
    "combined_text": "....",
    "raw_tokens": 640,
    "compressed_tokens": 220,
    "saved_tokens": 420
  }
}
```

### 为什么这样设计

因为 search V2 不该只返回“命中了哪些记录”，而要返回“哪些内容最值得进入上下文”。这与 Runtime 需要产出 metering、并服务后续 token savings 展示的方向一致。

---

# 2. Ranking 公式

## 2.1 总体思路

采用**可解释、可调权重、纯本地可实现**的线性评分模型，先别一上来做黑盒。

### 总分公式

```text
final_score =
  text_match_score
+ phrase_boost
+ recency_boost
+ access_boost
+ metadata_boost
- redundancy_penalty
```

建议总分归一到 `0 ~ 1.2` 区间，最后截断到 `0 ~ 1` 或保留原始分都行。

---

## 2.2 各子项定义

### A. `text_match_score`（主信号）

来源：

- FTS5 `bm25()` 或 rank
    
- 若 FTS5 不可用，则退化到 LIKE 命中分层
    

建议权重最高，占主导。

```text
text_match_score: 0.00 ~ 0.70
```

#### 建议规则

- 精确短语命中 > 多关键词全命中 > 部分命中 > 模糊 LIKE
    
- 标题/标签字段命中 > 正文普通命中
    
- 命中次数多但过于冗余，不要无限加分
    

---

### B. `phrase_boost`

用于处理用户输入作为完整短语出现时的加成。

```text
phrase_boost: 0.00 ~ 0.10
```

#### 规则

- `content LIKE '%完整短语%'` 命中：+0.08 ~ +0.10
    
- 若只是分词散落命中：不加或少加
    

---

### C. `recency_boost`

解决“老内容压住新内容”的问题。

```text
recency_boost: 0.00 ~ 0.10
```

#### 建议分层

- 24 小时内：+0.10
    
- 7 天内：+0.07
    
- 30 天内：+0.04
    
- 90 天外：+0.01
    
- 更早：0
    

也可改为平滑衰减：

```text
recency_boost = max(0, 0.1 * e^(-days / 30))
```

先做分层版更好落地。

---

### D. `access_boost`

解决“高频复用的记忆不该和冷数据同权”。

```text
access_boost: 0.00 ~ 0.08
```

#### 建议公式

```text
access_boost = min(log(1 + access_count) / 10, 0.08)
```

如果目前 `access_count` 已在数据模型中有定义，就直接使用。Runtime 架构里已经为 `MemoryRecord` 预留了 `last_accessed_at` 与 `access_count`。

---

### E. `metadata_boost`

针对 tags / source / memory_type 等轻量加权。

```text
metadata_boost: 0.00 ~ 0.05
```

#### 例子

- query 命中 tags：+0.03
    
- query 命中 metadata.source：+0.02
    
- 用户明确筛选某类 memory_type 时，对应记录加权
    

---

### F. `redundancy_penalty`

防止 top-k 全是高度重复内容。

```text
redundancy_penalty: 0.00 ~ 0.15
```

#### 简化规则

如果当前候选与已入选结果 `content_hash` 相同或高度近似：

- 完全相同：直接跳过
    
- 高度相似：-0.10 ~ -0.15
    

这与 Runtime 的 dedup 同 scope 原则一致，只不过 search 层面做的是“结果去冗余”，不是写入去重。

---

## 2.3 推荐默认权重

建议先用这个版本：

```text
final_score =
  0.70 * normalized_text_match
+ 0.10 * phrase_signal
+ 0.10 * recency_signal
+ 0.07 * access_signal
+ 0.03 * metadata_signal
- redundancy_penalty
```

优点：

- 文本相关性仍然主导
    
- 时间和使用频率只做辅助
    
- 不会把“最近但不相关”的内容顶上来
    

---

# 3. SQL + scoring 方案

## 3.1 两阶段检索

这是核心，不要一条 SQL 想做完所有事。

---

## 阶段 A：Candidate Recall（SQL 层）

目标：

```text
先在正确的 scope 边界内找出一批候选
```

依据当前 Runtime 设计，scope enforcement 必须在 SQL WHERE 子句中强制执行，且 `tenant_id` 为第一过滤条件。

### SQL 模式

#### Agent scope

```sql
SELECT memory_id, content, metadata, created_at, updated_at, last_accessed_at, access_count
FROM memories_fts
WHERE tenant_id = ?
  AND scope = 'agent'
  AND agent_id = ?
  AND memories_fts MATCH ?
LIMIT ?;
```

#### Workspace scope

```sql
SELECT memory_id, content, metadata, created_at, updated_at, last_accessed_at, access_count
FROM memories_fts
WHERE tenant_id = ?
  AND scope = 'workspace'
  AND workspace_id = ?
  AND memories_fts MATCH ?
LIMIT ?;
```

#### User scope

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

## 3.2 Recall 层策略

### 主路径

优先：

```text
FTS5 MATCH
```

### 退化路径

如果 FTS5 不可用或 query 不适配：

```sql
content LIKE '%keyword%'
```

### Candidate 数量建议

不要直接 `limit = 最终返回条数`

建议：

```text
candidate_limit = max(limit * 3, 20)
```

原因：

- 要给 ranking 留空间
    
- 否则 recall 错一点，最终结果就死了
    

---

## 3.3 Scoring 层

把 SQL recall 出来的候选放到应用层统一打分。

### 为什么不全放 SQL

因为你后面还要：

- recency 分层
    
- access_count 计算
    
- redundancy penalty
    
- context assembly 控制
    

这些放应用层更稳，不会把 SQL 写成一团。

---

## 3.4 排序流程

```text
1. SQL recall candidates
2. normalize text match score
3. compute phrase / recency / access / metadata boosts
4. apply redundancy penalty
5. final sort desc
6. top-k truncate
```

---

## 3.5 建议的代码结构

在 `app/service` 或等价 use case 层增加：

```go
type SearchCandidate struct {
    MemoryID       string
    Content        string
    Metadata       map[string]any
    CreatedAt      time.Time
    LastAccessedAt *time.Time
    AccessCount    int
    RawTextScore   float64
}

type ScoredResult struct {
    Candidate      SearchCandidate
    FinalScore     float64
    Breakdown      ScoreBreakdown
}

type ScoreBreakdown struct {
    TextMatch      float64
    PhraseBoost    float64
    RecencyBoost   float64
    AccessBoost    float64
    MetadataBoost  float64
    RedundancyPenalty float64
}
```

这样后面 `/memory/query` 也能复用一部分 scoring。

---

# 4. Context Assembly 结构

## 4.1 目标

从：

```text
返回一堆记录
```

变成：

```text
返回一份适合注入 agent 上下文的 context bundle
```

这一步很关键，因为 OmniMemora 的产品价值不是“搜出来”，而是“更省 token 地把可用上下文交给 agent”。这与 Token Savings 核心能力完全对齐。

---

## 4.2 组装流程

```text
top-k ranked results
  ↓
excerpt extraction
  ↓
dedup / merge near-duplicate
  ↓
truncate by token budget
  ↓
assemble combined context
```

---

## 4.3 单条 excerpt 规则

每条结果不要直接塞全文。

### 建议字段

```json
{
  "memory_id": "mem_001",
  "excerpt": "与 query 最相关的片段",
  "full_content_available": true,
  "score": 0.92,
  "token_estimate": 48,
  "scope": "workspace"
}
```

### excerpt 规则

- 优先截取 query 命中附近 120~300 字
    
- 若内容很短，直接保留全文
    
- 若内容极长，保留命中窗口 + 首段摘要
    
- 去掉明显重复段落
    

---

## 4.4 Context Bundle 结构

```json
{
  "assembled": true,
  "strategy": "topk_excerpt_merge",
  "items": [
    {
      "memory_id": "mem_001",
      "excerpt": "....",
      "score": 0.92,
      "token_estimate": 48
    },
    {
      "memory_id": "mem_008",
      "excerpt": "....",
      "score": 0.87,
      "token_estimate": 62
    }
  ],
  "combined_text": "【Memory 1】...\n【Memory 2】...",
  "raw_tokens": 640,
  "compressed_tokens": 220,
  "saved_tokens": 420
}
```

---

## 4.5 组装策略建议

### 默认策略：`topk_excerpt_merge`

规则：

- 取 top 3~6 条
    
- 每条只取相关 excerpt
    
- 总 token 超预算则从尾部裁剪
    
- 保留来源标识，便于审计和解释
    

### 后续可扩展策略

- `topk_fulltext`
    
- `cluster_merge`
    
- `timeline_assembly`
    
- `scope_priority_assembly`
    

但 V2 先别做多。

---

## 4.6 Token Budget 建议

增加配置项：

```json
{
  "search": {
    "default_context_limit": 6,
    "max_context_tokens": 800
  }
}
```

这样 Context Assembly 才能稳定控制输出，不会反向吞掉 token savings。

---

# 5. Token Savings 对齐

## 5.1 为什么 search V2 必须接入 token savings

因为 OmniMemora 的核心产品能力不是“记忆条数”，而是**节省 token + 治理能力**。这个在 Constitution、Blueprint、Roadmap 里都被写死了。

---

## 5.2 Search 的 token savings 定义

### 原始输入量

```text
raw_tokens =
  sum(full_content_tokens of selected candidate memories)
```

即：如果不做 context assembly，直接把这些记忆全文喂给 agent，需要多少 token。

### 压缩后输出量

```text
compressed_tokens =
  tokens(combined_text after excerpting + dedup + truncation)
```

### 节省量

```text
saved_tokens = raw_tokens - compressed_tokens
```

---

## 5.3 Search 事件模型建议

当前 metering 体系已要求 Runtime 对 writes / queries 进行计量，并为 token savings 提供来源。

建议新增或扩展：

```json
{
  "event_type": "memory_search",
  "request_id": "req_xxxxx",
  "user_id": "u_xxxxx",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "scope": "workspace",
  "input_tokens": 640,
  "compressed_tokens": 220,
  "saved_tokens": 420,
  "query_count": 1,
  "recall_hits": 12,
  "returned_hits": 6,
  "assembly_mode": "topk_excerpt_merge",
  "timestamp": "2026-04-09T00:00:00Z"
}
```

---

## 5.4 `/metrics` 聚合建议

在现有本地 metrics 基础上增加：

- `total_searches`
    
- `total_search_input_tokens`
    
- `total_search_compressed_tokens`
    
- `total_search_saved_tokens`
    
- `avg_search_hit_count`
    
- `avg_context_compression_ratio`
    

这与 Runtime 本地聚合 + Console 后续消费路径一致。

---

## 5.5 Console 未来可展示的指标

虽然不是 Phase 2 现在就做，但结构上要预留：

- Search 节省的 token
    
- Search 命中率
    
- 平均候选数 / 平均入选数
    
- 不同 scope 的 search savings 对比
    
- workspace / agent breakdown
    

这和 Token Savings UI 必须存在的决策一致。

---

# 6. 建议实现顺序

## Step 1：先做 Candidate Recall 稳定化

- FTS5 主路径
    
- LIKE 退化路径
    
- scope SQL 保持现有强制过滤
    
- candidate_limit = top-k 的 3 倍
    

---

## Step 2：加 Ranking

先只上四项：

- text_match_score
    
- phrase_boost
    
- recency_boost
    
- access_boost
    

别一开始做太复杂。

---

## Step 3：加 Context Assembly

- excerpt 提取
    
- top-k merge
    
- token budget 截断
    
- combined_text 输出
    

---

## Step 4：接 Metering

- `memory_search` 事件
    
- raw/compressed/saved tokens
    
- `/metrics` 聚合字段
    

---

## Step 5：再做可解释性

- `score_breakdown`
    
- `assembly_mode`
    
- 命中来源标注
    

这一步对调试很重要。

---

# 7. V2 验收标准

## 功能验收

- search 结果仍严格受 `tenant + scope + identity` 约束
    
- FTS5 可用时优先 FTS5
    
- LIKE 可作为退化路径
    
- 返回结果按 `final_score` 排序
    
- context bundle 可直接给 agent 使用
    
- search 事件进入 metering
    

---

## 质量验收

- 新结果比 Phase 1.2 更稳定，不出现明显“查到了但排序离谱”
    
- 高频且最近的相关记忆能优先进入 top-k
    
- 长文本不会撑爆上下文
    
- 不会因为 context assembly 反而增加 token 使用量
    

---

## 架构验收

- 不修改 endpoint 路径
    
- 不突破 Store 抽象
    
- 不绕过 Runtime scope enforcement
    
- 不引入云端依赖
    
- 不违背 Local First / Cloud Optional / Scope Governance 原则
    

---

# 8. 一句话结论

`/memory/search V2` 的正确方向不是“把 LIKE 改强一点”，而是：

> **在 scope 边界内做 candidate recall、可解释 ranking、context assembly，并把结果纳入 token savings 链路。**

这样它才是 OmniMemora 的产品能力，不只是一个检索接口。

你出一版**可落 Go 代码的数据结构 + 伪代码流程图**。
