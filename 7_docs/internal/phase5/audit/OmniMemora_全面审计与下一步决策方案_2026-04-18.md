# OmniMemora 全面审计与下一步决策方案

**日期：** 2026-04-18  
**语言：** 中文版  
**审计性质：** 只读审计，不修改产品代码路径，不把未提交工作区视为既成事实  
**当前仓库路径：** `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora`

## 1. 审计目标

本次审计不先给实现打分，而是先回答四个问题：

1. 现行产品要求到底是什么，哪些文档仍代表真相。
2. 代码当前真实实现到了哪里，哪些只是文档表述，哪些已经落地。
3. 文档、代码、未提交工作区、运行路径之间有哪些冲突或漂移。
4. 下一步应先整理文档与环境，还是先修产品与架构，以及顺序是什么。

本轮唯一主基线为：

- `README.md`
- `0_blueprint/PRODUCT_DEFINITION.md`
- `0_blueprint/DEFAULT_IN_CONTROL_PLANE.md`
- `0_blueprint/ROADMAP.md`
- `9_adr/ADR-0003-interface-access-paths.md`

以下内容降级为历史或冲突来源，不再直接作为现行验收标准：

- `7_docs/internal/phase3/**`
- `0_blueprint/PRODUCT_CONSTITUTION.md`
- 所有仍以 `memory tool / optional call / phase3 productization / /memory/query 主线` 为中心的旧文档

## 2. 执行前校准结论

根据仓库当前里程碑信号，活跃 phase 指向：

- [7_docs/internal/phase5/plan/云端小工程.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/云端小工程.md)

这意味着不能再把 `phase3` 启动文档默认当作现行启动真相。  
但当前仓库存在一个治理缺口：

- `phase5` 有 active 计划文档。
- `phase5` 没有对应的 working principles / SOP 文档。
- 仓库里仍只有 `phase3` 的 working principles / data governance SOP。

因此，启动治理层已经发生事实漂移：

- 里程碑现实已经进入 `phase5`
- 启动规范现实仍停留在 `phase3`

本轮未处理实验数据，因此未触发实验数据治理脚本。

## 3. 主基线冻结结果

### 3.1 主基线文档清单

- [README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/README.md)
- [0_blueprint/PRODUCT_DEFINITION.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_DEFINITION.md)
- [0_blueprint/DEFAULT_IN_CONTROL_PLANE.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/DEFAULT_IN_CONTROL_PLANE.md)
- [0_blueprint/ROADMAP.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/ROADMAP.md)
- [9_adr/ADR-0003-interface-access-paths.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/9_adr/ADR-0003-interface-access-paths.md)

### 3.2 已失效但仍影响判断的历史文档清单

- [7_docs/internal/phase3](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase3)
- [0_blueprint/PRODUCT_CONSTITUTION.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_CONSTITUTION.md)
- 各类以 `/memory/query`、`memory tool`、`optional call` 为主叙事的历史架构与审计文档

### 3.3 主基线共识

现行产品方向可归纳为：

- `Gateway + UI 双开关 + 弱侵入`
- `:18011` 是唯一产品入口
- `:8765` 只是内部 memory plane
- 产品控制权在 UI，不在 agent 自主决策
- 接入与使用是两个不同层级的动作

## 4. 文档冲突地图

### 4.1 明确冲突

1. `README.md` 指向不存在的文件：
- `DOCS-SSOT-MAP.md`
- `CANONICAL_FACTS.md`
- `CONSTITUTION.md`

2. `ROADMAP.md` 与若干基线文档都声称受 `CONSTITUTION.md v2.0` 接管，但该文件在仓库中不存在。

3. 主基线文档已将产品定义收敛到 `Gateway + 单入口 + UI 控制`，但大量 phase3 与历史架构文档仍把：
- `/memory/query`
- MCP tool / plugin / skill
- runtime 侧接口
- `8765`

放在主产品叙事中心。

4. “弱侵入”已被当作现行方向，但尚未在现行基线中形成统一、可执行、可验收的标准条款。

### 4.2 冲突分层

