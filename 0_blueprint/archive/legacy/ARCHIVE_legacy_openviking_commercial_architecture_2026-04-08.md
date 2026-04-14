---

ARCHIVED.
This document reflects a deprecated pre-blueprint architecture and must not be used for current planning or implementation.

---

# OmniMemora 本地产品架构

**日期:** 2026-04-08
**产品定位:** 商业记忆即服务（Memory-as-a-Service）

---

## 一、产品定位

OmniMemora 是 OpenViking 的商业迭代产品：

| 组件 | 许可证 | 定位 |
|------|--------|------|
| **OpenViking Engine** | AGPL-3.0 | 开源记忆引擎（文件型存储，viking:// URI） |
| **OmniMemora Memory Adapter** | 商业 | 商业中间层（多租户鉴权、路由、计费） |

```
OpenViking Engine (AGPL-3.0, 开源)
    ↓
OmniMemora Memory Adapter (商业中间层)
    ↓
OmniMemora Control Plane (D1 + Cloudflare Pages)
    ↓
OmniMemora Memory Plane (Railway FastAPI Adapter)
```

---

## 二、代码仓库

### 公开仓库

| 仓库 | URL | 内容 |
|------|-----|------|
| `omnimemora-core` | github.com/1108han-blip/omnimemora-core | 公共 A+C（MCP server + 工具接口文档） |

### 私有仓库

| 仓库 | URL | 内容 |
|------|-----|------|
| `omnimemora-adapter-prod` | github.com/1108han-blip/omnimemora-adapter-prod | FastAPI 商业 adapter 生产版本 |
| `infra` | （私有） | GitHub Actions 部署配置、域名绑定文档 |

---

## 三、omnimemora-adapter-prod 结构

```
omnimemora-adapter-prod/
├── app/
│   ├── main.py          # FastAPI 主体 (~2400行)，所有路由定义
│   ├── config.py        # Pydantic Config，所有环境变量和阈值配置
│   ├── access.py        # 租户注册表管理、API key 鉴权、D1 同步
│   ├── dedup.py         # MD5 内容去重（24h TTL，10000 条 LRU）
│   ├── filter.py        # 内容过滤（长度 <20 丢弃，类型过滤）+ 失败经验检测
│   ├── normalizer.py     # 数据标准化、TTL 计算
│   ├── router.py        # 评分制记忆路由（L0-L3）
│   └── v2_query.py      # Token Savings Meter、Quota 强制执行
├── requirements.txt
├── Dockerfile
├── start.sh
└── .env.example
```

### main.py 路由一览

| 路由 | 功能 |
|------|------|
| `POST /memory/write` | 标准化→过滤→去重→限流→路由→转发 OpenViking |
| `POST /memory/search` | OpenClaw 插件兼容的 `memories[]` 返回格式 |
| `POST /memory/read` | 按 URI 或查询读记忆 |
| `POST /memory/delete` | 按 URI 删除 |
| `POST /memory/snapshot` | 从 OpenViking 生成 `MEMORY.md` 自动摘要 |
| `GET /memory/types` | 记忆类型、等级（L0-L3）、TTL、失败检测关键词 |
| `POST /memory/query` | V2 统一查询 + Token Savings Meter |
| `POST /internal/trial-query` | Cloudflare Pages 调用的内部端点 |
| `POST /api/admin/trials/provision` | Trial 开通（X-OmniMemora-Admin-Token 保护） |

---

## 四、omnimemora-core 结构（A+C 公开内容）

```
omnimemora-core/
├── openapi.yaml          # OpenAPI 3.1 规范（生产 API 契约）
├── schemas/              # JSON Schema 定义
│   ├── memory_write.request.schema.json
│   ├── memory_write.response.schema.json
│   ├── memory_search.request.schema.json
│   ├── memory_search.response.schema.json
│   └── health.response.schema.json
├── mcp/
│   └── ov_enterprise_mcp_server.py  # MCP stdio server（参考实现）
├── mock/
│   └── mock_adapter.py   # 本地开发 mock adapter
├── examples/
│   ├── claude_code_mcp_example.md
│   ├── codex_api_example.md
│   └── openclaw_example.md
├── docs/
│   ├── TOOL_INTERFACE.md  # 工具接口文档（对外）
│   ├── COMPLIANCE.md      # 合规说明
│   └── INTEGRATION_GUIDE.md
└── supervisor/skills/     # Agent skill 定义
```

---

## 五、OpenViking-Enterprise-v2026.03.28.0 包结构

**路径:** `artifacts/packages/OpenViking-Enterprise-v2026.03.28.0/`

