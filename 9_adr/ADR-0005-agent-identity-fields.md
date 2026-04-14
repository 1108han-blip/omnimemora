---
doc_id: ADR-0005-AGENT-IDENTITY
title: OmniMemora Agent Identity Fields Specification
owner: platform-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [ADR-0001-PRODUCT-BOUNDARY]
supersedes: []
last_verified_commit: ""
---

# ADR-0005: OmniMemora Agent Identity 字段规范

**版本：** v1.0
**状态：** Accepted
**日期：** 2026-04-14
**所有者：** OmniMemora Architecture Team

---

## 0. 设计目标

统一三件事：

1. **不破坏 runtime（memory / scope）已有 agent_id 体系**
2. **支持 adapter 层做接入识别与观测**
3. **避免"同名不同义"导致的数据污染**

---

## 1. 核心原则（必须执行）

### Principle 1：单一权威源

> **canonical_agent_id = runtime 唯一合法 agent_id**

* 只允许一个"正式 agent 身份"
* 用于：memory scope、record 归属、权限隔离、多租户治理

### Principle 2：adapter 只做映射，不做定义

> adapter 不允许发明新的"主 agent_id"

adapter 只能：解析、标准化、映射到 canonical_agent_id

### Principle 3：会话维度独立

> **session_id 永远不是 agent_id 的一部分**

* 不拼接
* 不编码进 agent_id
* 不写入 memory scope

### Principle 4：所有扩展信息都是"附属字段"

> 只有 canonical_agent_id 是主键，其它全部是 metadata

---

## 2. 标准字段定义

### AgentIdentity（Adapter 内部标准结构）

```python
class AgentIdentity(BaseModel):
    # ===== 核心字段 =====
    canonical_agent_id: str

    # ===== 输入来源 =====
    raw_agent_id: str | None = None

    # ===== 分类信息 =====
    agent_family: str | None = None
    integration_type: Literal[
        "tool_caller",
        "pre_llm_connector",
        "wrapper",
        "unknown"
    ] = "unknown"

    # ===== 会话维度 =====
    session_id: str | None = None
    workspace_id: str | None = None
    user_id: str | None = None

    # ===== 来源标记 =====
    source: Literal[
        "header",
        "query",
        "body",
        "inferred",
        "default"
    ] = "default"
```

---

## 3. 字段语义

### 3.1 canonical_agent_id（最重要）

**定义：** runtime 认可的 agent 唯一标识

**来源（优先级）：**
1. request 中明确提供（标准 header）
2. adapter mapping 规则
3. fallback 默认值（`"unknown"`）

**示例：**
```
claude_code
openclaw
codex_cli
```

### 3.2 raw_agent_id

**定义：** 外部接入传入的原始值（不可信、未标准化）

**示例：**
```
claude-code-cli-session-7
openclaw-agent-batch-test
codex-run-20260413
```

**用途：** debug、日志、映射追踪

**禁止：**
- ❌ 用于 scope
- ❌ 用于 memory record
- ❌ 用于权限

### 3.3 agent_family

**定义：** agent 类型族（用于统计/UI）

**示例：** `claude_code`, `openclaw`, `codex`

### 3.4 integration_type

**定义：** 接入方式（能力判断依据）

**枚举：** `tool_caller`, `pre_llm_connector`, `wrapper`, `unknown`

**用途：** capability registry、control_mode 决策

### 3.5 session_id

**定义：** 单次会话 / 执行上下文

**示例：** `sess_abc123`, `session-batch-test`, `run-20260413-01`

**强约束：**
- ❌ 不允许写入 memory scope
- ❌ 不参与 agent_id 计算
- ❌ 不用于权限

### 3.6 workspace_id / user_id

**用途：** 多租户隔离、项目级统计、UI 过滤

---

## 4. 映射规则

### 4.1 标准映射函数

```python
def resolve_canonical_agent_id(raw_agent_id: str | None) -> str:
```

### 4.2 映射策略

**优先级：**
```
1. 明确 header: x-agent-id → canonical
2. 映射表匹配 raw_agent_id → canonical
3. agent_family 推断
4. fallback = "unknown"
```

### 4.3 示例映射表

```python
AGENT_ID_MAPPING = {
    "claude-code-cli": "claude_code",
    "claude-code": "claude_code",
    "openclaw-agent": "openclaw",
    "codex-cli": "codex_cli",
}
```

---

## 5. 日志规范

每个请求必须包含：

```json
{
  "canonical_agent_id": "claude_code",
  "raw_agent_id": "claude-code-cli-session-7",
  "agent_family": "claude_code",
  "session_id": "sess_123",
  "integration_type": "tool_caller",
  "control_mode": "guided",
  "optimization_applied": true,
  "bypass_detected": false
}
```

---

## 6. API 输出规范

### 6.1 对外字段（保持简洁）

```json
{
  "agent_id": "claude_code",
  "session_id": "sess_123",
  "entry_rate": 0.72,
  "saved_tokens": 1820,
  "quality_delta_pct": 12.5,
  "mode": "guided"
}
```

### 6.2 不对外暴露

- ❌ raw_agent_id
- ❌ source
- ❌ mapping 细节

---

## 7. 严格禁止

### ❌ 1. session 拼进 agent_id
```
claude_code_sess_123   ← 禁止
```

### ❌ 2. raw_agent_id 直接当 canonical
```
openclaw-agent-batch-test ← 禁止直接作为 agent_id
```

### ❌ 3. adapter 改写 runtime agent_id
adapter 只能映射，不得覆盖 runtime 已定义值

### ❌ 4. observability 字段写入 memory record
禁止把 session_id、integration_type 写进 memory

---

## 8. 与 runtime 的边界

### runtime（memory / scope）
只认：`canonical_agent_id`

### adapter（observability / control）
使用：`canonical_agent_id + raw_agent_id + session_id + integration_type`

---

## 9. 落地改动清单

| 文件 | 改动 |
|------|------|
| `agent_identity.py` | 新增 `canonical_agent_id` 字段；`resolve_agent_identity()` 改为先提取 raw，再映射到 canonical |
| 所有内部逻辑 | 统一改用 `identity.canonical_agent_id` |
| API 输出 | `"agent_id": identity.canonical_agent_id` |

---

## 10. 一句话版本

> **OmniMemora 只存在一个合法 agent_id（canonical_agent_id，由 runtime 定义）；adapter 侧只做映射与补充（raw_agent_id / session_id / integration_type），不得重新定义或污染该字段。**

---

## 架构价值

这套规范一旦定住：

> **你后面接多少 agent（Claude / Codex / OpenClaw / 新框架），都不会再出现身份体系混乱的问题。**