- **产品定义冲突：** Gateway 产品 vs Memory Control Plane 历史定义
- **入口冲突：** `:18011` 唯一入口 vs `/memory/query` 历史主链
- **控制面冲突：** UI 双开关 vs 已提交代码中的 `guided/observe` 模式
- **启动治理冲突：** phase5 active vs phase5 SOP 缺失

## 5. 代码与行为审计

## 5.1 已提交真实状态

当前已提交真实状态是分支上的 `HEAD`，不是未提交工作区。  
关键事实：

- `18011` 上的 LLM ingress 已经存在并可用。
- `/metrics/summary`、`/proxy/status`、`/agents/live` 已实现。
- `HEAD` 中 **没有** `/agents/control*` 全链路。
- `HEAD` 中 adapter 只注册了 `llm_proxy` 与 `status_api`，没有 `agent_control_api`。
- `HEAD` 中 runtime 也没有 `/agents/control*` 控制端点。
- `HEAD` 中 agent 控制语义仍延续 `guided / observe` 时代。

### 5.2 工作区候选状态

当前 dirty worktree 明显在推进一条新现实：

- 新增 adapter 侧 `agent_control_api.py`
- 新增 adapter 侧 `agent_routing_state.py`
- 新增 runtime 侧 `agent_control.go`
- 新增 runtime 侧 `backup.go`
- dashboard 已接入双开关 UI
- 文档正在从“默认接管”改写到“接入/使用分离”

但这些关键文件很多仍是未跟踪文件，说明它们还不是版本真相。

### 5.3 运行现实

本机在线服务来自：

- `~/.omnimemora/service/current/tools/omnimemora-runtime serve`
- `~/.omnimemora/service/current/tools/_run_adapter.py`

不是当前仓库工作区直接启动。

在线行为取证结果：

- `18011` 可访问 `/health`
- `18011` 可访问 `/metrics/summary`
- `18011` 可访问 `/proxy/status`
- `18011` 可访问 `/agents/live`
- `18011` 的 `/agents/control` 返回 `404`
- `8765` 在线，但并未体现当前工作区候选里的控制面 JSON 现实

因此，“运行现实”与“仓库候选现实”已经分叉。

## 6. 公开接口实现度判定

### 6.1 LLM ingress

以下接口已落地且与现行目标基本一致：

- `/llm/v1/messages`
- `/v1/messages`
- `/llm/anthropic`
- `/llm/chat`
- `/v1/chat/completions`
- `/v1/responses`

对应实现主要位于：

- [5_connectors/adapter/llm_proxy.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/llm_proxy.py)
- [5_connectors/adapter/gateway_compile.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/gateway_compile.py)

判定：

- **已落地且基本一致**

补充说明：

- `/v1/responses` 在仓内现实中是兼容层，而不是完全独立主实现。
- `path_registry.py` 仍保留较重的 `legacy` 口径，这会造成文档与代码注释层的漂移。

### 6.2 产品真相/诊断面

以下接口已落地且一致：

- `/metrics/summary`
- `/proxy/status`
- `/agents/live`

对应实现主要位于：

- [5_connectors/adapter/main.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/main.py)
- [5_connectors/adapter/status_api.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/status_api.py)
- [5_connectors/adapter/metrics_aggregator.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/metrics_aggregator.py)
- [5_connectors/adapter/agent_metrics.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/agent_metrics.py)

判定：

- **已落地且一致**

### 6.3 UI 控制面

目标接口：

- `/agents/control`
- `/agents/control/install`
- `/agents/control/uninstall`
- `/agents/control/enable`
- `/agents/control/disable`

事实判定：

- 已提交状态：**未落地**
- 工作区候选状态：**已落地一部分**
- 运行现实：**未落地**

细分判定：

- `/agents/control`：工作区候选已落地，但运行现实未体现
- `/agents/control/install`：工作区候选已落地，方向基本一致
- `/agents/control/uninstall`：工作区候选已落地，方向基本一致
- `/agents/control/enable`：工作区候选已落地，但实现存在断层
- `/agents/control/disable`：工作区候选已落地，但实现存在断层

关键断层：

- enable/disable 修改的是 `agent_modes.json`
- 但真正请求路径上的路由决策没有完整接入该开关
- 也就是说，当前候选现实更像“状态写入已存在”，不是“行为闭环已完成”

判定：

