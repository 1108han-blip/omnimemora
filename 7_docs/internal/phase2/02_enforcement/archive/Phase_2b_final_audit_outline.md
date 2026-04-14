
> **阶段收官 → 文档/代码/决策一致性确认**

---

# OmniMemora Phase 2b 收官审计大纲

## 一、审计目标

确认 Phase 2b 是否真正满足以下四件事：

1. `/memory/search` 已完成从 ranking search 到 lightweight context retrieval 的升级
    
2. search token savings 已真实成立，而非占位字段
    
3. scope governance 在 assembly 后仍未回退
    
4. 文档、代码、计量、迁移四者一致
    

---

## 二、审计结论模板

先准备这个结论框架，最后填：

```text
状态：Phase 2b 已通过 / 有条件通过 / 未通过

结论维度：
- 架构对齐：✅ / ⚠️ / ❌
- 功能闭环：✅ / ⚠️ / ❌
- Metering闭环：✅ / ⚠️ / ❌
- Migration闭环：✅ / ⚠️ / ❌
- Scope安全性：✅ / ⚠️ / ❌
- 文档一致性：✅ / ⚠️ / ❌

最终判断：
Phase 2b 是否可以正式收官
是否允许进入下一阶段
```

---

# 三、审计维度

## 1. 架构对齐审计

### 目标

确认 Phase 2b 没有突破 Runtime 既定边界。

### 核查项

- `/memory/search` 仍属于 Local Runtime 核心 API
    
- 未引入云端依赖
    
- 未引入向量检索实装
    
- 未绕过 Store 抽象
    
- 未绕过 scope enforcement
    
- 未把 search 变成独立 retrieval service
    

### 判定标准

只要 Phase 2b 仍然是：

```text
本地检索 + 本地组装 + 本地计量
```

就算通过。

对齐依据：Runtime Architecture 对 `/memory/search`、本地检索、scope enforcement、metering 的职责定义。

---

## 2. 功能闭环审计

### 目标

确认 Phase 2b 新增能力真的成立，不是只多了几个字段。

### 核查项

#### A. Excerpt 提取

- 命中窗口提取是否生效
    
- 短文本是否直接保留
    
- 无命中是否退回首段逻辑
    

#### B. Context Assembly

- `assemble_context=false` 时无 `context`
    
- `assemble_context=true` 时有 `context`
    
- `context_limit` 生效
    
- 最多只组装规定数量条目
    

#### C. Token Budget

- `max_context_tokens` 是否生效
    
- 超预算时是否正确裁剪
    
- 是否至少保留 1 条 excerpt
    

#### D. Response 兼容

- `results` 结构未被替换
    
- 老客户端仍可正常消费
    

### 判定标准

必须证明：

```text
results 仍可用
+
context 新能力成立
```

不是二选一，而是并存。

---

## 3. Ranking 不回退审计

### 目标

确认 Phase 2b 没有把 Phase 2a 已完成的 ranking 能力搞乱。

### 核查项

- recall/ranking/top-k 主流程是否复用 Phase 2a
    
- assembly 是否发生在 ranked results 之后
    
- `score` 是否仍来自 Phase 2a 排序结果
    
- `context` 是否按排序后的顺序组装，而不是重新乱排
    

### 判定标准

必须是：

```text
Phase 2a ranking
→ Phase 2b assembly
```

不能变成：

```text
Phase 2b assembly 反向改写 ranking 结果
```

---

## 4. Scope 安全审计

### 目标

确认 context assembly 没有破坏 SQL scope enforcement。

### 核查项

- workspace A 数据在 workspace B search 中不可见
    
- agent scope 不可跨 agent 混入
    
- user scope 不可跨 user 混入
    
- assembly 只消费已通过 scope filter 的结果
    
- 没有任何“为组装方便再查一次”的跨 scope 行为
    

### 判定标准

必须确认：

```text
scope filter 在 SQL 层先完成
assembly 只是后处理
```

这点非常关键，对齐 Decision Ledger 和 Scope Model。

---

## 5. Token Savings 审计

### 目标

确认 search token savings 是“真实计算”，不是虚构指标。

### 核查项

- `raw_tokens` 是否基于参与 assembly 的全文条目
    
- `compressed_tokens` 是否基于最终 `combined_text`
    
- `saved_tokens = max(raw_tokens - compressed_tokens, 0)`
    
- `assemble_context=false` 时 savings 是否归零
    
- 是否不存在负 saved_tokens
    

### 判定标准

必须确认：

```text
raw_tokens 来源真实
compressed_tokens 来源真实
saved_tokens 非负且有定义依据
```

