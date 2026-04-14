# OmniMemora Bootstrap / 安装层设计 v2

**Status:** ACTIVE
**Owner:** 春光
**Last Updated:** 2026-04-08
**依据**: Global Product Blueprint + PRODUCT_CONSTITUTION

---

# 一、核心升级（本版变更）

本版本相对于 v1，做了三项结构性修正：

1. 引入 **本地 Runtime（Memory Plane）为第一公民**
2. Bootstrap 不再依赖 API Key（支持纯本地运行）
3. 引入 **Memory Scope 模型（隔离 + 共享可控）**

---

# 二、职责边界（重要）

Bootstrap Layer **只负责**：

- runtime 下载 / 安装 / 升级
- config 生成与注入
- connector 自动注册
- 版本升级与依赖管理

Bootstrap Layer **不承担**（这些是其他层的职责）：

- ❌ metering / billing 逻辑 → 由 Control Plane 负责
- ❌ UI / Console → 由 Console 层负责
- ❌ Token Savings 聚合 → 由 Control Plane + Console 负责
- ❌ Scope 隔离逻辑执行 → 由 Runtime 负责

---

# 三、系统结构（安装层视角）

```
Connector → Local Runtime →（可选）Cloud Control Plane
```

说明：

- 所有请求默认先进入本地 Runtime
- 云端只用于：policy / metering / billing（可选）
- Bootstrap Layer 负责把 Local Runtime 装好、启动起来

---

# 四、安装器行为（Orchestrator）

## 4.1 下载阶段

用户：

- → doloclaw.com/download
- → 选择 agent（Claude / Codex / OpenClaw）
- → 下载安装包

## 4.2 安装阶段（核心）

```bash
check_env()
install_runtime()
init_runtime()
install_connector()
generate_config()
register_connector()
start_runtime()
```

## 4.3 Bootstrap Wizard（关键重构）

### 本地模式（默认）

- 初始化 runtime
- 创建 memory store
- **不需要 API Key**
- **不需要网络连接**

### 云增强模式（可选）

- 登录获取 API Key
- 启用 policy / metering
- 连接到 Cloud Control Plane

---

# 五、Memory Scope 模型

## 5.1 设计原则

> **默认隔离，显式共享**

## 5.2 Scope 类型

| Scope | 说明 |
| --- | --- |
| user | 用户级记忆 |
| workspace | 项目记忆 |
| agent | agent 私有记忆 |
| custom | 自定义共享域 |

## 5.3 行为规则

- agent 默认只访问自身 scope
- workspace scope 可跨 agent 共享
- user scope 只读共享（可选）
- custom scope 可多用户共享

---

# 六、配置结构

```json
{
  "mode": "local",
  "local": {
    "endpoint": "http://127.0.0.1:8765",
    "dataPath": "~/.omnimemora/runtime"
  },
  "cloud": {
    "enabled": false,
    "apiKey": null
  },
  "scope": {
    "default": "agent",
    "workspace": "default"
  }
}
```

---

# 七、Runtime 生命周期

## 启动

- 加载本地 memory
- 初始化 index
- 启动 localhost API

## 停止

- flush memory
- 保存 index

## 健康检查

```
GET /health → {"status": "ok", "mode": "local"}
```

---

# 八、用户体验目标（最终形态）

```
下载 → 双击 → 完成
```

- 无 Docker
- 无手动配置
- 无理解架构
- **无需 API Key（本地模式）**

---

# 九、关键原则总结

1. **本地优先（Local First）** — 默认安装本地 Runtime
2. **默认隔离（Isolated by Default）** — agent scope 默认隔离
3. **显式共享（Explicit Sharing）** — 共享必须配置
4. **云端可选（Cloud Optional）** — 云端不是必选
5. **Runtime 单一（Single Runtime）** — 一个用户一个 Runtime 实例
6. **Bootstrap 只管安装** — metering/UI/billing 由其他层负责

---

# 十、最终定义

OmniMemora =

- 本地 Memory Runtime
- Scope 治理
- 轻量 Control Plane
- Connector 接入层
- Bootstrap Layer（安装编排层）

---

**文档结束**
