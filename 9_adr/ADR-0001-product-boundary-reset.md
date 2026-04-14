---
doc_id: ADR-0001-PRODUCT-BOUNDARY
title: OmniMemora Product Boundary Reset
owner: product-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-07
depends_on: []
supersedes: []
last_verified_commit: ""
---

本文档为 OmniMemora 从"memory system"向"control plane"转型前的最终旧口径定义


# 8.51 OmniMemora 产品结构重定义架构文稿

**文档版本**: v1.0
**日期**: 2026-04-07
**状态**: 本文档为 OmniMemora 从"memory system"向"control plane"转型前的最终旧口径定义

---
| 本文内容          | Blueprint 对应    |
| ------------- | --------------- |
| 三条边界线         | 产品宪法(第三章)       |
| connector 是入口 | Connector Layer |
| 云端是核心         | ❌(需要修正)         |
| 用户路径          | User Journey    |
| 三类用户          | Client Layer    |


## 一、核心结论(必读)

本文档正式确立 OmniMemora 的产品边界,消除过去文档中"本地 vs 云"、"谁是产品"、"API 是否等于一切"等口径混淆。

### 三条不可动摇的边界线

1. **本地 Docker 栈(端口 18011/1933 等)= 开发/测试/内部验证环境,非商业交付物**
2. **云端 OmniMemora 服务(api.doloclaw.com)= 商业核心,用户不直接访问内部栈**
3. **Claude Code、Codex、OpenClaw = 三个独立真实用户,非产品内部组件**

---

## 二、产品分层架构(正式版)

### 2.1 分层总览

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4: 用户可见层                                     │
│  GitHub releases / doloclaw.com 下载页                   │
│  轻量级 connector / skill / plugin 安装包               │
│  说明书 + API key 引导                                   │
├─────────────────────────────────────────────────────────┤
│  Layer 3: 客户端组件层(可下载)                         │
│  omni-connector / omni-skill / omni-plugin              │
│  负责:本地记忆缓存、API 路由、认证透传、本地打包        │
│  ⚠️ 即使是开源/免费层,客户端 connector 仍需下载安装      │
├─────────────────────────────────────────────────────────┤
│  Layer 2: 云端商业核心(用户通过 API 访问)              │
│  api.doloclaw.com / cloud hosted OmniMemora             │
│  负责:记忆存储、recall 编排、token savings 计量、       │
│  多租户隔离、usage 聚合、策略执行                        │
├─────────────────────────────────────────────────────────┤
│  Layer 1: 开发/测试基线                                  │
│  本地 Docker: adapter:18011 / openviking-server:1933     │
│  用途:内部开发验证、CI/CD 测试、团队自用                 │
│  ⚠️ 用户不需要、也不应该访问这一层                        │
└─────────────────────────────────────────────────────────┘
```

### 2.2 为什么"API does everything"这句话是不准确的

常见误解:既然核心价值在云端 API,那用户就不需要下载任何东西,直接调 API 就行。

**这个说法在技术上可行,但在产品体验上不完整,原因如下:**

1. **客户端仍需 connector 组件**:即使 API 在云端,用户需要一个轻量级本地程序来:
   - 管理 API key 和认证
   - 做本地记忆缓存(减少不必要的远程往返)
   - 做 context packing 的本地预处理
   - 在网络不稳定时提供降级体验
   - 适配不同终端(Claude Code / Codex / OpenClaw / 未来更多)

2. **"API does everything"仅对极客用户成立**:一个普通用户(用 Claude Code 或 OpenClaw 的开发者)不可能每次任务前手动调 curl,他们需要一个安装即用的 connector。

3. **connector 是入口,不是核心**:connector 的价值不在于"自己完成记忆管理",而在于"把用户连接到正确的云端服务"。核心记忆编排逻辑留在云端。

**结论**:
> OmniMemora 的商业价值在云端 API,但用户接触产品的界面是一个轻量级下载包(connector/skill/plugin)。
> 这不是把"核心价值下放",而是"把接入体验做轻"。

---

## 三、用户视角:OmniMemora 的真实使用路径

### 3.1 目标用户第一步(不是注册账号,而是下载 connector)

```
用户访问 doloclaw.com 或 GitHub
         │
         ▼
下载 omni-connector-v1.x(如:omni-codex-skill-v1.zip)
         │
         ▼
解压 → 配置 api.doloclaw.com endpoint + API key
         │
         ▼
