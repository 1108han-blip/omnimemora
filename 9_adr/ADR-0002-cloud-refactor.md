---
doc_id: ADR-0002-CLOUD-REFACTOR
title: OmniMemora Cloud Refactor
owner: platform-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-14
depends_on: [ADR-0001-PRODUCT-BOUNDARY]
supersedes: []
last_verified_commit: ""
---

| 内容                | Blueprint 对应  |
| ----------------- | ------------- |
| 云端不存记忆            | 宪法1           |
| Control Plane 重构  | 架构模型          |
| 删除 memory backend | 非目标           |
| Gateway 角色        | Control Plane |

# 一、先给结论：当前云端该怎么改

## 目标态

把当前云端产品从：

**Cloudflare Pages（鉴权） → Railway Adapter（记忆执行） → 不存在的 backend**

改成：

**Cloudflare Pages / D1 / Stripe / Admin Console = OmniMemora Cloud Control Plane**  
**Railway = License Gateway / Trial Gateway / Policy Gateway / Telemetry Gateway（可选）**  
**删除“云端主记忆 backend”这个产品承诺**

也就是说：

### 云端保留

- 官网
    
- 账户/租户管理
    
- API key 管理
    
- 试用开通
    
- 套餐与计费
    
- Stripe webhook
    
- 后台 admin tenant 管理
    
- trial query / entitlement query
    
- 策略包管理
    
- 文档和接入说明
    

### 云端砍掉

- “我来存你的主记忆”
    
- “Railway 执行真正 memory write/search/read/delete”
    
- “需要一个远程 backend 才能跑通”
    

---

# 二、为什么必须这么改

你当前云端文档里有 3 个信号已经说明旧方案不该再救了。

## 1）Railway 当前就是 memory plane

Railway 上已有完整的 `/memory/write`、`/memory/search`、`/memory/read`、`/memory/delete`、`/memory/snapshot` 路由，说明它被当作正式记忆执行层来设计。

## 2）它依赖一个不存在的 backend

文档明确写了：`VIKING_URL` 指向旧的 `http://host.docker.internal:1933`，而这个 backend 在云端根本不存在，导致 write 失败、search 异常。

## 3）Cloudflare 侧缺失 `/api/memory/*`

这说明你现在的产品流量入口其实也没完全收敛，Cloudflare 和 Railway 的职责边界没定死。当前缺失的就是 `/api/memory/write/search/read/delete/snapshot`。

所以硬判断就是：

**当前云端产品不是“未完成”，而是“架构职责错位”。**

---

# 三、直接达成目标的改造方案

我不给你泛泛建议，直接给你“能落地”的版本。

## Phase 1：先定云端宪法

先把云端产品定义改成这 4 条，写死：

### OmniMemora Cloud 宪法

1. **云端不承载用户主记忆数据。**
    
2. **云端不要求存在远程主记忆 backend 才能成立。**
    
3. **云端只负责控制面：鉴权、计费、租户、策略、试用、文档、后台。**
    
4. **任何 `/memory/*` 云端接口都不是主存储承诺，只能是网关、调度或将来可选能力。**
    

这一步不是文案，是工程边界。

---

## Phase 2：重构 Cloudflare Pages 的角色

Cloudflare Pages 现在已经有 D1、billing、trial、tenant 管理，这正适合做控制面。

### 保留并加强这些接口

- `/api/admin/tenants`
    
- `/api/trial/query`
    
- `/api/billing/plans`
    
- `/api/billing/checkout-session`
    
- `/api/billing/portal-session`
    
- `/api/billing/webhook`
    

### 新增这些控制面接口

- `/api/auth/keys/create`
    
- `/api/auth/keys/revoke`
    
- `/api/entitlements/me`
    
- `/api/policies/current`
    
- `/api/devices/register`
    
- `/api/devices/list`
    
- `/api/trials/provision`
    
- `/api/tenants/status`
    

### 对 `/api/memory/*` 的处理

这里要做一个硬转向：

#### 方案 A，最稳

**暂时不对外开放 `/api/memory/*`**  
文档里彻底移除“云端记忆 API 已可用”的说法。

#### 方案 B，过渡方案

保留 `/api/memory/query` 这类轻量查询代理，但明确标注：

- 仅 trial/demo
    
- 非主存储
    
- 非长期承诺
    
- 不保证数据持久性
    

**我建议你走 A。**

因为你现在不是缺 handler，而是产品方向变了。

---

## Phase 3：Railway 从 Memory Adapter 改造成 Cloud Gateway

这是最关键的一刀。

当前 Railway 服务叫 `omnimemora-adapter-production`，版本还是 “Memory Adapter v2.2.0”，并且暴露完整记忆操作路由。

这个服务别删，但要**改角色**。

### 新角色

把 Railway 从：

**Memory Adapter / Memory Plane**

改成：

**Gateway / Control Worker / Metering Service**

### Railway 改造后只保留

- `/health`
    
- `/support/error-codes`
    
- `/api/admin/trials/provision`
    
- `/internal/trial-query`
    
- `/usage/token-savings`
    
- `/usage/token-savings/trend`
    
- `/requests/{request_id}/meter`
    

### Railway 要下线或隐藏的

- `/memory/write`
    
- `/memory/search`
    
- `/memory/read`
    
- `/memory/delete`
    
- `/memory/snapshot`
    

这些可以先：

- 标为 deprecated
    
- 仅内部 mock 使用
    
- 或直接移除公网暴露
    

### 这一步带来的直接好处

一旦 Railway 不再要求 `VIKING_URL`，你现在最大的阻塞点直接消失。当前文档里第 1 阻塞项就是这个。

---

