# OmniMemora — Execution Plan（Local-First V1）

**Status:** ACTIVE
**依据**: Global Product Blueprint + PRODUCT_CONSTITUTION
**Last Updated**: 2026-04-08

---

# 核心变更说明

旧方案以"云端 deployment"为起点，导致架构绕回了云中心模式。

新方案以"本地 Runtime"为起点，所有云端能力均为可选增强。

---

# Phase 0：本地 Runtime 最小可运行版

## 目标

验证本地 Runtime 可以独立运行，无需 API Key、无需云端依赖。

## 任务清单

### 0.1 Runtime 核心实现

- 实现本地 memory store（文件或 SQLite）
- 实现 `/health` 端点
- 实现 `/memory/write` 和 `/memory/query` 端点
- 实现 scope 注入（user / workspace / agent / custom）

### 0.2 Config Schema

```json
{
  "mode": "local",
  "local": {
    "endpoint": "http://127.0.0.1:8765",
    "dataPath": "~/.omnimemora/runtime"
  },
  "scope": {
    "default": "agent",
    "workspace": "default"
  }
}
```

### 0.3 Runtime Metering Events（必须实现）

Runtime 层必须产生以下 metering events：

```json
{
  "event_type": "token_savings",
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

### 0.4 验证标准

- `curl http://127.0.0.1:8765/health` 返回 `{"status": "ok"}`
- 写入一条 memory 并能查询回来
- 不依赖任何外部 API key
- metering event 正确产生

---

# Phase 1：Bootstrap Layer / 安装层

## 目标

实现安装编排器，用户下载后双击即可完成安装，无需理解架构。

## 职责边界（重要）

Bootstrap Layer **只负责**：

- runtime 下载/安装/升级
- config 生成
- connector 自动注册
- 版本升级

Bootstrap Layer **不承担**：

- metering / billing 逻辑
- UI / Console 逻辑
- policy engine 逻辑

## 任务清单

### 1.1 Bootstrap Orchestrator

```bash
check_env()
install_runtime()
init_runtime()
install_connector()
generate_config()
register_connector()
start_runtime()
```

### 1.2 Bootstrap Wizard

两种模式可选：

**本地模式（默认）**

- 无需 API Key
- 不连接云端
- 即装即用

**云增强模式**

- 登录获取 API Key
- 启用 policy / metering / billing

### 1.3 验证标准

- 用户下载 → 双击 → Runtime 启动 → Connector 连上
- 全程无需打开终端或配置文件
- API Key 不是安装前提

---

# Phase 2：Connector 接本地 Runtime + Scope 落地

## 目标

所有 Connector 默认连接到本地 Runtime，云端为可选。Scope 模型完整落地。

## 任务清单

### 2.1 Connector 默认行为

```
connector → local runtime (http://127.0.0.1:8765)
```

### 2.2 Connector 注册

- Connector 启动时向本地 Runtime 注册
- 注册内容：agent_id、connector_type、scope
- Runtime 维护活跃 Connector 列表

### 2.3 支持的 Connector

- Claude Code MCP Server
- OpenClaw Plugin
- Codex HTTP Client

### 2.4 Scope Enforcement（必须完整实现）

| 操作 | agent scope | workspace scope | user scope | custom scope |
| --- | --- | --- | --- | --- |
| 读取 | 仅自身 | 同 workspace | 同 user | 显式共享 |
| 写入 | 仅自身 | 同 workspace | 同 user | 显式共享 |
| 共享 | 不可 | 可配置 | 可配置 | 显式配置 |

### 2.5 验证标准

- Claude Code 通过 connector 写入 memory 到本地 Runtime
- 同一 workspace 的多个 agent 可以共享 memory
- 不同 agent 默认隔离
- Scope 配置正确执行

---

# Phase 3：Token Savings UI 上线

## 目标

Console 必须完整展示 Token Savings，这是核心产品价值。

## 任务清单

### 3.1 Control Plane 层（聚合）

实现 token savings 聚合接口：

- 按 user / workspace / agent / scope 聚合
- 支持多维度统计查询

### 3.2 Console UI（必须展示）

| 模块 | 内容 |
| --- | --- |
| Overview | Token Savings 总览、今日/本周/本月、趋势图 |
| Workspace | 各 workspace 的 token savings breakdown |
| Agent | 各 agent 的 token savings breakdown |

### 3.3 验证标准

- 总 token savings 正确显示
- 今日 / 本周 / 本月 可切换
- 按 workspace breakdown 可查看
- 按 agent breakdown 可查看
- 趋势图展示历史数据

---

# Phase 4：Metering → Billing 闭环

## 目标

Metering → Billing 闭环成立，支持 Pro / Enterprise 商业模式。

## 任务清单

### 4.1 Billing 体系

- Starter（免费）
- Pro（月费+额度）
- Enterprise（治理能力）

### 4.2 验证标准

- token savings 可计费
- usage 可观测
- billing plan 可切换

---

# Phase 5：Cloud Control 增强能力（可选）

## 目标

云端 Control Plane 作为本地 Runtime 的可选增强，不影响本地独立运行。

## 任务清单

### 5.1 本地 + 云端组合

```
Connector → Local Runtime →（可选）Cloud Control Plane
```

### 5.2 云端能力

- Policy Engine（云端）
- Metering（云端聚合）
- Billing（云端）
- 跨 workspace 审计

### 5.3 API Key 体系

- 本地模式：无需 API Key
- 云增强模式：登录获取 API Key
- API Key 用于：cloud control plane 身份验证

### 5.4 验证标准

- 本地 Runtime 独立运行（无网络）时，所有 Phase 0-3 功能正常
- 接入云端后，metering / billing 功能可用

---

# 执行顺序

```
Phase 0: 本地 Runtime 最小可运行版（含 metering events）
  ↓
Phase 1: Bootstrap Layer / 安装层
  ↓
Phase 2: Connector 接本地 Runtime + Scope 落地
  ↓
Phase 3: Token Savings UI 上线
  ↓
Phase 4: Metering → Billing 闭环
  ↓
Phase 5: Cloud Control 增强能力（可选）
```

---

# 与旧方案的对比

| | 旧方案（云优先） | 新方案（本地优先） |
| --- | --- | --- |
| 起点 | Cloudflare Pages + Railway | 本地 Runtime |
| API Key | 前置条件 | 可选 |
| 主记忆位置 | 云端 | 本地 |
| 云端定位 | 必选 | 可选增强 |
| Token Savings | 弱化 | 核心产品能力 |
| 架构 | 云中心 | 本地优先 |

---

# 版本治理

本文档优先级：

Blueprint > Constitution > Execution Plan > 其他文档
