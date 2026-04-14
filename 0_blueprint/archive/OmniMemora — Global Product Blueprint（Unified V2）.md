# OmniMemora — Global Product Blueprint（Unified V2）

**Status:** FINAL
**Last Updated:** 2026-04-08
**Source of Truth for:** Architecture, Scope Model, Token Savings

---

# 一、产品一句话定义（写死）

OmniMemora 是一个 **Memory Control Plane（记忆控制面）**，
用于编排、约束、计量和治理"记忆"，而不是存储记忆本身。

---

# 二、核心架构原则（六条，不可违反）

| # | 原则 | 说明 |
| --- | --- | --- |
| 1 | Local First | OmniMemora 默认在本地运行 |
| 2 | Cloud Optional | 云端仅提供可选增强，不承载主记忆 |
| 3 | Default Isolated | 记忆边界默认隔离 |
| 4 | Explicit Sharing | 共享必须显式配置 |
| 5 | Single Runtime | 每个用户/workspace 运行单一 Local Runtime |
| 6 | Scope Governance | 基于 scope 的记忆边界治理 |

---

# 三、产品宪法（不可违反）

1. 云端不承载主记忆
2. 系统必须无中心依赖可成立
3. Control Plane ≠ Memory Plane
4. 所有能力可替换
5. 全链路可追踪
6. **默认隔离，显式共享**
7. **OmniMemora 必须支持基于 scope 的记忆边界治理**

---

# 四、系统结构（六层模型）

```
┌─────────────────────────────────────────────┐
│           Bootstrap Layer（安装编排层）       │
│  负责：runtime 初始化、config 注入、connector │
│  自动配置、版本升级                          │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Client → Connector → Control Plane → Memory Plane → Storage │
└─────────────────────────────────────────────┘
```

说明：

- **Local Runtime** 是 Memory Plane 的默认实现形态
- **Bootstrap Layer** 是安装和生命周期管理的入口
- **Cloud Control Plane** 为可选增强，不影响本地独立运行

## 4.1 Connector Layer（连接器协议层）

**Connector Layer 支持多种访问协议：MCP、HTTP、Plugin，以及未来基于 SDK 的集成。**

| 协议 | 地位 | 说明 |
| --- | --- | --- |
| **MCP（Model Context Protocol）** | **一等公民（First-Class）** | 官方首选集成协议，不是一次性的 Claude Code 适配 |
| HTTP | 一等公民 | 通用 REST 协议，Codex 等客户端使用 |
| Plugin | 一等公民 | OpenClaw 等插件系统集成 |
| SDK-based | Future | 未来基于 SDK 的深度集成 |

**关键声明：**

> MCP 是 OmniMemora 的一等公民连接协议，不是针对 Claude Code 的临时适配。所有协议均通过统一的 Connector Layer 接入，享有相同的 scope enforcement 和 metering 能力。

---

# 五、Scope 模型（记忆边界治理）

## Scope 类型

| Scope | 说明 | 默认行为 |
| --- | --- | --- |
| user | 用户级记忆 | 跨 workspace 隔离，仅自身可写 |
| workspace | 项目/工作空间记忆 | 同 workspace 内共享读写 |
| agent | Agent 私有记忆 | 仅 agent 自身可读写 |
| custom | 自定义共享域 | 显式配置后共享 |

## Sharing Mode

| Mode | 说明 |
| --- | --- |
| isolated | 完全隔离，不可共享 |
| shared | 同 scope 内可读写共享 |
| shared_read_only | 同 scope 内仅可读 |
| custom | 按 custom_policy 规则共享 |

## 核心原则

> **默认隔离，显式共享**

---

# 六、Token Savings（三层职责）

Token Savings 是核心产品能力，必须在三层全部落地。

## 6.1 Runtime 层（必须产生 metering events）

```json
{
  "event_type": "memory_write",
  "request_id": "req_xxxxx",
  "raw_tokens": 1000,
  "compressed_tokens": 200,
  "saved_tokens": 800,
  "scope": "workspace",
  "workspace_id": "proj_alpha",
  "agent_id": "claude_code",
  "user_id": "u_001",
  "timestamp": "2026-04-08T00:00:00Z"
}
```

