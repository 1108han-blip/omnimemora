进入论文模式，可以直接把这一轮定成：

**“OmniMemora 的实验方法学补全稿”**

你现在最需要的，不是继续泛泛谈“论文怎么写”，而是把**实验问题、baseline、指标、脚本结构**钉死。这样后面无论投 arXiv，还是压成 NeurIPS/ICLR/AAAI 风格，骨架都不会再散。

先把产品边界锁住，不然后面的实验会跑偏：OmniMemora 不是 memory system，不接管 memory ownership，不是 orchestration layer，只是一个**optional context optimization layer**，核心任务是**优化进入模型前的 context，提升 context quality，降低 token usage**。这点必须成为实验设计的总前提。

---

# 一、论文实验的核心研究问题

建议把实验部分统一收束成 3 个研究问题。

## RQ1：OmniMemora 是否能显著降低 context token 开销？

这是你现在最强、最硬的主结果，因为你已经有 token savings 数据，而且这正是产品宪法明确要求可观测、可展示、可计量的核心能力。

## RQ2：在压缩 context 的同时，OmniMemora 是否保持或提升任务有效信息密度？

也就是不能只看“省了多少 token”，还要证明“不是瞎砍”。这部分要用检索质量、保真度、任务完成表现来支撑。

## RQ3：OmniMemora 在不同 agent / workspace / task 类型下是否稳定？

这对应你现在产品 Phase 3 的方向：observability、integration simplicity、stability，以及按 workspace / agent / scope 的分维度统计。

---

# 二、实验总体结构

建议直接拆成四组实验。

## Exp-1：Token Efficiency 主实验

目标：证明 OmniMemora 显著降低 context token 使用。

输入：同一批 query + candidate memories  
对照：不同 baseline  
输出：optimized context  
指标：token savings、compression ratio、budget fit rate

这是主表 1。

---

## Exp-2：Quality Preservation 实验

目标：证明压缩后仍保留高价值信息，不显著损伤可用性。

输入：有“理想应保留记忆”的标注样本，或规则式 silver labels  
输出：被选入 context 的 memory 集合  
指标：Recall@K、Precision@K、Coverage、Redundancy Reduction、Faithfulness

这是主表 2。

---

## Exp-3：Ablation 消融实验

目标：证明 OmniMemora 的有效性来自哪些模块，而不是“随便截断也差不多”。

建议消融：

- 去掉 dedup
    
- 去掉 ranking
    
- 去掉 compression
    
- 去掉 scope-aware filtering
    
- 去掉 policy weighting
    

这会成为论文里最能体现“不是拍脑袋工程”的部分。你的架构文件里已经明确允许的处理范围就是 dedup / ranking / truncation / compression，这些天然适合做消融。

---

## Exp-4：Robustness / Deployment-style 实验

目标：证明跨 agent、跨 workspace、跨 task 类型稳定。

分桶：

- task type：continuation / decision / implementation
    
- agent：Codex / Claude Code / OpenClaw
    
- scope：agent / workspace / user
    
- noise condition：normal / high-duplication / high-noise / near-budget-limit
    

你之前已经有 continuation、decision、implementation 三类样本，这正好直接升格为实验维度。

---

# 三、baseline 设计

这里不能乱。baseline 一旦定义差，论文会显得虚。

建议分成四层 baseline。

## Baseline A：Raw Retrieval

定义：不做任何优化，直接把召回结果按原顺序或原分数拼入 context。

作用：证明“OmniMemora 比不处理更好”。

这是最基础、最必须有的 baseline。

---

## Baseline B：Top-K Retrieval

定义：按照检索分数或召回顺序，只取前 K 条，不做 dedup，不压缩。

作用：证明你的提升不只是“少拿一点”。

它是最强的简单 baseline。

---

## Baseline C：Token-Budget Truncation

定义：按顺序拼接候选内容，超过 token budget 就截断。

作用：证明你不是靠“暴力砍长度”获胜。

这个 baseline 很关键，因为很多系统默认就是这么干的。

---

## Baseline D：Dedup-only / Compression-only

定义：

- Dedup-only：只去重，不重排不压缩
    
- Compression-only：只压缩，不做选择优化
    
- Rank-only：只排序，直到预算上限
    

