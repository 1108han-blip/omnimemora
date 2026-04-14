
# OmniMemora Phase 3 文档模板（标准版）

> 目标：  
> **只允许扩展能力，不允许改变边界**

---

# 0. 文档总结构（建议直接建目录）

```text

  /phase3
    PHASE3_OVERVIEW.md
    CAPABILITY_01_OBSERVABILITY.md
    CAPABILITY_02_INTEGRATION.md
    CAPABILITY_03_STABILITY.md
    NON_GOALS.md
    METRICS.md
```

---

# 1. PHASE3_OVERVIEW.md（唯一入口）

## 1.1 Phase 定义

```text
Phase 3 = Productization & Adoption
```

---

## 1.2 目标（只允许这三条）

```text
1. 可观测性（Observability）
2. 接入成本（Integration Simplicity）
3. 稳定性（Stability）
```

---

## 1.3 不做什么（必须写）

```text
Phase 3 明确不做：

- Retrieval pipeline 演进
- Query understanding
- Agent orchestration
- Memory ownership
- Learning / feedback system
```

---

## 1.4 系统边界（引用宪法）

```text
OmniMemora 仍然是：

Memory Augmentation Layer

仅作用于：
→ /memory/search 的 context 优化
```

---

## 1.5 成功标准（必须量化）

```text
- ≥ 80% search 请求开启 assemble_context
- 平均 token savings ≥ 30%
- 至少 2 个 Agent（CC / Codex / OpenClaw）稳定接入
```

---

# 2. CAPABILITY_01_OBSERVABILITY.md

## 2.1 目标

```text
让用户“看见”token savings 和策略效果
```

---

## 2.2 当前已有数据（直接引用）

```text
- raw_tokens
- compressed_tokens
- saved_tokens
- assembled_hits
- strategy_effectiveness
```

---

## 2.3 Phase 3 新增（只允许 UI/统计）

```text
1. 每次 search 返回 summary：

{
  "context_summary": {
    "strategy": "...",
    "saved_tokens": ...,
    "compression_ratio": ...
  }
}

2. 聚合统计（按 strategy）

- avg saved_tokens
- avg compression_ratio
- usage frequency
```

---

## 2.4 禁止扩展

```text
❌ 不引入策略学习
❌ 不动态调整 strategy
❌ 不引入 ranking feedback
```

---

# 3. CAPABILITY_02_INTEGRATION.md

## 3.1 目标

```text
让 Agent “无脑接入”
```

---

## 3.2 最小接入方式（核心）

```text
POST /memory/search

{
  "query": "...",
  "options": {
    "assemble_context": true
  }
}
```

---

## 3.3 默认行为（必须稳定）

```text
默认：

strategy = auto
mode = balanced
```

---

## 3.4 Phase 3 增强（允许做）

```text
1. SDK 封装（轻量）

searchWithContext(query)

2. Agent 适配指南（文档级）

- CC
- Codex
- OpenClaw
```

---

## 3.5 禁止扩展

```text
❌ 不做 Agent runtime
❌ 不接管 prompt 构建
❌ 不嵌入 Agent 内部状态
```

---

# 4. CAPABILITY_03_STABILITY.md

## 4.1 目标

```text
保证输出稳定 + metering 可信
```

---

## 4.2 必须保证

```text
1. deterministic assembly
2. token 计算一致
3. strategy 解析一致
```

---

## 4.3 Phase 3 增强

```text
1. 回归测试强化

- token consistency test
- strategy consistency test

2. 大规模数据测试

- 10k / 100k memory items

3. 边界测试

- 空结果
- 超长 query
```

---

## 4.4 禁止扩展

```text
❌ 不引入 adaptive system
❌ 不做自优化
```

---

# 5. NON_GOALS.md（非常关键）

这个文件必须存在。

---

## 内容（直接用）

```text
OmniMemora Phase 3 明确不做：

1. Retrieval Engine
2. Query Understanding
3. Agent Orchestration
4. Multi-stage Pipeline
5. Learning System

任何 PR / 设计若触及以上内容，必须被拒绝。
```

---

# 6. METRICS.md（产品级指标）

---

## 6.1 核心指标

```text
Token Efficiency

= saved_tokens / raw_tokens
```

---

## 6.2 Strategy 指标

```text
- usage %
- avg saved_tokens
- avg compression_ratio
```

---

## 6.3 系统指标

```text
- P95 latency
- error rate
- assembly success rate
```

---

## 6.4 禁止指标

```text
❌ “模型理解能力”
❌ “query 意图识别率”
```

---

# 七、使用方式（你接下来怎么用）

你只需要：

---

## Step 1

创建 Phase 3 文档结构

---

## Step 2

把当前系统能力填进：

```text
PHASE3_OVERVIEW.md
```

---

## Step 3

逐个 capability 填内容

---

## Step 4

强制写 NON_GOALS.md（不要偷懒）

---

# 八、最关键的一句话

```text
Phase 2 是“把能力做对”
Phase 3 是“只允许能力被使用，不允许能力变形”
```