- **部分落地**

## 7. 用户侧集成审计

本节单列 OpenClaw / Claude Code / Codex 的本机接入问题，不把它们混同为产品真相。

### 7.1 Claude Code

现状：

- attach 会写入 OmniMemora 配置
- 工作区候选中新增 backup/restore
- 已提交状态里 backup/restore 尚未成为正式现实

结论：

- 方向在向弱侵入修复
- 但正式真相尚未完成收敛

### 7.2 Codex

现状：

- attach 会写入 provider 配置，使流量进入 `18011`
- 工作区候选新增 backup/restore

结论：

- 作为“接入到产品入口”的方向成立
- 但回滚与恢复当前仍主要存在于候选现实

### 7.3 OpenClaw

现状：

- attach 不只是接入 MCP 或入口地址
- 还会改 provider、默认 model、默认 agent model

这意味着：

- 接入和使用被混成一个动作
- 已明显超出“弱侵入”范畴
- 与“保持原上游语义不变”的现行产品要求存在硬冲突

结论：

- OpenClaw 是当前用户侧集成审计中的最高风险点

### 7.4 边界结论

当前“产品问题”与“用户侧接入问题”的边界还不够清楚。

更准确地说：

- 文档已经开始把二者分开
- 已提交代码现实还没有完全分开
- 工作区候选是在尝试把二者拆开
- 运行实例尚未反映这条拆分后的新现实

## 8. 未提交工作区专项审计

## 8.1 与现行主线一致的增量

- runtime `start` 默认不再 auto-attach，只在显式 `--attach` 时执行 attach
- 新增 runtime `/agents/control*`
- attach 前备份、detach 优先恢复备份
- adapter 新增 UI 控制接口
- dashboard 已转向双开关控制卡模型

## 8.2 试图修正历史漂移的增量

- README 与产品定义从“默认接管”改到“用户授权后接管”
- `agent_modes.json` 从 `guided/observe` 向 `off/force_if_possible` 收敛
- OpenClaw attached 判定从 runtime 口径修到 adapter / MCP / OmniMemora 口径

## 8.3 尚未完成或可能制造新漂移的增量

- 多个关键控制文件仍未纳入版本真相
- 控制开关已可写，但行为闭环尚未证实
- attach/control 路径仍存在硬编码倾向
- 控制面测试覆盖仍偏窄
- 未跟踪杂项文件混在工作区里，增加判断噪音

## 8.4 仓库已提交真实状态 vs 工作区候选状态

### 已提交真实状态

- Gateway 入口链路已成形
- 指标/诊断面已成形
- UI 双开关未正式落地
- 弱侵入 attach/detach 未正式落地

### 工作区候选状态

- 正在把产品收敛到 `Gateway + UI 双开关 + 弱侵入`
- 但关键实现仍处于未提交候选阶段

### 判断

如果现在继续开发，将会默认基于“工作区候选现实”推进。  
但团队可复现、CI 可复现、他人拉取到的仍是“已提交现实”。

因此当前的真实问题是：

> 候选现实已经领先于提交现实，但尚未完成收敛。

## 9. 漂移地图

### 9.1 产品漂移

- 现行产品定义是 Gateway
- 历史代码和文档残留仍不断把系统拉回 Memory Plane / `/memory/query` 叙事

### 9.2 文档漂移

- README 引用失真
- `CONSTITUTION.md` 不存在却仍被当作上位真相引用
- phase3 历史文档仍高度污染判断

### 9.3 环境漂移

- 当前运行实例不来自当前 repo 工作区
- 运行行为与候选代码不一致

### 9.4 接入漂移

- 文档要求弱侵入
- OpenClaw 当前实现仍带明显强侵入痕迹
- 接入与使用尚未彻底拆开

## 10. 差距矩阵

