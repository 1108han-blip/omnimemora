# CLOUD_CURRENT_STATE.md

**Status:** ACTIVE
**Purpose:** OmniMemora 云端现状快照，作为 Local First 架构的对齐参考
**Last Updated:** 2026-04-08
**依据**: DECISION_LEDGER + Local First Architecture

---

# 一、云端组件清单

## 1.1 Cloudflare Pages

| 属性 | 值 |
| --- | --- |
| 域名 | doloclaw.com |
| 项目名 | openviking-site |
| 平台 | Cloudflare Pages |
| D1 Database | omnimemora-leads |
| D1 Binding | LEADS_DB |

**技术配置** (`6_console/ui-prototype/wrangler.jsonc`):

```json
{
  "name": "openviking-site",
  "compatibility_date": "2026-04-06",
  "pages_build_output_dir": ".",
  "d1_databases": [{
    "binding": "LEADS_DB",
    "database_name": "omnimemora-leads",
    "database_id": "e7481f9d-a1f2-482c-90e6-d56949bd42e2"
  }],
  "vars": {
    "ADAPTER_API_URL": "https://omnimemora-adapter-production.up.railway.app",
    "INTERNAL_ADAPTER_TOKEN": "a523334ef0efc056c5b163f88b952e3d85958761f04642d81996fbae6d785cd0"
  }
}
```

---

## 1.2 Railway Adapter

| 属性 | 值 |
| --- | --- |
| URL | https://omnimemora-adapter-production.up.railway.app |
| 仓库 | github.com/1108han-blip/omnimemora-adapter-prod |
| 当前版本 | Memory Adapter v2.2.0 |
| 环境 | Production |

**现状问题**: 该服务当前角色是 Memory Adapter，但依赖一个不存在的 backend（VIKING_URL 指向 `http://host.docker.internal:1933`，本地开发地址，云端不存在）。

---

## 1.3 GitHub Releases

| 仓库 | 用途 | 状态 |
| --- | --- | --- |
| omnimemora-core | Public A+C (MCP server + tool interface docs) | 活跃 |
| omnimemora-adapter-prod | FastAPI commercial adapter production | 活跃 |
| omnimemora-cloud-console | Cloudflare Pages 控制台（待确认） | 需重构 |

**Release 产物**:
- doloclaw.com 下载页面
- Connector 安装包: `omni-claude-code-skill`, `omni-codex-connector`, `omni-openclaw-plugin`

---

## 1.4 D1 Database

| Database ID | 名称 | 用途 |
| --- | --- | --- |
| e7481f9d-a1f2-482c-90e6-d56949bd42e2 | omnimemora-leads | 租户注册、账单、leads |

**Schema 包含**:

```sql
billing_subscriptions    -- Stripe 订阅记录
billing_customers        -- Stripe 客户记录
billing_events           -- Stripe webhook 事件日志（append-only）
tenant_registry          -- 租户注册表
private_leads            -- Lead 捕获
```

---

## 1.5 Stripe 集成

| 属性 | 值 |
| --- | --- |
| API Version | 2024-11-20.acacia |
| Starter Plan | $29/month (STARTER_MONTHLY_PRICE_ID) |
| Pro Plan | $99/month (PRO_MONTHLY_PRICE_ID) |