## 6.2 Control Plane 层（聚合）

- 按 user / workspace / agent / scope 聚合 token savings
- 支持多维度统计查询

## 6.3 Console 层（展示）

必须展示：

- 总 token savings
- 今日 / 本周 / 本月
- 按 workspace breakdown
- 按 agent breakdown
- 趋势图

---

# 七、Control Plane（核心模块）

- Identity（tenant / workspace / agent）
- Auth（API key / scope）
- Policy Engine（写入/压缩/去重）
- Routing（memory 去向）
- Metering（token_savings 聚合）
- Billing（plan / quota）

---

# 八、数据流

## Write

```
Client → Connector → Control Plane → Policy Engine → Routing → Local Runtime → Storage
                                    ↓
                              Metering Event
```

## Query

```
Client → Connector → Control Plane → Routing → Local Runtime → Policy Engine → Return
                                    ↓
                              Metering Event
```

---

# 九、产品边界

### ✅ 做

- Scope Governance（记忆边界治理）
- Policy（规则）
- Routing（路由）
- Metering（计量 + token savings 聚合）
- Billing（计费）
- Token Savings 展示

### ❌ 不做

- memory hosting（由 Local Runtime 负责）
- 强绑定 backend
- 云端承载主记忆

---

# 十、Console（产品核心界面）

## Dashboard

| 模块 | 内容 |
| --- | --- |
| Overview | **Token Savings 总览**、今日/本周/本月、趋势图 |
| Usage | memory writes、queries、token 统计 |
| Workspace | workspace 列表、scope 配置 |
| Agents | agent 列表、scope 归属 |
| Policies | 压缩/去重/保留规则 |
| Connectors | connector 注册状态 |
| Billing | 计划、额度、用量 |
| Settings | scope 配置、API Keys |
| Audit Logs | 操作审计 |

---

# 十一、User Journey（两条路径）

### 本地优先模式（默认）

```
下载 → 双击安装 → 完成（无需 API Key）→ 运行 agent → 看到 token savings → 付费
```

### 云增强模式（可选）

```
访问官网 → 注册 → 创建 API Key → 安装 Connector → 5分钟接入 → 看到 token savings → 形成习惯 → 付费
```

---

# 十二、商业模型

卖的不是存储，而是：

> **token savings + 控制能力**

### 定价结构

- Starter（免费）
- Pro（月费+额度）
- Enterprise（治理能力）

### 计费指标

- memory writes
- memory queries
- **token savings**
- active agents

---

# 十三、GTM（增长路径）

阶段1：Claude / Codex 用户
阶段2：Agent / MCP
阶段3：企业系统

---

# 十四、产品飞轮

```
用户 → usage → policy优化 → savings提升 → 价值增强 → 收费 → 更多用户
```

---

# 十五、设计原则

1. Local First / Cloud Optional
2. 控制 vs 执行 必须分离
3. 默认可替换
4. 默认多租户
5. 所有行为可计量
6. **默认隔离，显式共享**

---

# 十六、最终抽象

OmniMemora =

- **本地 Memory Runtime**（Memory Plane 默认实现）
- **Scope 治理**
- **Memory Control Plane**
- Policy Engine
- Routing
- Metering + Billing
- **Bootstrap Layer**（安装编排层）

---

# 十七、唯一判断标准

如果一个功能：

- ❌ 在存数据 → **不做**
- ✅ 在控制规则 → **做**
- ❌ 增加 backend 依赖 → **不做**
- ❌ 削弱 token savings 展示 → **不做**

---

# 十八、禁止残留（旧架构）

以下旧架构模式**严禁出现**在任何文档或实现中：

- ❌ connector 直连云端 memory backend
- ❌ 云端作为主记忆存储
- ❌ API key 作为前置条件
- ❌ 本地 Runtime 作为可选附件

---

# 十九、版本治理

本文档优先级：

**Blueprint > Constitution > Execution Plan > 其他文档**

任何与此文件冲突的文档以此文件为准。
