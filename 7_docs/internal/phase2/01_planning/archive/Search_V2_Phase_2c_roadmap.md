

# 一、Phase 2c 架构设计大纲

## 0. Phase 2c 的一句话目标

```text
把 /memory/search 从“FTS 排序 + 轻量 context assembly”
升级为“可扩展的 Retrieval Engine 骨架”，
但不破坏 Phase 2a/2b 已成立的诚实计量、scope 治理和本地优先边界。
```

Phase 2b 已经把 `/memory/search` 做到 ranking + context assembly + real search token savings，并完成了文档同步与决策补充。

---

## 1. Phase 2c 的边界

## 1.1 要做

### A. Retrieval 分层架构正式化

把现有 search 内部流程固化为可扩展三层：

```text
Recall Layer
→ Ranking Layer
→ Assembly Layer
```

### B. 为向量/混合召回预留正式接口

先把接口和数据结构搭好，不承诺必须在 Phase 2c 首批完成真实向量检索。

### C. 混合召回编排

支持未来：

```text
FTS recall
+ vector recall
+ merged candidate set
```

### D. Explainability 最小升级

让结果可解释，但不做花哨可视化。

### E. 保持诚实计量

search metering 继续只记录真实发生的值，不引入口径污染。

---

## 1.2 不做

### Phase 2c 明确不做

- 云端检索
    
- 托管向量库
    
- LLM 摘要压缩
    
- 自动策略学习
    
- 多租户 SaaS 级检索编排
    
- 复杂 RAG orchestration
    

这些都超出当前 Runtime 边界。OmniMemora 仍然必须是 Local First / Cloud Optional / Scope Governed。

---

## 2. Phase 2c 要解决的真实问题

## 2.1 当前 Phase 2b 的上限

你现在已经有：

- FTS5 recall
    
- BM25/fallback ranking
    
- recency/access boost
    
- excerpt + context assembly
    
- search token savings
    

但当前 recall 还是：

```text
关键词主导
```

这意味着问题不是 assembly，而是：

```text
召回结构还不够强
```

---

## 2.2 Phase 2c 的核心升级点

不是继续微调：

- boost 参数
    
- excerpt 长度
    
- token budget 常数
    

而是升级：

```text
Recall 架构本身
```

---

## 3. Phase 2c 总体结构

## 3.1 目标结构

```text
/memory/search
  → scope resolve
  → Recall Orchestrator
      → Keyword Recall Provider
      → Vector Recall Provider (optional)
  → Candidate Merge
  → Ranking Engine
  → Context Assembly
  → Metering
```

---

## 3.2 三层定义

### Layer 1: Recall Layer

负责：

- 候选召回
    
- 多召回源并行或串行执行
    
- 统一 candidate 输出格式
    

### Layer 2: Ranking Layer

负责：

- text/vector/relevance 信号归一化
    
- recency/access/metadata 等加权
    
- 最终排序
    

### Layer 3: Assembly Layer

负责：

- excerpt
    
- dedup
    
- token budget
    
- combined_text
    
- search token savings
    

---

## 4. Phase 2c 子阶段建议

## Phase 2c-1：Retrieval 接口抽象

先做架构，不急着做向量实装。

### 交付目标

- 抽象 RecallProvider 接口
    
- 抽象 CandidateMerger
    
- 抽象 RankingEngine
    
- 让 `/memory/search` 主流程不再直接绑死在 FTS5
    

---

## Phase 2c-2：Hybrid Ready

### 交付目标

- 引入 `vector_score` 的真实可接入路径
    
- 允许 provider 返回不同候选
    
- 支持 merged candidates 后统一排序
    

---

## Phase 2c-3：Explainability Minimal

### 交付目标

- 最小可解释 breakdown
    
- recall source 标记
    
- ranking source 标记
    

---

# 5. Phase 2c 核心接口设计

## 5.1 RecallProvider

```go
type RecallProvider interface {
    Name() string
    Enabled() bool
    Recall(ctx context.Context, req *pkg.SearchRequest, scopeRef *pkg.ScopeRef, limit int) ([]store.SearchCandidate, error)
}
```

### 初始实现

- `KeywordRecallProvider`：现有 FTS5 / LIKE 路径
    
- `VectorRecallProvider`：先占位，可返回 `not enabled`
    

---

## 5.2 CandidateMerger

