# PRODUCT_CONSTITUTION.md

**Status:** FINAL (UNTOUCHABLE)
**Role:** 产品宪法 - 定义产品边界，所有文档必须与此一致

---

# 一、产品定义（唯一合法表达）

> OmniMemora 是 Memory Control Plane for AI Agents

## 产品愿景锚点（Vision Anchor）

> Keep it on, or things get worse.

---

# 二、核心架构原则（六条，不可违反）

## 1. Local First（本地优先）

OmniMemora 默认在本地运行，不要求云端依赖。

## 2. Cloud Optional（云端不承载主记忆）

云端仅提供可选的 Control Plane 增强能力，主记忆存储在本地 Runtime。

## 3. Default Isolated / Explicit Sharing（默认隔离，显式共享）

记忆边界默认隔离，共享必须显式配置。

## 4. Single Runtime（单本地 Runtime）

每个用户/workspace 运行单一 Local Runtime 实例。

## 5. Memory Scope Governance（基于 scope 的记忆边界治理）

OmniMemora 必须支持基于 scope 的记忆边界治理。

## 6. Control Plane / Memory Plane 分离

决策与执行必须解耦。

## 7. Minimal Exposure to LLM（最小暴露原则）

复杂性留在系统外，进入 LLM 的只保留最小必要结果。

不得向 LLM 暴露策略、候选集、评分过程、控制面元信息。

Context 是结果，不是决策过程。

### Allowed Context Definition（允许进入 LLM 的内容）
允许进入 LLM 的 context 必须满足：
- 直接用于当前任务推理或生成
- 删除后会显著影响任务正确性

不满足以上条件的内容，默认不得进入 context。

---

# 三、Scope 模型（记忆边界治理）

## Scope 类型

| Scope | 说明 | 默认行为 |
| --- | --- | --- |
| user | 用户级记忆 | 跨 workspace 隔离 |
| workspace | 项目/工作空间记忆 | 同 workspace 内共享 |
| agent | Agent 私有记忆 | 仅 agent 自身可访问 |
| custom | 自定义共享域 | 显式配置后共享 |

## Sharing Mode

| Mode | 说明 |
| --- | --- |
| isolated | 完全隔离，不可共享 |
| shared | 同 scope 内可读写共享 |
| shared_read_only | 同 scope 内仅可读 |
| custom | 按 custom_policy 规则共享 |

## 默认规则

> 默认隔离，显式共享

---

# 四、不可动摇的宪法

## 1️⃣ 不承载主记忆

- 不做 memory database
- 不做 vector DB
- 不做托管存储

## 2️⃣ Control Plane / Memory Plane 分离

- 决策与执行必须解耦

## 3️⃣ 无后端依赖成立

- 不依赖某个 memory backend 才能运行

## 4️⃣ 全部能力可替换

- engine / storage / model 可替换

## 5️⃣ 全链路可追踪

- request_id / tenant / agent / action

---

# 五、Token Savings（核心产品能力）

## 定义

OmniMemora 必须在 UI / Console 中展示 token savings（节省 token）。

## 三层职责

### Runtime 层（必须产生 metering events）

```json
{
  "event_type": "token_savings",
  "raw_tokens": 1000,
  "compressed_tokens": 200,
  "saved_tokens": 800,
  "scope": "workspace",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "timestamp": "2026-04-08T00:00:00Z"
}
```

### Control Plane 层（聚合）

- 按 user / workspace / agent / scope 聚合 token savings
- 支持多维度统计

### Console 层（展示）

必须展示：

- 总 token savings
- 今日 / 本周 / 本月
- 按 workspace breakdown
- 按 agent breakdown
- 趋势图

---

# 六、商业能力

## Metering

- 所有 memory writes / queries 必须计量
- token savings 必须可测量

## Billing

收费基于：

> token savings + usage + governance

---

# 七、非目标（必须明确）

OmniMemora 不做：

- AI Agent 本体
- 模型服务
- 数据存储平台
- 单一 memory server
- 云端承载主记忆

---

# 八、产品能力范围

## 应该做

- Scope Governance
- Policy（规则）
- Dedup / Compile
- Routing
- Metering
- Billing
- Token Savings 展示

## 不应该做

- 存储（由 Local Runtime 负责）
- 执行（由 Local Runtime 负责）
- backend 绑定

---

# 九、用户模型

用户：

- 拥有数据
- 控制 memory plane

OmniMemora：

- 控制规则
- 提供治理
- 展示 token savings

---

# 十、优先级原则

当冲突出现：

1. 架构边界 > 功能需求
2. 可治理 > 易实现
3. 可替换 > 性能优化

---

# 十一、版本治理

本文档优先级：

**Constitution > 其他所有文档**

任何与此文件冲突的文档以此文件为准。

---

# 十二、补充约束

## 🔴 补充条款1：非接管原则（最重要）

OmniMemora 不接管 Agent 的 memory ownership。

- 不替代 Agent 原生 memory
- 不作为主 memory storage
- 不要求 Agent 迁移其 memory 系统

OmniMemora 仅作为 memory augmentation layer 存在。

> 这一条是整个产品生死线

## 🔴 补充条款2：弱侵入原则

OmniMemora 必须以"可选增强组件"存在：

- Agent 可不接入 OmniMemora 正常运行
- OmniMemora 不得成为 Agent 必经路径
- 接入成本必须最小化（单 API 或轻量调用）
- 任何需要深度侵入 Agent workflow 的设计均为违规。

## 🔴 补充条款3：单能力原则（极关键）

OmniMemora 只解决一个核心问题：

→ 提升 context 质量
→ 降低 token 使用

所有功能必须直接服务于：

- token savings 或 context optimization

否则不进入产品范围。

## 🟡 补充条款4：接口边界原则

OmniMemora 只通过标准接口提供能力：

- `/memory/search`
- `/memory/write`

不扩展为 orchestration / agent runtime / tool system。

---

## 🔴 补充条款5：Context Strategy Boundary

OmniMemora 不得演化为：

- query understanding system
- retrieval pipeline（多阶段）
- orchestration layer
- adaptive learning system

Context Strategy 仅允许：
→ 对已召回结果进行选择与压缩

## 🔴 补充条款6：LLM Context Exposure Boundary

LLM 输入必须满足最小暴露：

- 仅交付最终 context 结果
- 不暴露候选集与淘汰过程
- 不暴露评分细节与策略参数
- 不暴露 control plane 内部元信息