连接成功,开始使用
```

**注意**:用户下载的不是"OpenViking 源码",也不是"完整 Docker 栈"。他们下载的是一个经过封装的、针对其使用场景(Claude Code / Codex / OpenClaw)的轻量 connector。

### 3.2 三类用户的下载包可能不同

| 用户 | 下载包 | 形态 | 说明 |
|------|--------|------|------|
| Claude Code 用户 | `omni-claude-code-skill` | Skill / 脚本包 | 针对 Claude Code CLI 的 hooks 和 wrapper |
| Codex 用户 | `omni-codex-connector` | Plugin / 扩展 | 针对 Codex IDE 插件形态 |
| OpenClaw 用户 | `omni-openclaw-plugin` | 现有 plugin 增强版 | 复用现有 memory-openviking 改造 |
| 通用开发者 | `omni-generic-connector` | 标准 SDK / CLI | 无特定终端偏好时的通用入口 |

---

## 四、Claude Code、Codex、OpenClaw 的真实身份

### 4.1 它们不是产品组件,而是第一批真实用户

**这是 OmniMemora 历史上最重要的身份澄清之一。**

过去文档中有时会把这三个工具描述为"产品模块"或"内部集成方式",这种写法是不准确的。

**正确理解**:
- Claude Code = OmniMemora 的第一个真实付费/试用用户(使用 Claude Code Skill connector)
- Codex = OmniMemora 的第二个真实用户(使用 Codex Plugin connector)
- OpenClaw = OmniMemora 的第三个真实用户(使用 OpenClaw Plugin connector)

它们不是 OmniMemora 的"内部组件",而是有各自独立需求的外部用户。

### 4.2 三个用户的三套独立 Identity

每个用户拥有完全独立的 API Identity:

```
Claude Code 用户身份:
  tenant:    omni-tenant-claude-code
  user:      cc-{session_id}
  agent:     claude-code-cli
  client:    omni-claude-code-skill
  API key:   独立 key
  Token Savings: 独立计量(tenant-level + agent-level)

Codex 用户身份:
  tenant:    omni-tenant-codex
  user:      cx-{workspace_id}
  agent:     codex-agent
  client:    omni-codex-plugin
  API key:   独立 key
  Token Savings: 独立计量

OpenClaw 用户身份:
  tenant:    omni-tenant-openclaw
  user:      oc-{user_id}
  agent:     openclaw-agent
  client:    memory-openviking
  API key:   独立 key
  Token Savings: 独立计量