```
OpenViking-Enterprise-v2026.03.28.0/
├── runtime/
│   ├── adapter/           # Memory Adapter 代码（同 omnimemora-adapter-prod）
│   │   ├── app/
│   │   │   ├── main.py        # v2.2 FastAPI
│   │   │   ├── config.py      # Pydantic Config
│   │   │   ├── access.py      # 租户注册表
│   │   │   ├── dedup.py       # 去重
│   │   │   ├── filter.py      # 过滤
│   │   │   ├── normalizer.py  # 标准化
│   │   │   ├── router.py      # 路由
│   │   │   └── v2_query.py    # Token Savings Meter
│   │   ├── requirements.txt
│   │   └── openviking.Dockerfile  # Python 3.11 + pip install openviking
│   │
│   ├── engine/            # 企业生命周期管理（30+ 模块）
│   │   ├── ov_enterprise_install.py
│   │   ├── ov_enterprise_install_check.py
│   │   ├── ov_enterprise_upgrade.py
│   │   ├── ov_enterprise_backup.py
│   │   ├── ov_enterprise_restore.py
│   │   ├── ov_enterprise_rollback.py
│   │   ├── ov_enterprise_uninstall.py
│   │   ├── ov_enterprise_verify.py
│   │   ├── ov_enterprise_doctor.py
│   │   ├── ov_enterprise_rehearsal.py
│   │   └── ... (tenant/context/runtime/tool 管理模块)
│   │
│   ├── plugin/
│   │   └── memory-openviking/  # OpenClaw 插件
│   │       ├── index.ts        # 主插件（memory_recall/store/forget 工具）
│   │       ├── client.ts       # MemoryAdapterClient（HTTP → adapter）
│   │       ├── config.ts       # 配置 schema
│   │       ├── memory-ranking.ts  # 后处理、分数钳制、注入选择
│   │       ├── text-utils.ts   # 文本提取、清洗、转录检测
│   │       ├── openclaw.plugin.json
│   │       └── package.json
│   │
│   └── ui-prototype/      # Cloudflare Pages 原型
│       ├── functions/
│       │   └── api/
│       │       ├── leads.ts
│       │       ├── leads/summary.ts
│       │       ├── admin-tenants.ts
│       │       ├── trial/query.ts
│       │       ├── tenants.ts
│       │       ├── contact.ts
│       │       └── billing/
│       │           ├── plans.ts
│       │           ├── checkout-session.ts
│       │           ├── portal-session.ts
│       │           ├── webhook.ts
│       │           └── schema.sql
│       ├── app/leads/index.html
│       ├── docs/
│       ├── wrangler.jsonc
│       ├── _routes.json
│       └── _worker.bundle
│
├── artifacts/
│   ├── baseline/
│   ├── last_execute/
│   ├── last_verify/
│   └── workspace/
│
└── README.md
```

---

## 六、记忆路由评分规则（L0-L3）

```python
route_score_rules = {
    "length_gt_100": 1,        # 内容 > 100 字符
    "length_gt_500": 1,        # 内容 > 500 字符
    "success_keyword": 2,       # 含"成功"/"完成"
    "strategy_keyword": 2,      # 含"策略"/"规划"
    "important_keyword": 2,     # 含"重要"/"关键"
    "knowledge_keyword": 2,     # 含"知识"/"规则"
    "failure_experience": 2,    # 失败经验（v2.2 新增，不过滤改为加分）
    "type_strategy": 2,        # metadata.type = strategy
    "type_result": 1,           # metadata.type = result
    "type_failure": 2,         # metadata.type = failure_experience
}
long_term_threshold = 2        # 分数 ≥2 进入长期记忆
```

**记忆等级：**

| 等级 | 分数 | TTL | 说明 |
|------|------|-----|------|
| L0 | 0 | — | 垃圾，不存储 |
| L1 | 1-2 | 7天 | 短期缓存 |
| L2 | 3-4 | 30天 | 经验记忆 |
| L3 | ≥5 | 永久 | 核心知识 |

---

## 七、OpenClaw 插件工具

**插件 ID:** `memory-openviking`
**注册工具:** `memory_recall`, `memory_store`, `memory_forget`
**钩子:** `session_start`, `session_end`, `before_prompt_build`, `agent_end`

### autoCapture 逻辑

```
session_start  → memory_recall (获取历史记忆)
before_prompt_build → memory_recall (上下文注入)
agent_end → memory_store (写入当前会话重要内容)
session_end → memory_store (生成 MEMORY.md 快照)
```

### 配置参数

```json
{
  "baseUrl": "https://api.doloclaw.com",
  "agentId": "main-agent",
  "vikingAccount": "18790-account",
  "vikingUser": "18790-user",
  "autoCapture": true,
  "autoRecall": true
}
```

---

## 八、API 密钥体系（产品级设计）

```
三层鉴权模型：

A层 — Internal System Auth（系统内部）
  VIKING_API_KEY / OMNIMEMORA_INTERNAL_API_TOKEN
  用途：adapter ↔ core, registry sync, metering writer
  特点：不暴露给用户

B层 — Tenant API Key（对外正式调用）
  omni_tk_live_xxxxx / omni_tk_test_xxxxx
  用途：SDK / CLI / MCP / Agent / 插件
  存储：只存 key_id + secret_hash（不存明文）

C层 — Ephemeral Session Token（短期令牌）
  TTL：15min / 1h / 24h
  用途：浏览器临时接入、第三方回调
```

---

## 九、套餐体系

| 套餐 | 价格 | 额度 |
|------|------|------|
| Starter | $29/月 | 500,000 tokens/month |
| Pro | $99/月 | 待定 |
| Enterprise | 定制 | 定制 |

---

## 十、下一步决策点

| 决策项 | 选项 |
|--------|------|
| **Backend 存储方案** | A: 自托管 OpenViking Engine<br>B: 使用 Volcengine 部署<br>C: 替换为其他向量存储 |
| **记忆 API 实现** | A: 补全 CF Pages `/api/memory/*` handlers<br>B: 全部走 Railway 直连（无需 CF 层） |
| **多租户范围** | A: 单一 trial tenant<br>B: 支持多租户隔离 |
| **计费接入** | A: Stripe 已集成，待配置<br>B: 暂不接计费 |