这一步决定 search 是否真正接上 Token Savings 主线。

---

## 6. Metering 审计

### 目标

确认 Phase 2b 的 search metering 不只是“代码里有字段”，而是事件链完整。

### 核查项

- `memory_search` 事件是否仍正常产生
    
- `raw_tokens` 是否被写入
    
- `assembled_hits` 是否被写入
    
- `compressed_tokens` / `saved_tokens` 是否为真实值
    
- 无 assembly 时事件是否仍可记录
    
- search 失败时是否不会写脏数据
    

### 判定标准

必须确认：

```text
search 功能闭环
+
metering 数据闭环
```

---

## 7. Migration 审计

### 目标

确认 Phase 2b 扩展字段对旧环境升级是安全的。

### 核查项

- 启动时是否执行 `migrateMeteringPhase2b()`
    
- 是否通过 `pragma_table_info` 检测缺列
    
- `ALTER TABLE ADD COLUMN` 是否幂等
    
- 旧 schema 升级后是否能正常写 `memory_search`
    
- 新环境建表是否不受影响
    
- 测试数据库是否覆盖 migration 路径
    

### 判定标准

必须确认：

```text
旧环境可自动升级
新环境可直接运行
无人工 SQL 前置要求
```

这一步决定 Phase 2b 是“功能完成”还是“版本完成”。

---

## 8. 测试完整性审计

### 目标

确认测试不是只测 happy path。

### 核查项

- excerpt 测试
    
- budget 测试
    
- savings 测试
    
- no negative saved tokens 测试
    
- context_limit 测试
    
- assemble_context 开关测试
    
- scope 不回退测试
    
- migration 测试
    
- results 兼容测试
    

### 判定标准

至少要覆盖：

```text
功能
兼容
安全
迁移
计量
```

如果只覆盖功能，不算完整收官。

---

## 9. 文档一致性审计

### 目标

确认项目文档口径该更新的地方已经更新，不再停留在 Phase 2a 或 Phase 1.2。

### 需要检查的文档

#### A. `ROADMAP_CURRENT.md`

检查是否需要把 Phase 1 的 `/memory/search` 与 `/memory/delete` 已完成状态更新掉。当前 Roadmap 里仍把 Phase 1.2 任务列为 delete/search/context。

#### B. `RUNTIME_ARCHITECTURE.md`

检查 `/memory/search` 说明是否仍停留在“关键词搜索”，是否需要补充：

- ranking search 已完成
    
- context assembly 已完成
    
- search token savings 已成立  
    当前文档里 `/memory/search` 还是基础关键词搜索口径。
    

#### C. `DECISION_LEDGER.md`

看是否需要新增一条实现级决策，例如：

- Search Token Savings via Context Assembly
    
- Metering Schema Auto-Migration for Search Phase 2b  
    如果不新增，也至少确认现有决策未被违反。
    

#### D. `MEMORY_SCOPE_MODEL.md`

确认 Phase 2b 没有引入任何与 scope 模型冲突的新行为。

### 判定标准

代码状态如果已变，文档仍旧，就不算真正收官。

---

# 四、建议输出格式

你审计时，建议按这个格式出报告：

## 1. 审计范围

```text
代码范围：
- pkg/types.go
- app/service.go
- metering/event.go
- metering/collector.go
- store/sqlite_store.go
- search_phase2b_test.go

文档范围：
- ROADMAP_CURRENT.md
- RUNTIME_ARCHITECTURE.md
- DECISION_LEDGER.md
- MEMORY_SCOPE_MODEL.md
```

## 2. 审计结果表

|维度|结果|说明|
|---|---|---|
|架构对齐|✅|未突破 Runtime 边界|
|功能闭环|✅|context assembly 已成立|
|Ranking 不回退|✅|Phase 2a 主流程保留|
|Scope 安全|✅|无跨 scope 混入|
|Token Savings|✅|已真实计算|
|Metering|✅|事件字段扩展完成|
|Migration|✅|启动自动补列|
|文档一致性|⚠️|需补更新|

---

## 3. 最终结论模板

```text
Phase 2b 审计结论：

- 代码实现：通过
- 功能闭环：通过
- Metering/Migration：通过
- Scope 安全：通过
- 文档同步：待补

最终判断：
Phase 2b 可以视为实现完成并可正式收官。
建议下一步先补文档同步，再决定是否进入 Phase 2c。
```

---

# 五、我对你下一步的建议

## 正确顺序

```text
先做 Phase 2b 审计
再补文档同步
最后决定是否开 Phase 2c
```

因为现在最容易漏的不是代码，而是**项目口径**。

---