```

### 4.3 三者不是竞争关系,而是覆盖关系

- Claude Code → 覆盖命令行 AI CLI 市场
- Codex → 覆盖 IDE AI 辅助编程市场
- OpenClaw → 覆盖 AI 终端工具市场

三者共同扩大 OmniMemora 的可触达市场,而不是互相蚕食。

---

## 五、商业模式(正式版)

### 5.1 产品定位

**OmniMemora = Agent Memory Orchestration as a Service**

不是"记忆数据库",不是"OpenViking 增强版",而是:
> 帮助 AI Agent 在正确时间用正确记忆,同时节省 token 的记忆编排托管服务。

### 5.2 商业模式画布

| 层级 | 内容 | 说明 |
|------|------|------|
| **主商品** | Agent Memory API / SaaS | 按调用量或订阅收费 |
| **用户入口** | 轻量 connector 下载 | 免费/低成本,降低使用门槛 |
| **辅线** | 企业私有部署 | 高客单价,按需报价 |
| **辅线** | 定制 connector 开发 | 针对特定终端的深度集成 |
| **已下线** | 源码下载付费 | 不再作为主商业模型 |
| **已下线** | Docker 安装包本体售卖 | 用户自建不在此口径下 |

### 5.3 为什么 connector 免费/低价也能成立

因为:

1. **核心价值在云端**:用户拿走 connector,没有云端 API key,就无法实际使用记忆服务
2. **Token Savings Meter 是转化点**:用户看到自己每月节省了多少 token,就会愿意为云端服务付费
3. **网络效应**:覆盖越多终端(Claude Code / Codex / OpenClaw),平台数据越多,越难被替代

---

## 六、实现顺序建议(下一步落地路线图)

### Phase 0(已完成): 产品结构澄清
- [x] 区分本地 dev stack 与云端 commercial core
- [x] 明确 Claude Code / Codex / OpenClaw 为三个独立用户
- [x] 确认 connector 需要单独下载(不等于"API does everything")
- [x] 确立 Token Savings Meter 为核心商业可视化指标

### Phase 1(下一步): Cloud SaaS 商业化落地
**优先级:最高**

目标:把现有本地 Docker stack 正式转化为对外可用的云端 SaaS。

具体任务:
1. 将 `adapter:18011` / `openviking-server:1933` 的能力映射到 `api.doloclaw.com`
2. 实现 `/memory/query` 统一入口(带 token savings meter)
3. 实现 `/usage/token-savings` 及趋势 API
4. 配置 API key 认证体系
5. 配置 tenant plan / quota 基本模型

验收标准:
- 外部用户可通过 connector 访问 `api.doloclaw.com` 并完成完整 write/query/read 链路
- Token Savings Meter 在每个请求中可观测

### Phase 2: Connector 产品化
**优先级:高**

目标:把 connector 从"内部工具"变成"可发布产品"。

具体任务:
1. 拆分 `omni-claude-code-skill` 并发布到 GitHub releases
2. 拆分 `omni-codex-connector` 并发布
3. 改造现有 OpenClaw plugin 为 `omni-openclaw-plugin`
4. 统一 connector 的 API key 引导流程
5. 在 doloclaw.com 添加 connector 下载页面

验收标准:
- 用户可在 doloclaw.com 或 GitHub 下载对应 connector
- 下载后 5 分钟内完成 API 连接配置并可用

### Phase 3: 商业计费与增长
**优先级:中**

目标:把 usage 变成 revenue。

具体任务:
1. 实现 Stripe billing 与 subscription 绑定
2. 把 Token Savings Meter 做成用户控制台(app.doloclaw.com)的核心展示
3. 实现 per-tenant usage quota 强制
4. 实现 trial → paid 转化路径
5. 实现 enterprise contact flow

---

## 七、架构决策记录(ADR)

### ADR-8.51-001: 本地 Docker 栈不是商业交付物

**决策**:将本地 Docker 环境(adapter:18011 / openviking-server:1933)明确标注为"开发/测试/内部验证"环境,不作为商业交付物向用户推荐。

**理由**:
- 用户应通过云端 API 访问服务
- 降低用户使用门槛(不需要懂 Docker)
- 避免本地部署带来的维护负担和版本碎片问题
- 商业价值集中在云端编排层

**例外**:企业客户如需私有部署,走 Phase 3 企业辅线,不在此常规路径内。

### ADR-8.51-002: Claude Code / Codex / OpenClaw 是用户,不是组件

**决策**:在所有产品文档、口径、README 中,将 Claude Code、Codex、OpenClaw 描述为"第一批真实用户/接入案例",而非"产品内部模块"。

**理由**:
- 避免产品边界模糊
- 避免把"接入适配成本"算作"产品价值"
- 便于向投资人/客户解释:OmniMemora 不附属于任何单一 AI 工具
- 为接入更多终端(Cursor / Copilot / 其他)留出空间

### ADR-8.51-004: OmniMemora 多接入接口架构原则(已修订 2026-04-13)

**决策**:OmniMemora 提供多种接入接口(MCP / CLI / REST / Wrapper),但产品路径唯一--所有接口统一从 Python Adapter(:18011)接入。

**接口定位:**

| 接口 | 协议 | 入口端口 | 角色 |
|------|------|---------|------|
| MCP | SSE + JSON-RPC | :18011 | 通用 Agent 生态标准接入面 |
| CLI | HTTP REST | :18011 | 本地优先,低延迟 |
| REST | HTTP JSON | :18011 | 工具链 / CI/CD / 编排系统 |
| Wrapper | subprocess | :18011 | 策略验证与实验 |

**端口约定:**
- **:18011** = 统一产品入口(Python Adapter),承载 Context Compiler + Token Savings + Metering
- **:8765** = Local Memory Plane(Go Runtime),仅提供存储/检索,**非产品入口**

**核心原则**:多接口,单路径。协议可替换,核心路径不分裂。

**溯源**:`9_adr/ADR-0003-interface-access-paths.md`(已同步修订)

### ADR-8.51-003: "API does everything"是不完整描述

**决策**:产品叙事中不使用"API does everything"作为 OmniMemora 的核心描述。正确的描述是:

> 用户下载轻量级 connector,通过 connector 与云端 OmniMemora API 交互,核心记忆编排逻辑在云端执行。

**理由**:
- 实际用户体验需要 connector 层
- 过度简化会误导用户期望
- connector 是产品入口而非核心价值,但入口体验决定转化率

---

## 八、口径对照表(旧 vs 新)

| 场景 | 旧口径(错误/模糊) | 新口径(正确) |
|------|-------------------|----------------|
| 本地 Docker 是什么 | "产品运行环境" / "主栈" | "开发/测试/内部验证环境" |
| 用户如何访问服务 | "自己部署 Docker" | "下载 connector,连接 api.doloclaw.com" |
| Claude Code 是什么 | "产品集成方式" / "内部模块" | "第一个真实用户" |
| Codex 是什么 | "内部开发工具" | "第二个真实用户" |
| OpenClaw 是什么 | "产品展示窗口" | "第三个真实用户" |
| API 是什么 | "API does everything" | "云端商业核心 + connector 入口" |
| 核心价值在哪里 | "在本地记忆系统" | "在云端记忆编排服务" |

---

## 九、文档状态

- 本文档由 Claude Code 基于任务包 S1 执行生成
- 替代:所有将本地 Docker 栈描述为商业交付物的口径
- 补充:8.2(商业目标重定义)和 8.4(API 契约与 Token Savings Meter 定义)中的产品边界描述
- 与 8.49(公网 API 平面检查)互补:8.49 说明技术暴露路径,本文档说明产品逻辑边界

---

**文档结束**