作用：这是半 baseline、半消融，能证明 OmniMemora 的组合策略优于单模块策略。

---

## 可选 Baseline E：Heuristic Summarization Baseline

定义：把候选 memory 先合并再做简单摘要，直到预算内。

作用：模拟“常见工程直觉做法”。

但这条 baseline 有一个风险：如果你没有稳定 summarizer 或摘要质量不稳，容易引入噪声。可以作为附录实验，不一定放主表。

---

# 四、baseline 的正式表述方式

论文里可以直接这样写：

- **Raw**: concatenate retrieved memories without optimization.
    
- **Top-K**: keep the top-K retrieved items under fixed K.
    
- **Truncate-to-Budget**: concatenate memories in ranked order and truncate to fit the token budget.
    
- **Dedup-only**: apply duplicate filtering only.
    
- **Rank-only**: rank candidates and include them until the token budget is reached.
    
- **OmniMemora**: apply scoped filtering, deduplication, ranking, and compression under a fixed token budget.
    

这样写出来，逻辑就完整了。

---

# 五、指标体系

你要把指标分成四类，不要只盯 token savings。

## 1. 效率指标

这是你的主指标组。

### Token Savings

[  
\text{Token Savings} = \text{Raw Tokens} - \text{Compressed Tokens}  
]

### Savings Rate

[  
\text{Savings Rate} = \frac{\text{Raw Tokens} - \text{Compressed Tokens}}{\text{Raw Tokens}}  
]

### Compression Ratio

[  
\text{Compression Ratio} = \frac{\text{Compressed Tokens}}{\text{Raw Tokens}}  
]

### Budget Fit Rate

在固定 token budget 下，输出 context 未超预算的比例。

这很重要，因为“能省 token”和“稳定卡进预算”不是一回事。

---

## 2. 信息保留指标

这是防止审稿人说你只是“压缩得狠”。

### Gold Coverage / Evidence Recall

在应保留记忆集合 (G) 中，被保留到输出 context 的比例。

[  
\text{Coverage} = \frac{|G \cap S|}{|G|}  
]

其中 (S) 是被选入 context 的 memory 集合。

### Precision@K

选中的 memory 里，有多少是真正相关的。

### Recall@K

应该保留的 memory 里，你保留了多少。

### MRR / nDCG

如果你有排序分数和标注等级，可以加。  
没有强标注就别硬上，避免实验体系过重。

---

## 3. 冗余抑制指标

这组指标很适合 OmniMemora，因为你的核心价值之一就是 dedup / compile。

### Redundancy Rate

输出 context 中，近重复内容占比。

### Unique Information Density

单位 token 内承载的唯一信息量。