```go
type CandidateMerger interface {
    Merge(groups map[string][]store.SearchCandidate, limit int) []store.SearchCandidate
}
```

### Phase 2c 默认策略

```text
按 memory_id 去重
保留多来源命中标记
取较优初始分
```

---

## 5.3 RankingEngine

```go
type RankingEngine interface {
    Rank(candidates []store.SearchCandidate, keyword string, caps store.SearchCapabilities) []ScoredResult
}
```

### 说明

把现在 `rankCandidates()` 从 service 里进一步抽离成独立组件。

---

## 5.4 AssemblyEngine

```go
type AssemblyEngine interface {
    Assemble(results []ScoredResult, keyword string, opts pkg.SearchOptions) (*pkg.AssembledContext, error)
}
```

### 说明

把 Phase 2b 的 `assembleContext()` 结构化，不再只是 service 内部函数。

---

# 6. SearchCandidate 结构扩展

建议在 `store.SearchCandidate` 或对应中间结构里增加：

```go
type SearchCandidate struct {
    MemoryID        string
    Content         string
    Metadata        map[string]any
    CreatedAt       time.Time
    UpdatedAt       time.Time
    LastAccessedAt  *time.Time
    AccessCount     int

    RecallSource    string   // keyword / vector / hybrid
    RecallSources   []string // 多来源命中时可选
    KeywordScore    float64
    VectorScore     float64
}
```

---

# 7. Ranking 模型升级方向

## 7.1 当前模型保留

先保留 Phase 2a 已验证路径：

```text
text_match_score
+ recency_boost
+ access_boost
+ vector_score
```

---

## 7.2 Phase 2c 升级为可组合模型

```text
final_score =
  keyword_component
+ vector_component
+ recency_component
+ access_component
+ metadata_component
```

---

## 7.3 当前要求

### 必须做到

- `vector_score` 不再只是字段占位
    
- 即使 vector provider 未启用，结构也成立
    
- keyword-only 路径仍完整可跑
    

---

# 8. Recall 编排策略

## 8.1 默认策略

Phase 2c 初始建议：

```text
keyword recall 先实现 provider 化
vector provider 先 stub
merge/rank 流程先打通
```

---

## 8.2 未来混合模式

后续支持：

```text
mode = keyword_only
mode = vector_only
mode = hybrid
```

请求可扩展为：

```json
{
  "options": {
    "retrieval_mode": "keyword_only"
  }
}
```

### 当前 Phase 2c 可先只支持

```text
keyword_only（默认）
hybrid（预留）
```

---

# 9. Explainability 最小设计

## 9.1 新增字段建议

在 `SearchResultItem` 中增加可选：

```go
RecallSource   string          `json:"recall_source,omitempty"`
ScoreBreakdown *ScoreBreakdown `json:"score_breakdown,omitempty"`
```

在 `ScoreBreakdown` 中扩展：

```go
type ScoreBreakdown struct {
    TextMatchScore float64 `json:"text_match_score"`
    VectorScore    float64 `json:"vector_score"`
    RecencyBoost   float64 `json:"recency_boost"`
    AccessBoost    float64 `json:"access_boost"`
}
```

---

## 9.2 原则

- 默认不返回复杂 breakdown
    
- 继续由 `include_breakdown` 控制
    
- 解释服务于调试，不搞成产品噪音
    

---

# 10. Metering 设计原则

## 10.1 不允许回退到假数据

Decision 10 已经确立了 Search Token Savings via Context Assembly 的诚实口径原则。

所以 Phase 2c 必须保持：

```text
无 assembly → savings = 0
无真实向量分 → vector_score 可为 0，但不能伪造
无真实压缩 → compressed_tokens 不伪造
```

---

## 10.2 可新增的 metering 字段

Phase 2c 如要扩展，可考虑新增：

- `recall_provider_count`
    
- `keyword_hits`
    
- `vector_hits`
    
- `hybrid_merged_hits`
    

但这不是第一优先级。

---

# 11. 配置设计建议

在 runtime config 中预留：

```json
{
  "search": {
    "retrieval_mode": "keyword_only",
    "enable_vector_provider": false,
    "max_recall_candidates": 30,
    "default_context_limit": 4,
    "default_max_context_tokens": 800
  }
}
```

---

# 12. 测试大纲

## 12.1 Retrieval 接口抽象测试

- provider 未启用时 keyword 路径仍可运行
    
- provider 返回空集时系统不崩
    

