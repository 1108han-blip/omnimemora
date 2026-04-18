---
doc_id: COMPAT-PHASE5_5-TRACKA-8765-2026-04-18
title: OmniMemora Phase 5.5 Track A 8765 过渡兼容清单
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora Phase 5.5 / Track A: 8765 过渡兼容清单

## 一、文档定位

本文件用于明确 `8765` 当前哪些 HTTP 路径继续保留为内部依赖面，哪些路径不得再出现在正式产品叙事中，哪些路径只允许作为过渡或历史兼容存在。

本文件不授权删除 runtime 路径；它只定义：

- 内部保留
- 对外退场
- 过渡兼容

## 二、继续保留的内部依赖面

以下路径继续允许存在于 `8765`，但仅作为 gateway / runtime / operator 内部依赖：

| 路径 | 用途 | 说明 |
|------|------|------|
| `GET /health` | runtime 健康检查 | 用于内部健康探测与候选实例验证 |
| `GET /metrics` | runtime-local metrics | 仅限 runtime 自身指标，不是产品 KPI 真相 |
| `GET /agents/control` | 低频 install 状态读取 | 仅供 gateway/UI 控制面代理 |
| `POST /agents/control/install` | 低频 attach/install | install/uninstall 层内部动作 |
| `POST /agents/control/uninstall` | 低频 detach/uninstall | 保留 backup restore 语义 |
| `POST /agents/control/rescan` | 低频探测刷新 | 仅供 gateway/UI 代理 |
| `POST /memory/write` | runtime 写入 | gateway 与内部验证依赖 |
| `POST /memory/query` | runtime 查询 | gateway 与内部验证依赖 |
| `POST /memory/search` | runtime 搜索 | gateway compile/search 依赖 |
| `POST /memory/delete` | runtime 删除 | 内部能力面 |
| `POST /connector/register` | 内部 connector 注册 | 内部能力面 |
| `GET /connector/list` | 内部 connector 枚举 | 内部能力面 |
| `POST /internal/metrics` | bootstrap/internal verification | 仅内部使用 |

## 三、不得再出现在正式产品叙事中的路径或表述

以下内容不得再作为正式产品接口、对外接入建议、或用户验收入口出现：

- 把 `8765` 写成产品入口
- 把 runtime `/health` 写成产品健康入口
- 把 runtime `/metrics` 写成 KPI 真相入口
- 把 runtime `/agents/control*` 写成用户直接调用的正式控制面
- 把 `127.0.0.1:8765` 暴露为插件、UI、agent 的首选接入地址
- 把 runtime dashboard 或 runtime HTTP contract 当成用户主操作面

## 四、允许保留但必须带限制说明的内容

以下内容可以暂时保留，但文档必须显式标记为 internal-only / operator-only：

- runtime README 中的 HTTP contract 清单
- runtime `/health`、`/metrics` 的本地调试示例
- 候选实例、隔离环境、启动链路验证文档中出现的 `8765`
- 审计、验证记录、历史报告中的 `8765` 事实描述

## 五、当前对外验收绑定规则

正式产品对外验收只绑定：

- gateway `:18011`
- gateway 暴露的产品诊断面
- UI/GUI 控制面

不得再以 `8765` 行为作为“产品已具备某能力”的对外验收证据。

## 六、下一步实现约束

Track A 后续实现只能做以下方向：

1. 收紧文档与说明中的 `8765` 曝光面
2. 让 gateway 持续承接正式产品接口
3. 为未来可能的 runtime contract 精简建立清单

本阶段不做：

- 删除 runtime HTTP 路径
- 改变 `18011 -> runtime` 内部调用链
- 把 runtime control/install 迁到别处