**Webhook 处理事件**:
- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_failed`

---

# 二、各组件当前职责

## 2.1 Cloudflare Pages 当前职责

| 类别 | 接口 | 说明 | Control Plane 归属 |
| --- | --- | --- | --- |
| **Auth/Identity** | | | |
| | `GET/POST/PATCH /api/tenants` | 租户注册 CRUD | ✅ Control Plane |
| | `GET /api/admin/tenants` | Admin 租户管理 | ✅ Control Plane |
| | `POST /api/internal/tenants` | 内部租户同步 | ✅ Control Plane |
| **Billing** | | | |
| | `GET /api/billing/plans` | 套餐映射 | ✅ Control Plane |
| | `POST /api/billing/checkout-session` | Stripe Checkout | ✅ Control Plane |
| | `POST /api/billing/portal-session` | Stripe Portal | ✅ Control Plane |
| | `POST /api/billing/webhook` | Stripe Webhook | ✅ Control Plane |
| **Trial** | | | |
| | `POST /api/trial/query` | Trial 查询代理 | ✅ Control Plane |
| **Contact/Leads** | | | |
| | `POST /api/contact` | Lead 捕获 + 自动开通 trial | ✅ Control Plane |
| | `GET/PATCH /api/leads` | Lead 管理 | ✅ Control Plane |
| | `GET /api/leads/summary` | Lead 统计 | ✅ Control Plane |
| **Memory Proxy（遗留）** | | | |
| | `POST /api/memory/write` | 代理到 Railway | ❌ 旧架构残留 |
| | `POST /api/memory/search` | 代理到 Railway | ❌ 旧架构残留 |

**结论**: Cloudflare Pages 80% 的接口已经是正确的 Control Plane 职责。

---

## 2.2 Railway Adapter 当前职责

| 接口 | 说明 | Control Plane 归属 |
| --- | --- | --- |
| `/health` | 健康检查 | ✅ 可保留 |
| `/memory/write` | 写记忆 | ❌ 旧 Memory Plane 职责（依赖不存在 backend） |
| `/memory/search` | 搜索记忆 | ❌ 旧 Memory Plane 职责（依赖不存在 backend） |
| `/memory/read` | 读记忆 | ❌ 旧 Memory Plane 职责（依赖不存在 backend） |
| `/memory/delete` | 删除记忆 | ❌ 旧 Memory Plane 职责（依赖不存在 backend） |
| `/memory/snapshot` | 生成 MEMORY.md | ❌ 旧 Memory Plane 职责 |
| `/memory/query` | V2 统一查询（含 token savings metering） | ⚠️ 核心 metering 已实现，但 Railway 角色错误 |
| `/usage/token-savings` | Token savings 统计 | ✅ Control Plane |
| `/usage/token-savings/trend` | Token savings 趋势 | ✅ Control Plane |
| `/internal/trial-query` | Trial 查询 | ✅ Control Plane（Cloudflare 代理） |
| `/api/admin/trials/provision` | Trial 开通 | ✅ Control Plane |
| `/support/error-codes` | 错误码查询 | ✅ 可保留 |
| `/requests/{request_id}/meter` | 请求 metering | ✅ Control Plane |

**关键问题**: Railway 当前将 Memory Plane 职责（`/memory/*`）与 Control Plane 职责混合在一起，且 Memory Plane 依赖的 backend 不存在。

---

## 2.3 OpenClaw Plugin 当前职责

| 属性 | 值 |
| --- | --- |
| 插件 ID | memory-openviking |
| 接入 URL | http://127.0.0.1:18011（本地 Adapter）→ OmniMemora Runtime:8765 |
| 当前指向 | Railway Adapter |

**工具接口**:
- `memory_recall` - 召回记忆
- `memory_store` - 存储记忆
- `memory_forget` - 删除记忆

**问题**: 插件 `baseUrl` 配置为 `http://memory-adapter:8000`（旧地址），当前本地 Adapter 已迁移至 `http://127.0.0.1:18011`，Runtime 位于 `8765`。

---

# 三、当前已有 API / 页面 / 功能

## 3.1 Auth / Identity

| 功能 | 现状 | 架构对齐 |
| --- | --- | --- |
| 租户注册 | ✅ 完整 | ✅ 正确 |
| API Key 管理 | ❌ 缺失（需新增 key create/revoke） | ❌ 待补充 |
| Token/Identity | ⚠️ tenant_registry 有 token_id 字段但未完整实现 | ❌ 待补充 |

## 3.2 Metering

| 功能 | 现状 | 架构对齐 |
| --- | --- | --- |
| Token Savings 产生 | ⚠️ Railway `/memory/query` 内已实现 metering | ✅ 基本正确 |
| Token Savings 聚合 | ⚠️ `/usage/token-savings` 存在但需验证 | ⚠️ 需对标新架构 |
| Token Savings 展示 | ❌ Console UI 未实现 | ❌ 缺失（Phase 3） |

## 3.3 Billing

| 功能 | 现状 | 架构对齐 |
| --- | --- | --- |
| Plans 展示 | ✅ `/api/billing/plans` | ✅ 正确 |
| Checkout | ✅ Stripe Checkout | ✅ 正确 |
| Portal | ✅ Stripe Portal | ✅ 正确 |
| Webhook | ✅ 完整 | ✅ 正确 |
| Usage-based 计费 | ❌ 未实现（Starter/Pro 固定价格） | ⚠️ 需扩展 |

## 3.4 Trial

| 功能 | 现状 | 架构对齐 |
| --- | --- | --- |
| Trial 开通 | ✅ `/api/admin/trials/provision` | ✅ 正确 |
| Trial 查询 | ✅ `/api/trial/query` | ✅ 正确 |
| Trial Quota | ✅ `OMNIMEMORA_TRIAL_QUOTA_TOKENS=500000` | ✅ 正确 |

## 3.5 Console

| 功能 | 现状 | 架构对齐 |
| --- | --- | --- |
| Admin Tenants | ✅ `/api/admin/tenants` | ✅ 正确 |
| Leads 管理 | ✅ `/api/leads` | ✅ 正确 |
| Token Savings 展示 | ❌ 未实现 | ❌ Phase 3 任务 |
| Workspace Breakdown | ❌ 未实现 | ❌ Phase 3 任务 |
| Agent Breakdown | ❌ 未实现 | ❌ Phase 3 任务 |

## 3.6 Connector Download

| 功能 | 现状 | 架构对齐 |
| --- | --- | --- |
| 下载页面 | ⚠️ doloclaw.com/download | ⚠️ 需确认 |
| GitHub Releases | ✅ 存在 | ✅ 可保留 |

---

# 四、当前与新架构的冲突点

## 4.1 云中心思维残留

| 冲突项 | 旧思维 | 新架构要求 |
| --- | --- | --- |
| Railway 角色 | Memory Adapter（记忆执行层） | Control Plane / Gateway |
| Memory Backend | 需要远程 backend 才能运行 | Local Runtime 为第一公民 |
| API Key 定位 | 前置条件（云端身份凭证） | 可选（本地模式无需） |
| Connector 接入 | 默认连接云端 | 默认连接本地 Runtime |
| 记忆存储 | 云端为主 | 本地为默认 |

---

## 4.2 Connector 直连云端问题

**当前问题**:

```json
// OpenClaw Plugin 配置
{
  "baseUrl": "http://127.0.0.1:18011"  // 本地 Adapter → OmniMemora Runtime:8765
}
```

**新架构要求**:

```
Connector → Local Runtime (127.0.0.1:8765) → (可选) Cloud Control Plane
```

**根本冲突**: 当前 OpenClaw Plugin 设计假设有一个远程 memory adapter，而新架构要求 connector 优先连接本地。

---

## 4.3 Railway 依赖不存在 Backend

**当前配置** (`4_core/adapter-raw/.env.example`):

```bash
VIKING_URL=http://openviking-server:1933
VIKING_API_KEY=your_viking_api_key_here
```

**问题**:
- `VIKING_URL` 指向 `http://host.docker.internal:1933`（本地开发地址）
- 云端 Railway 环境中这个 backend 不存在
- 导致 `/memory/write` 等接口实际不可用

**根据 ADR-0002**: 这是"架构职责错位"，不是未完成，是方向错误。

---

## 4.4 命名残留

| 旧命名 | 现状 | 应改为 |
| --- | --- | --- |
| `VIKING_URL` | 环境变量 | `OMNIMEMORA_CONTROL_PLANE_URL` |
| `VIKING_API_KEY` | 环境变量 | 删除 |
| `memory-openviking` | Plugin ID | `omnimemora-memory` |
| `openviking-site` | Cloudflare 项目 | `omnimemora-cloud-console` |
| OpenViking backend | 文档描述 | 删除 |

---

# 五、可复用资产

## 5.1 可直接保留

| 资产 | 说明 | 对应新架构 |
| --- | --- | --- |
| **Cloudflare Pages** | 控制面主入口 | ✅ Cloud Control Plane |
| **D1 Database (tenant_registry)** | 租户注册 | ✅ Control Plane |
| **D1 Database (billing_*)** | 账单系统 | ✅ Billing |
| **Stripe 集成** | checkout/portal/webhook | ✅ Billing |
| **Trial Provisioning** | 试用开通逻辑 | ✅ Control Plane |
| **Railway `/usage/token-savings`** | Token savings 聚合 | ✅ Control Plane |
| **Railway `/internal/trial-query`** | Trial 查询 | ✅ Control Plane |
| **Railway `/api/admin/trials/provision`** | Trial 开通 | ✅ Control Plane |
| **GitHub Releases** | Connector 分发 | ✅ Distribution |

---

## 5.2 需降级为 Optional

| 资产 | 当前状态 | 降级后 |
| --- | --- | --- |
| **Railway `/memory/*` 接口** | 主存储承诺 | 仅内部/过渡使用，标注 DEPRECATED |
| **Cloudflare `/api/memory/*` 代理** | 主存储代理 | 仅 trial/demo 使用 |
| **云端 metering 聚合** | 唯一 metering 路径 | 可选增强，本地 Runtime 优先 |

---

## 5.3 应删除

| 资产 | 删除原因 |
| --- | --- |
| `VIKING_URL` 环境变量 | 不存在的 backend，误导性强 |
| `VIKING_API_KEY` 环境变量 | 旧架构残留 |
| `memory-openviking` plugin ID | 命名混乱 |
| Railway `/memory/write/search/read/delete/snapshot` 路由 | 依赖不存在 backend，无实际功能 |
| `openviking-site` 项目名 | 品牌命名应统一 |
| "云端主记忆"产品承诺 | 违反 Local First 架构 |

---

# 六、结论

## 6.1 Local First 架构下云端最终应保留

```
┌─────────────────────────────────────────────────────────┐
│                  Cloud Control Plane                     │
│                  (doloclaw.com)                          │
├─────────────────────────────────────────────────────────┤
│  保留                                    │  删除          │
│  ───                                    │  ───          │
│  ✅ 官网 / 文档                          │  ❌ 云端主记忆    │
│  ✅ 账户 / 租户管理 (D1)                 │  ❌ Railway     │
│  ✅ API Key 管理 (新增)                  │     Memory Plane│
│  ✅ 试用开通 (trial)                     │  ❌ VIKING_URL  │
│  ✅ 套餐与计费 (Stripe)                  │  ❌ memory-     │
│  ✅ Stripe Webhook                      │     openviking  │
│  ✅ Admin Console                       │  ❌ 云端记忆 API  │
│  ✅ Token Savings 聚合                   │                │
│  ✅ Policy Bundle 分发 (可选)            │                │
│  ✅ Connector 下载 (GitHub)             │                │
└─────────────────────────────────────────────────────────┘
```

---

## 6.2 云端职责最终定义

| 职责 | 说明 | 实现 |
| --- | --- | --- |
| **Identity** | 租户注册、API Key lifecycle | D1 + Cloudflare API |
| **Auth** | API Key 验证 | Cloudflare Functions |
| **Billing** | Stripe 集成、套餐管理 | Cloudflare + Stripe |
| **Trial** | 试用开通、配额管理 | Cloudflare + Railway（精简后） |
| **Metering Aggregation** | Token savings 聚合（可选） | Railway 或 Cloudflare Workers |
| **Policy Distribution** | 策略包下发（可选） | Cloudflare D1 |
| **Distribution** | Connector 下载 | GitHub Releases |

---

## 6.3 云端最终不承载

- ❌ 用户主记忆数据
- ❌ Connector 默认接入点（改为本地 Runtime）
- ❌ 强制 API Key 依赖
- ❌ 任何需要远程 backend 才能成立的功能

---

## 6.4 最小改造路线图

**P0: 止血**
1. Railway `/memory/*` 标记 DEPRECATED，返回 `410 MEMORY_PLANE_DISABLED`
2. 移除 `VIKING_URL` 作为必填生产依赖
3. 文档移除"云端主记忆"承诺

**P1: 角色重构**
1. Railway 转型为 Gateway/Metrics Service
2. 删除或隐藏 `/memory/write/search/read/delete/snapshot`
3. Cloudflare 新增 key create/revoke API

**P2: 产品化**
1. 官网改为 "Cloud Control Plane" 定位
2. 实现 Token Savings Console UI
3. 全局替换旧命名（VIKING → OMNIMEMORA）

---

**文档结束**