## Phase 4：配置与命名一次性切干净

你现在云端还残留这些旧命名：

- `VIKING_URL`
    
- `VIKING_API_KEY`
    
- `memory-openviking`
    
- OpenViking backend
    

这些都该切掉。文档里这一套旧词现在还贯穿云端链路。

### 改成

- `OMNIMEMORA_CONTROL_PLANE_URL`
    
- `OMNIMEMORA_INTERNAL_API_TOKEN`
    
- `OMNIMEMORA_ADMIN_API_TOKEN`
    
- `OMNIMEMORA_POLICY_BUNDLE_URL`
    
- `OMNIMEMORA_REGISTRY_SYNC_URL`
    
- `OMNIMEMORA_GATEWAY_MODE=control_plane`
    

### 同时要做的文档替换

- 删除 “OpenViking Backend (不存在)” 这种图
    
- 删除 “需配置正确 backend URL 才能运行” 这种前提
    
- 删除 “Backend 存储方案待定” 这种旧决策项。这个旧决策项现在还挂在本地架构参考里，但对新云端目标已经失真。
    

---

# 四、你当前云端代码该怎么拆

## 1）Cloudflare Pages 仓库

把它确认为：  
**`omnimemora-cloud-console`**

职责：

- marketing site
    
- docs
    
- admin
    
- billing
    
- trial
    
- tenant registry
    
- policy distribution
    

### 立即要做的动作

- 删掉 memory plane 的 roadmap 描述
    
- 新增 Control Plane 文档页
    
- 新增 API key 管理页
    
- 新增 tenant 状态页
    
- 新增设备/接入说明页
    

---

## 2）Railway 仓库

把 `omnimemora-adapter-prod` 逻辑拆成两部分：

### 可保留的通用模块

你本地参考架构里这些模块其实不是只有“记忆存储”才能用：

- `access.py`
    
- `v2_query.py`
    
- metering 相关
    
- admin/trial provisioning 相关  
    这些可以继续用于云端控制服务。
    

### 应剥离的 memory pipeline

- `normalizer.py`
    
- `filter.py`
    
- `dedup.py`
    
- `router.py`
    
- 以及所有最终依赖 backend 的 `/memory/*` 路由  
    这些属于执行面，不该继续挂在当前云端正式产品上。
    

也就是说，当前仓库不是废掉，而是**瘦身转型**。

---

# 五、最小改造路线图

这是我认为最直接、最少绕路的版本。

## P0：止血

1. 把 Railway 的 `/memory/*` 在文档里全部标记为 deprecated
    
2. 去掉 `VIKING_URL` 作为必填生产依赖
    
3. 修改官网/API文档，不再承诺云端主记忆存储
    
4. 保留 trial、billing、tenant registry 正常运行
    

## P1：角色改造

1. Railway 改名为 gateway/service
    
2. 删除或下线对不存在 backend 的调用链
    
3. Cloudflare 补全控制面接口，而不是补 `/api/memory/*`
    
4. D1 继续作为 tenant registry 与 entitlement registry
    

## P2：产品化

1. 官网改成 “Cloud Control Plane”
    
2. 后台加入 key lifecycle
    
3. 加套餐 gating、试用剩余额度、租户状态管理
    
4. 文档改成：
    
    - 云端：账户、策略、授权
        
    - 非云端：主记忆执行
        

---

# 六、你现在最该让 Codex 执行的任务

你要的是直接达成目标，那就别让它继续补 memory API 了。  
应该直接改这 6 件事：

### 任务 1

**删除 Railway 对 `VIKING_URL` 的生产依赖**

- 没有这个变量时服务仍正常启动
    
- 仅 memory routes 禁用或返回明确 `410 Deprecated`
    

### 任务 2

**把 `/memory/*` 路由全部改成 deprecated**  
返回统一响应，例如：

```json
{
  "error": "MEMORY_PLANE_DISABLED",
  "message": "OmniMemora Cloud no longer provides hosted primary memory storage."
}
```

### 任务 3

**提取 Gateway 保留路由**  
保留：

- health
    
- admin trial provision
    
- internal trial query
    
- usage metering
    
- support
    

### 任务 4

**Cloudflare Pages 新增控制面 API**  
新增：

- key create/revoke
    
- entitlements
    
- tenant status
    
- policy bundle metadata
    

### 任务 5

**全仓替换旧命名**

- `VIKING_*` → `OMNIMEMORA_*`
    
- `openviking` → `omnimemora`
    
- 插件 ID、文档标题、环境变量说明全部切换
    

### 任务 6

**重写部署文档**  
新部署文档必须明确：

- 云端部署不再依赖远程 memory backend
    
- Railway 只是 control/gateway service
    
- Cloudflare 是主控制台与 API 边界
    

---

# 七、我对你这个项目的硬判断

你这次说清楚以后，方向反而更好定了。

**不是“本地 + 云协作架构”要怎么设计，**  
而是：

> **当前云端产品原本误走成了“托管 memory plane”，现在要强制纠偏成纯控制面产品。**

这件事一旦做对：

- 你不再被 `VIKING_URL` 卡死
    
- 你不再背“用户主记忆托管”的合规包袱
    
- 你不再需要为了云端产品硬补一个根本不该存在的 hosted backend
    
- 你的网站、计费、试用、租户系统会一下子变得逻辑统一
    

说白了：

**别救那个云端记忆 backend 幻觉。直接宣布它不存在，而且以后也不是主产品方向。**

这是最省时间、最专业、也最像产品负责人的决策。

如果你要，我下一条可以直接给你一份 **“Codex 可执行的云端改造任务清单（按仓库 / 文件 / 函数级）”**。