# OmniMemora Demo UI & Metrics Panel（V1 实施方案）

---

# 一、设计目标（必须统一）

## 唯一目标

> **让用户在 10 秒内看懂：用了 OmniMemora 到底牛在哪**

---

## 不要做的

* 不要做后台管理系统
* 不要做复杂配置台
* 不要堆功能

---

## 要做到的

只做三件事：

1. **节省了多少 token**
2. **上下文变干净了多少**
3. **系统到底做了什么**

---

# 二、整体 UI 架构（四块屏）

---

## 页面结构（单页 Dashboard）

```text
┌────────────────────────────┐
│ OmniMemora Dashboard       │
├────────────────────────────┤
│ ① 核心指标（Hero Metrics） │
├────────────────────────────┤
│ ② 请求流（Live Flow）      │
├────────────────────────────┤
│ ③ 上下文对比（Before/After）│
├────────────────────────────┤
│ ④ 调用链（Call Chain）     │
└────────────────────────────┘
```

---

# 三、模块 ①：核心指标（最重要）

## 目标

> 一眼震撼

---

## UI（大卡片）

```text
┌────────────────────────────┐
│ Token Saved Today          │
│        92.7%              │
│ Saved: 18,230 tokens      │
└────────────────────────────┘
```

---

## 必须有 4 个指标

| 指标                 | 含义   | 数据来源        |
| ------------------ | ---- | ----------- |
| Token Saving %     | 节省比例 | meter       |
| Tokens Saved       | 绝对节省 | meter       |
| Requests           | 请求数  | meter_store |
| Avg Context Size ↓ | 压缩效果 | engine      |

---

## 数据接口设计

```json
GET /metrics/summary
```

```json
{
  "token_saving_ratio": 0.927,
  "tokens_saved": 18230,
  "request_count": 142,
  "avg_context_reduction": 0.88
}
```

---

## 实现任务

* 从 `meter_store` 聚合
* 做一个 `metrics_service.py`
* 提供 REST API

---

# 四、模块 ②：请求流（Live Flow）

## 目标

> 让用户看到"系统正在工作"

---

## UI

```text
[12:01:02] /memory/query → saved 92% → 4 memories selected
[12:01:05] /memory/query → bypass → implementation task
```

---

## 数据来源

* decision log（你已经有）

---

## API

```json
GET /metrics/recent_requests
```

---

## 实现

* 解析 stdout / log
* 存入 ring buffer（内存 or sqlite）

---

# 五、模块 ③：上下文对比（杀手级）

> 这是最核心卖点

---

## 目标

> 让用户看到"优化前 vs 优化后"

---

## UI

```text
BEFORE (10,000 tokens)
--------------------------------
[大量重复/噪音]

AFTER (800 tokens)
--------------------------------
[精选 4 条 memory]
```

---

## 数据结构

```json
GET /debug/context_diff?id=xxx
```

```json
{
  "before_tokens": 10000,
  "after_tokens": 800,
  "selected_memories": [...],
  "dropped_memories": [...]
}
```

---

## 实现关键

在 `/memory/query` 时，额外存：

* candidate_memories
* selected_memories
* packed_context

---

## 执行点

* 在 adapter 中增加 debug snapshot
* 存 SQLite / memory

---

# 六、模块 ④：调用链（专业感）

## 目标

> 让工程师信你

---

## UI（流程图）

```text
Request
 ↓
Unified Interface Layer (18011)
 ↓
Context Compiler
   ├─ filter
   ├─ route_score
   ├─ dedup
   ├─ select
   └─ pack
 ↓
Meter (saved 92%)
 ↓
Response
```

---

## API

```json
GET /debug/call_chain?id=xxx
```

---

## 数据来源

已经在：

* adapter
* engine

只需要"记录"

---

## 执行点

* 每一步打 trace_id
* 组装 chain JSON

---

# 七、技术选型

---

## 前端（快速）

* React + Vite
* 或直接：Next.js

---

## UI 库

* shadcn/ui（推荐）
* 或 Ant Design（更快）

---

## 图表

* recharts（简单）
* 或 echarts（复杂）

---

## 后端

直接复用：

* FastAPI（你已有）

---

## 路由新增

```text
/metrics/*
/debug/*
```

---

# 八、最小可运行版本（MVP）

---

## 3天内必须完成

### 后端

* [ ] `/metrics/summary`
* [ ] `/metrics/recent_requests`
* [ ] `/debug/context_diff`
* [ ] `/debug/call_chain`

---

### 前端

* [ ] 一个 dashboard 页面
* [ ] 4 个模块展示

---

# 九、数据流（必须对齐）

---

```text
User Request
 ↓
Unified Interface Layer (Python Adapter :18011)
 ↓
Context Compiler (engine.optimize_context)
   ├─ filter
   ├─ route_score
   ├─ dedup
   ├─ select
   └─ pack
 ↓
Meter Store
 ↓
Trace Store
 ↓
Debug Snapshot (新增)
 ↓
UI 展示
```

---

# 十、关键设计原则

---

## 1 "所有数据来自真实运行"

不能 mock

---

## 2 "一切围绕 token savings"

不要偏

---

## 3 "一屏讲清价值"

不要多页面

---

# 十一、UI 的真正作用

不是为了好看。

而是：

> **把"不可见的上下文优化"变成"可销售的证据"**

---

# 十二、优先级

```
目标：3天内做出 Demo Dashboard

优先级：
1. metrics summary
2. context diff
3. call chain
4. live flow

要求：
- 数据必须来自真实运行
- 不允许 mock
- 单页完成
```

---

**创建时间**: 2026-04-13
**版本**: V1
**状态**: 实施方案
