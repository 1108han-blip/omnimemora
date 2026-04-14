This document is a historical snapshot and must not be used for product or architecture decisions.

# 8.53 OmniMemora项目交接清单-2026-04-07

## 当前结论

- 本机 `8000 / 1933 / Docker` 是开发验证环境，不是正式产品面。
- `doloclaw.com` 已经承载 OmniMemora 的公开站点与 trial 入口。
- `https://doloclaw.com/api/contact` 已可公网申请 trial。
- `https://doloclaw.com/api/trial/query` 已部署并可用，但当前仍是 `v1 placeholder`，还没有接到真实云端 query runtime。
- 产品当前方向：
  - 云端核心服务
  - 本地轻量 connector / plugin / skill
  - `Claude Code / Codex / OpenClaw` 作为 3 个独立真实用户验证 token 变化

## 已完成

- 官网、Demo、Docs、Contact、Open Source 页面已上线并统一为 `OmniMemora`
- trial 自动开通链路已成立：
  - contact -> lead -> tenant -> trial key
- adapter / access / usage / quota / leads / app 最小 SaaS 闭环已落地
- Stripe 代码已冻结，不再作为当前主线
- `wrangler.jsonc` 已修正并恢复 `LEADS_DB` 绑定
- `query.ts` 已部署到 Pages Functions

## 当前状态压缩

```text
Goal: 把 OmniMemora 从“trial 申请可用”推进到“云端真实 query 产品面可用”，并准备三真实用户验证
Changed Files: contact.ts, query.ts, wrangler.jsonc, access.py, main.py, config.py, 多个 ui-prototype 页面
Current Status: 公开站点可用，trial 发号可用，trial query 路由已上线，但仍是 placeholder；云端真实 query runtime 尚未接通
Next Step: 把 /api/trial/query 接到真实云端 query runtime，并设计三独立用户的 metrics 验证链
```

## 重要边界

- 不要再走“本地 tunnel 暴露给用户”的主线。
- 正式产品应是云端核心 + 本地轻量接入层。
- `Claude Code / Codex / OpenClaw` 不是产品模块，而是独立真实用户。
- 三者必须：
  - 独立 tenant
  - 独立 key
  - 独立 usage / token savings 统计

## 安全与清理

- 不要复用之前泄露过的 trial key。
- 已禁用的泄露 tenant：
  - `trial-94ba0176ba66`
  - `trial-e95ac9e3be09`
- 后续执行记录中禁止写出任何明文 API key / secret。

## 直接交给 Claude Code 的后续任务清单

### Task 1

```text
[Goal]
将 /api/trial/query 从 placeholder 接到真实云端 OmniMemora query runtime。

[Current State]
query.ts 已上线并可用，但只返回 v1 placeholder 结构；trial 发号已通。

[Scope]
E:\AI相关\Obsidian Vault\13 OpenViking商业项目\artifacts\packages\OpenViking-Enterprise-v2026.03.28.0\runtime\ui-prototype\functions\api\trial\query.ts
必要时只扩展到同目录最少相关函数文件。

[Constraints]
不要走本地 tunnel 主线。
不要泄露任何 trial key。
保持现有 trial key 校验逻辑不被破坏。

[Expected Output]
让公网 /api/trial/query 返回真实 query 结果，而不是 placeholder。
同时产出执行记录文档。
```

### Task 2

```text
[Goal]
定义并实现三真实用户验证基线：Claude Code、Codex、OpenClaw 各自独立 tenant/key/metrics。

[Current State]
产品方向已明确，但三独立用户验证结构尚未正式落地。

[Scope]
先出文档与最小配置方案；仅修改必要配置和文档，不扩大到无关模块。

[Constraints]
三者不能共用身份。
统计必须可分别查看。
不要把三者写成产品内部模块。

[Expected Output]
形成一份可执行的三用户验证配置方案，至少包括：
- tenant/key 分配
- usage / token savings 分桶
- 基本接入顺序
并产出执行记录文档。
```

### Task 3

```text
[Goal]
为 OmniMemora 定义“云端核心 + 本地轻量接入层”的最小产品交付结构。

[Current State]
产品方向已理顺，但 GitHub / 官网 / connector 边界还没有正式收口成实施结构。

[Scope]
文档为主；必要时只补最小目录或说明页，不做大重构。

[Constraints]
不要重新回到“整套安装包售卖”。
保留开源可下载部分，但核心功能应留在 API。

[Expected Output]
形成一份明确的交付边界文档，至少说明：
- 云端服务包含什么
- 本地 connector / plugin / skill 包含什么
- GitHub 提供什么
- 用户体验路径是什么
```

### Task 4

```text
[Goal]
设计 token 节省验证口径，支持 Google Cloud provider-side usage 与 OmniMemora saved estimate 对照。

[Current State]
Token Savings Meter 已有产品雏形，但真实用户验证口径尚未正式收口。

[Scope]
文档与最小数据结构为主。

[Constraints]
按用户分别统计，不做混合总表替代。
先做验证口径，不急着做大仪表盘。

[Expected Output]
形成一份 metrics 方案，至少包括：
- provider actual usage
- OmniMemora saved estimate
- per-user comparison
- 最小采集点
```

## 交接顺序建议

1. 先做 Task 1
2. 再做 Task 2
3. 然后做 Task 4
4. 最后做 Task 3

## 交接备注

- 默认继续遵守 `E:\AI\AGENTS.md` 的低消耗执行模式
- `Claude Code` 执行
- `Codex` 只做验收与纠偏
