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

## 6️⃣ 用户端接入真相优先

- 用户端已配置的 `provider / base_url / auth / model` 是接入真相的第一来源
- 产品端必须优先透传该真相，只做最小必要兼容
- 只有在用户端未提供足够上游信息时，才允许产品端使用 fallback/default
- 产品端不得演化为持续维护外部模型生态或个性化配置的中心

---

# 五、Token Savings（核心产品能力）

## 定义

OmniMemora 必须在 UI / Console 中展示 token savings（节省 token）。

Token savings 不只意味着统计“用了多少 token”。产品必须逐步回答：

- token 花在哪；
- 为什么花；
- 哪些部分浪费；
- 如何优化；
- 开启 OmniMemora 优化后实际节省了多少。

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

## Token Intelligence（下一阶段核心价值面）

Token Intelligence 是 Token Savings 的解释层和增值层。

它必须服务于：

- 诊断 token spending；
- 识别浪费来源；
- 推荐优化动作；
- 证明优化前后的实际节省；
- 帮助用户判断 agent、prompt、memory、model、workflow 的 token/cost ROI。

允许回答的问题：

- Token 花在哪；
- 为什么花；
- 哪些 Agent 最烧钱；
- 哪些 Prompt 最低效；
- 哪些上下文重复；
- 哪些 Memory 命中失败；
- 哪些模型性价比最低；
- 哪些工作流 ROI 最高；
- 哪些优化可以由 OmniMemora structured compile 或 User Pattern Lite 执行。

硬约束：

- Token Intelligence 不得退化为普通 usage dashboard。
- Token Intelligence 不得变成用户画像、行为监控或隐藏 telemetry 产品。
- 默认不得存储 raw prompt、完整 tool output 或完整 provider response。
- 用户数据必须可查看、可删除、可过期、可导出。
- 计量结果必须标注置信度，例如 official usage、official count API、provider tokenizer、compatible estimate、rough estimate。
- 任何 recommendation 都必须连接到具体 token/cost saving 路径，否则不得作为核心产品能力推进。

---

# 六、商业能力

## Metering

- 所有 memory writes / queries 必须计量
- token savings 必须可测量

## Billing

收费基于：

> token savings + usage + governance

Token Intelligence 可作为商业能力，但收费理由必须来自：

- 可信 token/cost 审计；
- token 浪费诊断；
- optimization opportunity；
- actual savings proof。

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
→ 解释 token 花费并推动实际优化

所有功能必须直接服务于：

- token savings 或 context optimization
- token intelligence that leads to measurable token/cost saving

否则不进入产品范围。

## 🟡 补充条款4：接口边界原则

OmniMemora 只通过标准接口提供能力：

- `/memory/search`
- `/memory/write`
- product ingress and audit interfaces required for token intelligence, such as local proxy/audit APIs, when explicitly user-enabled

不扩展为 orchestration / agent runtime / tool system。

同时要求：

- 产品通过透传用户端已熟悉、已配置的协议与上游真相工作
- 协议兼容只服务于产品主链所需的最小能力：读取请求、插入 compile 结果、保持原协议返回
- 不得把协议兼容扩张成产品自己的配置中心、模型映射中心或市场适配中心

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

## 🔴 补充条款7：User Pattern Lite Boundary

OmniMemora 不做用户画像。

允许做 User Pattern Lite，但它只能用于减少重复 prompt 和提升 token saving。

允许记录：

- 用户显式表达的稳定偏好；
- 项目边界；
- 重复工作流程约束；
- 反复纠正过的错误方向；
- 能减少重复解释的短事实。

禁止记录：

- 敏感个人画像；
- 心理、健康、财务、关系、位置、消费倾向推断；
- 从 meter/proxy/trace/compile logs 静默推断出的习惯；
- 低置信度且自动注入上游的 habit 记录。

User Pattern Lite 必须用户可见、可删、可关，并且只在与当前请求相关且能减少 token 时进入 compile。
