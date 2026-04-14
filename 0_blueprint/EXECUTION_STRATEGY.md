# EXECUTION_STRATEGY.md

**Status:** FINAL
**Role:** 执行策略 - 描述在被调用时如何优化 context（非产品定义）

---

# 一、核心原则

OmniMemora 不控制 memory，也不作为必经路径。

愿景对齐锚点：

> Keep it on, or things get worse.

当被调用时：

→ **对进入模型的 context 进行优化**
→ **仅输出最小必要结果，不输出决策过程**

---

# 二、执行定位（Phase 3.6）

OmniMemora 在当前阶段的角色：

→ **Context Optimization Layer（执行层能力）**

而不是：

- orchestration layer ❌
- memory controller ❌
- required gateway ❌

---

# 三、调用模型

```
Agent (ChatGPT / Codex / OpenClaw)
↓ (optional call)
OmniMemora
↓
Optimized Context
↓
LLM
```

---

# 四、执行范围（严格限制）

OmniMemora 只在以下范围内工作：

### 输入

- Omni memory（自身）
- native memory（若被调用方提供）

---

### 处理（允许）

- 去重（dedup）
- 排序（ranking）
- 截断（truncation）
- 压缩（compression）

---

### 输出

→ optimized context
→ 不包含策略、候选集、评分过程、control plane 元信息

---

# 五、禁止行为（必须写清）

OmniMemora 不得：

- 强制所有 memory 经过自身
- 阻止 agent 使用原生 memory
- 接管 memory routing
- 成为 context 唯一入口
- 演化为 orchestration system
- 向 LLM 暴露策略细节、候选集、评分过程
- 向 LLM 暴露 control plane 元信息

---

# 六、Phase 3.6 执行重点

## 6.1 Telemetry 修复

确保：

→ 所有调用都被正确记录（handshake / invocation）

---

## 6.2 Context Assembly（MVP）

目标：

→ 在 token budget 内生成最优 context

---

## 6.3 Native Memory 兼容

原则：

→ native memory 是数据源之一，而不是必须接管

---

# 七、策略扩展（Phase 3.7）

允许扩展：

- policy（recall / compression）
- 权重调节（source weighting）
- 跨会话 context 提示（非强注入）

---

# 八、核心锚点（唯一允许表达）

We do not control memory.

We optimize what is selected into context.