| 要求 | 代码现状 | 运行现状 | 文档现状 | 冲突 | 风险 | 优先级 |
|---|---|---|---|---|---|---|
| `:18011` 唯一产品入口 | 已基本实现 | 在线成立 | 主基线一致 | 历史 `/memory/query` 叙事仍强 | 容易误判产品真相 | P0 |
| UI 双开关 | 候选中推进 | 运行未体现 | 新主线已表达 | 已提交与运行现实不一致 | 继续开发会踩空现实 | P0 |
| 弱侵入 attach/detach | 候选中推进 | 未验证到新现实 | 已是主方向 | OpenClaw 明显偏离 | 用户侧污染与不可控回退 | P0 |
| KPI 单一真相 | 已实现 | 在线成立 | 一致 | 无重大冲突 | 低 | P1 |
| 产品/用户侧边界清楚 | 文档开始拆分 | 行为仍混杂 | 局部一致 | OpenClaw 把接入和使用混成一体 | 判断与验收失真 | P0 |
| 启动治理与当前 phase 对齐 | 未对齐 | 无法体现在运行 | phase5 缺 SOP | 启动规则失配 | 新会话容易误读 | P1 |

## 11. 优先级判断

### P0：必须先止血

1. **文档入口止血**
   README 中失效 SSOT 链接与不存在的 `CONSTITUTION.md` 必须先处理，否则连“从哪里开始读”都失真。

2. **现实对位止血**
   必须先确认 `~/.omnimemora/service/current` 与当前 repo 的关系，否则继续做行为验证会一直验错对象。

3. **控制面现实止血**
   必须先决定是否接纳当前工作区这条双开关路线，不能让未提交候选继续充当事实上的产品现实。

4. **OpenClaw 接入止血**
   这是当前最偏离“弱侵入”的实现面，必须优先纳入治理。

### P1：影响判断但不一定立刻阻塞运行

1. phase5 启动治理文档缺失  
2. `path_registry.py` 与主口径之间的 legacy 叙事残留  
3. 测试覆盖不足，特别是 control API 与 UI 联动闭环  

### 历史遗留：可后置归档

- phase3 审计沉淀
- 旧的 memory tool / optional call / `/memory/query` 中心叙事文档
- 已废止宪法及其延伸文档

## 12. 最终决策稿

### 12.1 这轮不应先做什么

当前不应先继续写功能，也不应先做大架构重构。  
原因不是功能复杂，而是：

- 产品现实未统一
- 代码现实未统一
- 运行现实未统一
- 文档现实未统一

### 12.2 这轮应先做什么

下一步顺序建议固定为：

1. **止血**
   先冻结单一主基线，清理 README 与上位真相引用失真，明确 phase5 缺失治理文档。

2. **收敛**
   把当前工作区的“双开关 + backup/restore + 非 auto-attach”候选线收敛成一个明确的仓库现实，或明确放弃，不能继续模糊悬挂。

3. **验证**
   在收敛后，用当前 repo 本身启动一套可验证实例，对 `/agents/control*`、attach/detach/restore、`18011` 单入口进行行为验证。

4. **再开发**
   只有在文档、代码、运行三者对齐后，再进入后续产品修复与架构推进。

### 12.3 一句话决策

> 当前最优先的不是“继续开发功能”，而是先把主基线、已提交现实、工作区候选现实和在线运行现实收敛为一个现实。

## 13. 证据摘要

### 静态证据

- 主基线文档已明确 `:18011` 唯一入口
- phase3 历史文档仍大量保留 `/memory/query` 主叙事
- `README` 指向不存在的 SSOT 文件

### 代码证据

- `HEAD` 中无 `/agents/control*`
- 工作区候选新增了 control API、routing state、backup/restore
- OpenClaw attach 仍明显强侵入

### 运行证据

- `18011` 在线
- `8765` 在线
- `5173` 未开
- 运行实例来自 `~/.omnimemora/service/current`
- 在线 `18011` 对 `/agents/control` 返回 `404`

### 自动化证据

- `go test ./...` in `4_core/local-runtime` 通过
- `python3 -m pytest --version` 失败，当前机器缺少 `pytest`

## 14. 审计结论

本次审计的核心结论不是“产品没做出来”，而是：

OmniMemora 当前同时存在四个现实：

- **主基线现实**
- **已提交代码现实**
- **未提交候选现实**
- **在线运行现实**

四者没有对齐。

因此，下一步正确顺序必须是：

> **止血 -> 收敛 -> 验证 -> 再开发**

在这之前，任何直接继续开发的动作，都会默认站在一个尚未被正式接纳的“候选现实”上继续放大漂移。