这个指标可以定义成：  
[  
\text{UID} = \frac{\text{# unique facts retained}}{\text{compressed tokens}}  
]

如果人工标注太重，可以先用 rule-based fact unit 或 sentence cluster 近似。

---

## 4. 稳定性指标

这会让实验看起来更像系统论文，而不是一次性 demo。

### Variance Across Agents

不同 agent 上 savings rate 的方差。

### Variance Across Task Types

continuation / decision / implementation 三类任务上的方差。

### Failure Rate

输出为空、超预算、明显错选的比例。

### Latency Overhead

OmniMemora 相对 Raw / Top-K 增加的运行时间。

注意：你这个产品不是以重推理为核心，所以 latency 不必追求极低，但必须证明 overhead 可控。

---

# 六、推荐主指标组合

真正写论文时，主文里别塞太多，建议主指标就这 6 个：

1. Token Savings
    
2. Savings Rate
    
3. Budget Fit Rate
    
4. Coverage / Recall of relevant memory
    
5. Redundancy Rate
    
6. Latency Overhead
    

这 6 个已经能完整说明：  
**省没省、稳不稳、有没有砍错、代价大不大。**

---

# 七、数据集与样本构造

你现在不一定有标准公开 benchmark，所以建议分两层。

## 层 1：内部受控 benchmark

你自己构造 evaluation suite。

按任务类型分：

- continuation tasks
    
- decision tasks
    
- implementation tasks
    

按噪声条件分：

- normal
    
- high duplication
    
- many noise
    
- near token limit
    

这和你现有样本完全契合。

---

## 层 2：真实部署日志回放

把线上/本机 usage logs 脱敏后，回放成离线评测集。

每条样本包括：

- query
    
- candidate memories
    
- original token count
    
- optimized token count
    
- selected memory ids
    
- task tag
    
- scope
    
- agent
    

这样实验会非常像真实系统评测。

---

# 八、标注方案

如果你现在没有人工标注体系，不要停住。先上 **silver labeling**。

## 方案 A：规则式 silver label

为每个任务预先指定“核心应保留记忆”。  
例如：

- continuation：应包含最近计划、上次结论、执行状态
    
- decision：应包含约束、已决策项、不可违反边界
    
- implementation：应包含接口、目录、能力边界、未实现项
    

这个特别适合你当前项目，因为产品边界和架构边界本来就清楚。像 Constitution、Product Definition、Execution Strategy 这些本身就能作为任务 gold evidence 来源。

## 方案 B：人工双人标注

后续增强版可以做：

- 两个标注者独立选择“必须保留记忆”
    
- 计算 Cohen’s Kappa
    
- 分歧交由第三人仲裁
    

这会更像正式论文，但不是你现在的第一优先级。

---

# 九、实验脚本结构

这里建议直接产品化成一个 `eval/` 目录。

```text
eval/
├── README.md
├── configs/
│   ├── exp_token_efficiency.yaml
│   ├── exp_quality.yaml
│   ├── exp_ablation.yaml
│   └── exp_robustness.yaml
├── data/
│   ├── benchmark/
│   │   ├── continuation.jsonl
│   │   ├── decision.jsonl
│   │   ├── implementation.jsonl
│   │   └── mixed_eval.jsonl
│   └── replay/
│       └── usage_log_replay.jsonl
├── baselines/
│   ├── raw_concat.py
│   ├── topk.py
│   ├── truncate_budget.py
│   ├── dedup_only.py
│   ├── rank_only.py
│   └── summarize_baseline.py
├── metrics/
│   ├── token_metrics.py
│   ├── retrieval_metrics.py
│   ├── redundancy_metrics.py
│   └── stability_metrics.py
├── runners/
│   ├── run_single_exp.py
│   ├── run_all.py
│   ├── run_ablation.py
│   └── replay_logs.py
├── labeling/
│   ├── build_silver_labels.py
│   └── validate_labels.py
├── reports/
│   ├── tables.py
│   ├── plots.py
│   └── export_latex.py
└── outputs/
    ├── raw_results/
    ├── aggregated/
    └── figures/
```

---

# 十、单样本数据结构建议

建议每条 eval sample 长这样：

```json
{
  "sample_id": "decision_001",
  "task_type": "decision",
  "agent": "codex",
  "scope": "workspace",
  "query": "Should we move to Phase 4 billing now or finish Phase 3 observability first?",
  "candidate_memories": [
    {
      "id": "mem_1",
      "content": "...",
      "source": "constitution",
      "retrieval_score": 0.87
    },
    {
      "id": "mem_2",
      "content": "...",
      "source": "roadmap",
      "retrieval_score": 0.83
    }
  ],
  "token_budget": 1200,
  "gold_memory_ids": ["mem_1", "mem_2"],
  "metadata": {
    "noise_level": "normal",
    "duplication_level": "medium"
  }
}
```

---

# 十一、每个 runner 的输出结构

统一输出，后面才好聚合。

```json
{
  "sample_id": "decision_001",
  "method": "omnimemora",
  "raw_tokens": 1840,
  "compressed_tokens": 420,
  "saved_tokens": 1420,
  "savings_rate": 0.7717,
  "selected_memory_ids": ["mem_1", "mem_2"],
  "coverage": 1.0,
  "precision_at_k": 1.0,
  "redundancy_rate": 0.08,
  "latency_ms": 37.2,
  "budget_fit": true
}
```

---

# 十二、主表设计

## Table 1：Main Efficiency Results

列建议：

- Method
    
- Raw Tokens
    
- Output Tokens
    
- Token Savings
    
- Savings Rate
    
- Budget Fit Rate
    
- Latency
    

---

## Table 2：Quality Preservation

列建议：

- Method
    
- Coverage
    
- Precision@K
    
- Recall@K
    
- Redundancy Rate
    
- Unique Info Density
    

---

## Table 3：Ablation

列建议：

- Variant
    
- Savings Rate
    
- Coverage
    
- Redundancy Rate
    
- Budget Fit Rate
    

---

## Table 4：Robustness by Task / Agent

列建议：

- Group
    
- Savings Rate Mean
    
- Savings Rate Std
    
- Coverage Mean
    
- Failure Rate
    

---

# 十三、图表建议

建议至少 4 张图。

## Figure 1

不同方法的 token savings 柱状图

## Figure 2

Coverage vs Savings Rate 散点图  
这张图很重要，一眼看出“省 token 同时不掉质量”。

## Figure 3

Ablation 雷达图或柱状图  
展示 dedup / ranking / compression 各自贡献

## Figure 4

按 task type / agent 的稳定性箱线图

这几张图就足够支撑一篇系统型短论文了。

---

# 十四、统计检验

别太重，但要有。

建议：

- 对 Savings Rate、Coverage 用配对 t-test 或 Wilcoxon signed-rank test
    
- 报告 mean ± std
    
- 报告 effect size
    

如果样本数量不大，优先 Wilcoxon，更稳一点。

---

# 十五、与产品架构的一致性要求

实验设计不能越界。你要特别注意：

OmniMemora 的实验对象必须是**context optimization**，不是“证明自己比完整 memory system 更强”。因为产品宪法已经明确：

- 不做主记忆存储
    
- 不接管 memory ownership
    
- 不演化为 retrieval pipeline / orchestration / adaptive learning system
    
- 只允许对已召回结果做选择与压缩。
    

所以论文表述上要避免这些危险说法：

- “OmniMemora improves memory retrieval end-to-end”
    
- “OmniMemora learns to manage long-term memory”
    
- “OmniMemora acts as a unified memory layer”
    

都别写。

应该写成：

- “OmniMemora optimizes retrieved context under a fixed token budget.”
    
- “OmniMemora is evaluated as an optional control-plane layer over pre-retrieved candidate memories.”
    
- “The system does not replace memory backends and is measured only on context selection and compression.”
    

---

# 十六、你现在最适合采用的实验口径

我给你一个最稳的论文口径：

**OmniMemora is evaluated as a control-plane context optimizer over fixed candidate memory sets.**  
Given a query, a set of candidate memories, and a token budget, the system selects and compresses evidence to maximize information retention while minimizing token cost.

这句话一出来，整篇论文就稳了。

---

# 十七、你下一步最该立刻落地的内容

按优先级排：

第一步，先把 **benchmark schema + baseline runners** 定下来。  
第二步，把你现有 token savings 样本整理进统一 `jsonl`。  
第三步，补一个 **silver label**，至少能算 Coverage / Precision / Recall。  
第四步，跑出第一版 3 张主表。

先别急着雕摘要和标题。没有实验骨架，摘要写得再漂亮也空。

---

# 十八、我建议你直接采用的最终实验框架

可以直接写进论文方法节：

**Experimental Setup**

- Fixed candidate-memory evaluation
    
- Multiple task types: continuation, decision, implementation
    
- Multiple noise regimes: normal, high-duplication, high-noise, near-budget
    
- Multiple baselines: Raw, Top-K, Truncate-to-Budget, Dedup-only, Rank-only
    
- Metrics: Token Savings, Savings Rate, Budget Fit Rate, Coverage, Precision@K, Redundancy Rate, Latency
    
- Ablations: no-dedup, no-ranking, no-compression, no-scope-filter
    
- Robustness: across agents, workspaces, and scopes
    

这已经是论文级结构了。

---

# 十九、一个更狠但更现实的判断

你现在不缺“想法”，你缺的是**一个能重复跑、能出表、能导出 LaTeX 的评测框架**。

论文成不成，基本不取决于你再聊多少概念，而取决于下面这件事有没有做好：

**给任意一批 query + candidates，能不能一键跑出 baseline 对比、指标汇总、图表和 latex table。**

这件事一旦做成，OmniMemora 才真正像一个能投稿的系统，而不只是一个理念。

如果你愿意，我下一轮直接给你出一份**“实验目录 + JSON schema + baseline runner 伪代码 + LaTeX表格模板”**，可以直接喂给 CC 开始实现。