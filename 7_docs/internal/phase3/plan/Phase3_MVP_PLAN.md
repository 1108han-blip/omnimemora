
我会严格对齐你交接单 + 宪法 + roadmap，不做任何越界设计。

---

# ✅ OmniMemora Phase 3 MVP（严格受控版）

基于交接单：  
对齐 Roadmap Phase 3：  
遵守宪法（不漂移）：

---

# 一、Phase 3 的本质（先说透）

你现在不是缺能力：

```text
Phase 2 = 能力已经成立（而且是对的）
Phase 3 = 让“能力变成产品价值”
```

一句话：

```text
把“token savings 能力” → 变成“用户看得见 + 感知得到 + 愿意用”
```

---

# 二、MVP 范围（只做三件事）

严格收敛，不扩散：

```text
1. Observability（可观测）
2. Integration（接入简单）
3. Stability（稳定性）
```

禁止新增任何“智能能力”。

---

# 三、MVP 模块拆解（可以直接做）

---

## ① Metrics API（增强版）

👉 在现有 `/metrics` 基础上补全结构（不改语义）

### 新增字段（必须）

```json
{
  "token_savings": {
    "total_saved_tokens": 1120000,
    "today_saved_tokens": 120000,
    "week_saved_tokens": 580000,
    "month_saved_tokens": 1120000
  },
  "efficiency": {
    "avg_compression_ratio": 0.28,
    "avg_saved_per_query": 132
  }
}
```

---

### 新增 breakdown（核心）

```json
{
  "by_workspace": {
    "proj_alpha": {
      "saved_tokens": 600000,
      "queries": 3200
    }
  },
  "by_agent": {
    "codex": {
      "saved_tokens": 400000
    },
    "claude_code": {
      "saved_tokens": 300000
    }
  }
}
```

---

### 🚨 注意

- ❌ 不允许新增复杂计算逻辑
    
- ✅ 只做 aggregation（聚合）
    

符合宪法：

```text
Control Plane 做聚合，不做智能
```

---

## ② Search Response 可观测增强（关键）

👉 不改接口结构，只增强 `context` 字段

当前：

```json
"context": {
  "strategy": "topk_excerpt",
  "raw_tokens": 640,
  "compressed_tokens": 220,
  "saved_tokens": 420
}
```

---

### 新增（MVP核心）

```json
"context": {
  ...
  "compression_ratio": 0.34,
  "strategy_resolved": "topk_excerpt",
  "mode": "balanced",
  "items_selected": 4,
  "token_budget_used": 220
}
```

---

### 价值（非常关键）

这一步直接让：

```text
“黑盒优化” → “可解释能力”
```

---

## ③ Lightweight Console（极简版 UI）

👉 不做完整 SaaS，只做本地可视化

### 形式（两种选一个）

#### 方案 A（推荐）

```text
http://127.0.0.1:8765/dashboard   # Go Runtime 内部面板（非产品入口）
```

#### 方案 B

```bash
omnimemora dashboard
```

---

### 页面结构（只做一个页面）

```text
[Token Savings Overview]

总节省：
1,120,000 tokens

今日：
120,000

本周：
580,000

---

[Breakdown]

Workspace:
- proj_alpha → 600k

Agent:
- codex → 400k
- claude_code → 300k

---

[Trend]

Day 1: ███
Day 2: ██████
Day 3: █████████
```

---

### 🚨 强约束

- ❌ 不做复杂 UI
    
- ❌ 不做权限系统
    
- ❌ 不做云同步
    

只做：

```text
“让用户第一次看到价值”
```

---

## ④ One-line Integration（必须做）

👉 这是 Phase 3 成败关键

---

### Codex / CC 接入标准

```python
client.post("/memory/search", {
  "keyword": "...",
  "options": {
    "assemble_context": true
  }
})
```

---

### 你要额外做一件事：

👉 出一个 **官方推荐调用模板**

```json
{
  "keyword": "...",
  "options": {
    "assemble_context": true,
    "context_mode": "balanced",
    "context_strategy": "auto"
  }
}
```

---

### 并明确一句话：

```text
默认调用 = 最优策略（用户不需要理解任何机制）
```

---

## ⑤ Deterministic Guarantee（稳定性）

👉 Phase 3 必须加测试

---

### 新增测试（必须）

```text
同一 query + 同一数据

→ 连续调用 10 次

结果必须完全一致
```

---

### 覆盖范围

- strategy=auto
    
- 不同 mode
    
- token budget 边界
    

---

### 原因（很关键）

你这个产品：

```text
不是 AI → 是基础设施
```

不稳定 = 直接废掉

---

# 四、MVP 不做清单（再强调一次）

严格执行 DECISION_LEDGER：

---

## ❌ 一律禁止

```text
- reranker
- embedding 优化
- query 理解
- 多阶段 pipeline
- 自动学习策略
- cache（继续禁用）
```

---

## 判断标准（你以后用这个自检）

```text
这个功能是在“变聪明”吗？

是 → 砍掉
不是 → 可以做
```

---

# 五、MVP 验收标准（你可以直接用）

---

## ✅ 必须满足

### 1. 用户能看到价值

```text
打开 dashboard
→ 能看到 token savings
```

---

### 2. 接入简单

```text
1 次 API 调用
→ 自动生效
```

---

### 3. 数据可信

```text
saved_tokens = 真值（不是估算）
```

（你 Phase 2c.5 已经做对了 👍）

---

### 4. 稳定

```text
同输入 → 同输出
```

---

# 六、一句话执行版（你直接喂 Codex）

你可以直接丢这段：

---

```text
实现 OmniMemora Phase 3 MVP（严格受控版）：

目标：
只做 productization，不增加任何智能能力

任务：

1. 增强 /metrics：
   - total / today / week / month token savings
   - by_workspace / by_agent breakdown
   - efficiency metrics（compression_ratio）

2. 增强 /memory/search response：
   - compression_ratio
   - strategy_resolved
   - mode
   - items_selected
   - token_budget_used

3. 实现本地 dashboard：
   - 展示 token savings overview
   - workspace / agent breakdown
   - 简单趋势图
   - 不做权限，不做云

4. 提供默认 integration 模板：
   - assemble_context=true
   - context_strategy=auto
   - context_mode=balanced

5. 加 deterministic 测试：
   - 相同输入必须返回相同 context

约束（必须遵守）：

- 不允许引入 query understanding
- 不允许 multi-stage pipeline
- 不允许 learning / adaptive
- 不允许 cache 启用
- 只允许 aggregation 和展示
```

---