## 12.2 Candidate merge 测试

- 同一 memory 被多个 provider 命中时能正确去重
    
- recall source 标记正确
    

## 12.3 Ranking 测试

- keyword-only 路径分数不回退
    
- vector provider stub 不影响现有排序稳定性
    

## 12.4 Assembly 测试

- Phase 2b 已有测试全部不回退
    
- hybrid-ready 结构下仍能正确 assembly
    

## 12.5 Scope 测试

- 多 provider 路径下 scope 仍只在 SQL/recall 前置过滤后生效
    
- 不允许 vector provider 绕过 scope 边界
    

---

# 13. Phase 2c 验收标准

## 通过标准

- `/memory/search` 内部结构完成 provider 化 / engine 化
    
- keyword-only 路径保持通过
    
- Phase 2a/2b 行为不回退
    
- 为 vector/hybrid 留出真实接口，不是假字段堆积
    
- 诚实计量原则不被破坏
    

## 不通过标准

- 为了接入 vector 破坏 scope enforcement
    
- 为了做 hybrid 重写 Phase 2b 成熟逻辑
    
- 引入假分数、假 token、假 hit 统计
    
- 让 `/memory/search` 膨胀成难以维护的大函数
    

---

# 14. 一句话施工目标

```text
Phase 2c 不是继续打磨 search 参数，而是把 /memory/search 重构成可扩展 Retrieval Engine 骨架，在不破坏 Phase 2a/2b 已成立的 ranking、context assembly、诚实计量和 scope 治理前提下，为 vector/hybrid recall 做正式接口准备。
```

---

# 二、本窗口一页交接单

下面这页你可以直接复制到新窗口使用。

---

## OmniMemora 当前阶段交接单

### 当前状态

```text
Phase 1.2：已完成（Memory lifecycle closed loop）
Phase 2a：已完成（Ranking Search）
Phase 2b：已完成（Lightweight Context Assembly + Search Token Savings）
```

### 当前 `/memory/search` 已具备能力

```text
可检索 → 可排序 → 可组装 → 可计量 → 可迁移
```

### Phase 2b 最终结论

- 系统收官：✅
    
- 文档收官：✅
    
- 审计通过：✅
    

### 已完成的关键点

- scope-aware candidate recall
    
- FTS5/BM25 capability detection
    
- fallback text scoring
    
- recency/access ranking
    
- top-k stable return
    
- optional context assembly
    
- excerpt extraction
    
- token budget control
    
- real raw/compressed/saved token calculation
    
- memory_search metering
    
- metering schema auto-migration
    
- honest metering principle fixed
    
- scope leak test fixed
    
- ROADMAP / RUNTIME_ARCHITECTURE / DECISION_LEDGER 已同步 Phase 2b
    

### 当前约束

- 仍为 Local Runtime 能力，不引入云依赖
    
- 不做托管向量库
    
- 不做 LLM 摘要
    
- 不做复杂多策略 assembly
    
- 继续遵守 Default Isolated / Explicit Sharing
    
- 继续遵守 honest metering 原则
    

### 下一阶段目标

```text
Phase 2c：Retrieval 结构升级
```

### Phase 2c 核心目标

- 将 `/memory/search` 重构为可扩展 Retrieval Engine 骨架
    
- 分层为 Recall / Ranking / Assembly
    
- 抽象 RecallProvider / CandidateMerger / RankingEngine / AssemblyEngine
    
- keyword-only 路径继续稳定运行
    
- 为 vector/hybrid recall 提供正式接口预留
    
- 不破坏 Phase 2a/2b 已成立的 scope、安全、计量、assembly 逻辑
    

### Phase 2c 明确不做

- 云端检索
    
- 向量库托管
    
- LLM 压缩摘要
    
- cluster/timeline assembly
    
- 复杂自动策略路由
    

### 当前开发原则

```text
不要继续微调 boost 参数；
重点升级 retrieval 结构，不是继续打磨 Phase 2b 细节。
```

### 新窗口可直接执行的请求

```text
请基于当前状态，继续展开 OmniMemora Phase 2c：
输出可直接交给 CC 的工程设计大纲，重点是 Retrieval Engine 分层、RecallProvider 抽象、hybrid-ready 接口设计、测试与验收标准。
```

---

如果你要，我下一条可以直接把 **Phase 2c 的“给 CC 的极简施工 prompt”** 也写出来。