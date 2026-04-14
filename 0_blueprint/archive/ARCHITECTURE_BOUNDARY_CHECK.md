# ARCHITECTURE_BOUNDARY_CHECK.md

**Status:** ACTIVE
**Scope:** 所有 PATCH / Implementation Guide 文档
**Last Updated:** 2026-04-09

---

# 一、架构边界检查规则

所有 PATCH / Implementation Guide 文档在合入前必须通过以下三条检查：

| # | 规则 | 检查动作 |
| --- | --- | --- |
| **G-1** | PATCH 不得引入 Blueprint 未定义结构 | 在 `0_blueprint/` 和 `RUNTIME_ARCHITECTURE.md` 中溯源，无定义则禁止 |
| **G-2** | Interface 实现必须在 RUNTIME_ARCHITECTURE 找到映射 | 检查 `RUNTIME_ARCHITECTURE.md` 第八节 Store 接口，无映射则禁止 |
| **G-3** | Scope / Identity 字段必须 100% 对齐 Blueprint | 对比 `MEMORY_SCOPE_MODEL.md` 和 `RUNTIME_ARCHITECTURE.md` 5.2 节，不一致则强制对齐 |

---

# 二、逐条检查标准

## G-1：PATCH 不得引入 Blueprint 未定义结构

**检查范围：** scope 类型、sharing_mode、memory_level、Backend 类型、端口号

**通过条件：**
- 新增的 scope 类型在 `MEMORY_SCOPE_MODEL.md` 中有定义
- 新增的 sharing_mode 在 `MEMORY_SCOPE_MODEL.md` 中有定义
- 新增的 Backend/Store 类型在 `RUNTIME_ARCHITECTURE.md` 第八节有对应接口

**禁止示例：**

```python
# ❌ 在 PATCH 中引入 Blueprint 未定义的 scope
scope = "team"  # MEMORY_SCOPE_MODEL.md 无此定义

# ❌ 在 PATCH 中引入 Blueprint 未定义的 sharing_mode
sharing_mode = "read_write"  # Blueprint 只定义 isolated/shared/shared_read_only/custom
```

## G-2：Interface 实现必须在 RUNTIME_ARCHITECTURE 找到映射

**检查范围：** Backend 接口、Store 抽象、API 端点

**通过条件：**
- Backend 的 `write / search / read / delete` 方法可在 `RUNTIME_ARCHITECTURE.md` 第八节 Store 接口找到对应签名
- API 端点与 `RUNTIME_ARCHITECTURE.md` 第七节一致或明确标注为 Future

**禁止示例：**

```python
# ❌ PATCH 定义了 RUNTIME_ARCHITECTURE 未覆盖的新接口
async def vector_search(self, query: str, scope: ScopeRef) -> List[MemoryRecord]:
    # RUNTIME_ARCHITECTURE.md 第八节无 vector_search 定义（MVP 不含向量检索）
    ...
```

## G-3：Scope / Identity 字段必须 100% 对齐 Blueprint

**检查范围：** ScopeRef 结构、MemoryRecord.scope_ref、metering event 字段

**通过条件：**
- ScopeRef 包含 Blueprint 定义的完整字段（user_id / workspace_id / scope / agent_id / sharing_mode）
- ScopeRef 包含 `tenant_id`（RUNTIME_ARCHITECTURE.md 5.2 定义）
- Metering event 字段与 RUNTIME_ARCHITECTURE.md 5.4 节 100% 对齐

**禁止示例：**

```python
# ❌ PATCH 中的 ScopeRef 缺少 Blueprint 定义的 tenant_id
ScopeRef = {
    user_id: str,
    workspace_id: str,
    scope: str,
    agent_id: str,
    sharing_mode: str,
    # ❌ 缺少 tenant_id（RUNTIME_ARCHITECTURE.md 5.2 定义）
}
```

```python
# ❌ metering event 字段与 Blueprint 不一致
event = {
    "raw_tokens": 1000,
    "compressed_tokens": 200,
    # ❌ Blueprint 使用 input_tokens / compressed_tokens（RUNTIME_ARCHITECTURE.md 5.4）
}
```

---

# 三、检查流程

```
PATCH 文档提交
    ↓
[ G-1 检查 ] 在 Blueprint 中溯源所有新增结构
    ↓ 失败 → 禁止合入
    ↓ 通过
[ G-2 检查 ] 在 RUNTIME_ARCHITECTURE.md 查找接口映射
    ↓ 失败 → 禁止合入
    ↓ 通过
[ G-3 检查 ] 对齐 ScopeRef / Identity 字段
    ↓ 失败 → 强制对齐后重审
    ↓ 通过
→ 允许合入
```

---

# 四、溯源索引

| 要素 | Blueprint 溯源位置 |
| --- | --- |
| scope 类型 / sharing_mode | `MEMORY_SCOPE_MODEL.md` 第二/三节 |
| ScopeRef 完整字段 | `RUNTIME_ARCHITECTURE.md` 5.2 节 |
| MeteringEvent 字段 | `RUNTIME_ARCHITECTURE.md` 5.4 节 |
| Store 接口定义 | `RUNTIME_ARCHITECTURE.md` 第八节 |
| API 端点 | `RUNTIME_ARCHITECTURE.md` 第七节 |
| 默认 scope / sharing_mode | `RUNTIME_ARCHITECTURE.md` 6.3 节 |

---

# 五、违规处理

| 级别 | 情形 | 处理方式 |
| --- | --- | --- |
| **严重（BLOCKER）** | PATCH 引入 Blueprint 完全未定义的结构 | 禁止合入，要求先在 Blueprint 中补充定义 |
| **中等（MAJOR）** | ScopeRef / Identity 字段与 Blueprint 不一致 | 以 Blueprint 为准强制对齐，重审 |
| **轻微（MINOR）** | 接口命名风格略有差异但语义一致 | 记录，限期修复 |

---

# 六、决策追溯

| 依据 | 来源 |
| --- | --- |
| Blueprint 是唯一权威来源 | DECISION_LEDGER.md |
| PATCH 合法性规则 | DECISION_LEDGER.md 四.1 节 |
| Interface 溯源要求 | RUNTIME_ARCHITECTURE.md 第八节 |
