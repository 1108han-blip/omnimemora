
---

# ✅ 最正确位置（直接结论）

```text
7_docs/phase3/
```

---

# 📂 为什么必须放在这里

你当前结构是：

```text
0_blueprint      → 理念/蓝图
1_architecture   → 架构
2_product        → 产品设计
3_governance     → 宪法/决策
4_core           → 核心实现
5_connectors     → 接入层
6_console        → UI/控制台
7_docs           → 文档层（说明/阶段文档）
```

👉 所以：

```text
Phase 3 文档 = 阶段性产品文档
→ 必须属于 7_docs
```

---

# 📁 你现在应该建成这样

在 `7_docs` 下新增：

```text
7_docs/
  external/
    api/
    guides/
    examples/
    release-notes/

  internal/
    phase1/
    phase2/
    phase3/
```

---

# 📦 phase3 内部结构（直接用）

```text
7_docs/phase3/
  PHASE3_OVERVIEW.md
  CAPABILITY_01_OBSERVABILITY.md
  CAPABILITY_02_INTEGRATION.md
  CAPABILITY_03_STABILITY.md
  NON_GOALS.md
  METRICS.md
```

---

# ❗ 不要放错的地方（很关键）

### ❌ 不要放在

```text
2_product/
```

原因：

```text
那是“长期产品结构”，不是阶段文档
```

---

### ❌ 不要放在

```text
1_architecture/
```

原因：

```text
Phase 3 不是架构升级阶段
```

---

### ❌ 不要放在

```text
3_governance/
```

原因：

```text
那是“规则”，不是“执行计划”
```

---

# 🔥 进阶优化（建议你做）

在 `7_docs` 下再加一个入口：

```text
7_docs/
  INDEX.md
  phase3/
```

---

## INDEX.md 写什么？

```text
# OmniMemora Docs Index

## Current Phase
→ Phase 3 (Productization)

## Entry
→ ./phase3/PHASE3_OVERVIEW.md
```

这样以后不会迷路。

---

# 🧠 一句话帮你记住

```text
Blueprint / Architecture / Governance = 不动
Phase 文档 = 永远进 7_docs
```

---

# 🚀 下一步建议

你现在可以直接做：

```text
1. 创建 7_docs/phase3/
2. 建 PHASE3_OVERVIEW.md
3. 把第一版内容填进去（高质量，不返工）
```
