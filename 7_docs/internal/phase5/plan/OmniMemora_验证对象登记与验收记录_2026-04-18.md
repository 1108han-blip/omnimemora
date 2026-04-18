---
doc_id: RECORD-PHASE5-VALIDATION-OBJECTS-2026-04-18
title: OmniMemora 验证对象登记与验收记录
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5_5-PRODUCT-HARDENING-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora 验证对象登记与验收记录

## 一、文档定位

本文件是 `Gate B: 环境 Gate` 的正式记录载体。

用途只有两个：

- 固定当前阶段允许使用的验证对象分类
- 为后续 gate 留下可复用、可追溯、不可混验的验收记录模板

若本文件与执行计划或 runbook 表述冲突，以：

1. [OmniMemora Decision Carrier / Control-Plane Decoupling 执行计划](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Decision_Carrier_Control_Plane_Decoupling_执行计划_2026-04-18.md)
2. 本文件
3. [OmniMemora Decision Carrier / Control-Plane Decoupling Runbook](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Decision_Carrier_Control_Plane_Decoupling_Runbook_2026-04-18.md)

的优先顺序解释。

## 二、当前冻结规则

### 2.1 允许的验证对象分类

- `仓库候选实例`
- `外部运行实例`

### 2.2 当前默认对象

- 未额外声明时，`运行实例` 默认指向 `外部运行实例`
- 当前 `外部运行实例` 来源固定为 `~/.omnimemora/service/current`
- 当前 repo 工作区只代表 `仓库现实` 与 `仓库候选现实`，不自动代表在线运行实例

### 2.3 禁止混验规则

- 一条验证记录只能绑定一个验证对象分类
- 仓库代码阅读结论不得与外部运行实例行为拼接为同一条“已验证”结论
- 未写明 `实例分类 / 实例路径或来源 / 结论适用范围` 的记录无效
- 未显式启动 `仓库候选实例` 前，不得把当前 repo 改动当作行为验证结论
- 不得把 `~/.omnimemora/service/current` 的行为当作当前 repo 已生效的证据

## 三、验收记录模板

后续所有行为验证记录至少必须包含以下字段：

| 字段 | 要求 |
|------|------|
| 记录编号 | 唯一编号 |
| 日期 | 绝对日期 |
| 实例分类 | `仓库候选实例` 或 `外部运行实例` |
| 实例路径/来源 | 明确路径、启动来源或运行来源 |
| 验证动作 | 本次实际执行的命令、访问、观察或代码读取 |
| 观察结果 | 原始观察到的事实 |
| 结论适用范围 | 只能写“候选成立/不成立”或“外部运行实例成立/不成立” |
| 备注 | 可为空；用于写明限制或未覆盖项 |

## 四、当前基线记录

### RECORD-B-001

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-001` |
| 日期 | `2026-04-18` |
| 实例分类 | `外部运行实例` |
| 实例路径/来源 | `~/.omnimemora/service/current` |
| 验证动作 | 在本机执行 `ls -ld ~/.omnimemora/service/current`；同时复核 phase5 审计文档中已记录的运行命令来源 |
| 观察结果 | `~/.omnimemora/service/current` 目录存在；审计文档已记录运行链路来自 `~/.omnimemora/service/current/tools/omnimemora-runtime serve` 与 `~/.omnimemora/service/current/tools/_run_adapter.py` |
| 结论适用范围 | `外部运行实例成立`：当前在线运行实例来源固定为 `~/.omnimemora/service/current`，不得反推当前 repo 已具备同等运行行为 |
| 备注 | 本记录用于冻结外部运行实例来源，不用于证明当前候选改动已上线 |

### RECORD-B-002

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-002` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区 |
| 验证动作 | 在当前 repo 执行 `git status --short` |
| 观察结果 | 当前工作区存在已修改与未跟踪文件，说明仓库候选现实与已提交现实未收敛；且未记录从当前 repo 显式启动的候选实例 |
| 结论适用范围 | `候选成立`：当前 repo 只能作为仓库/候选现实，不得直接当作在线运行实例验证对象 |
| 备注 | 在从当前 repo 显式启动候选实例前，不得用其代码差异替代行为验证 |

### RECORD-B-003

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-003` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区 |
| 验证动作 | 在当前 repo 执行针对 M3 控制面相关 10 个文件的 `git status --short` |
| 观察结果 | 新文件：`4_core/local-runtime/api/agent_control.go`、`5_connectors/adapter/agent_control_api.py`、`5_connectors/adapter/agent_routing_state.py`。叠加修改：`4_core/local-runtime/api/server.go`、`4_core/local-runtime/internal/cli/commands.go`、`5_connectors/adapter/llm_proxy.py`、`5_connectors/adapter/main.py`、`6_console/demo-dashboard/src/api.ts`、`6_console/demo-dashboard/src/components/AgentsDashboard.tsx`、`6_console/demo-dashboard/src/types.ts` |
| 结论适用范围 | `候选成立`：M3 控制面当前处于“部分新建 + 部分叠加修改”的候选现实；此记录只用于入口风险划分，不用于证明控制面已完成或已上线 |
| 备注 | 该记录用于区分新文件与在脏工作区上继续叠加的文件，便于后续避免污染工作区 |

### RECORD-B-004

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-004` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区 |
| 验证动作 | 复核执行计划、runbook 与当前验证对象规则，判断是否已具备进入 M3 行为验收的实例条件 |
| 观察结果 | 当前仅完成 M3 入口准备；尚未新增“从当前 repo 显式启动的仓库候选实例”记录，也未声明将使用外部运行实例还是候选实例做控制面验收 |
| 结论适用范围 | `候选不成立`：当前只足以支持“先补文档记录、暂不进入 M3 实现/验收”，不足以声明 M3 已开始正式验收 |
| 备注 | 进入 M3 前，必须先追加一条新的实例声明记录，写明本次控制面验收到底绑定哪个验证对象 |

### RECORD-B-005

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-005` |
| 日期 | `2026-04-18` |
| 实例分类 | `外部运行实例` |
| 实例路径/来源 | `~/.omnimemora/service/current` 对应的 `http://127.0.0.1:18011` |
| 验证动作 | 访问 `GET http://127.0.0.1:18011/agents/control` 与 `GET http://127.0.0.1:18011/proxy/status` |
| 观察结果 | `/agents/control` 返回 `404` 与 `{\"detail\":\"Not Found\"}`；`/proxy/status` 返回 `200`，说明当前在线网关可用，但外部运行实例未暴露 M3 所需控制面接口 |
| 结论适用范围 | `外部运行实例不成立`：当前外部运行实例不适合作为 `M3` 控制面验收对象；后续 `M3` 验收应绑定 `仓库候选实例`，不得把外部运行实例当作控制面已落地的证据 |
| 备注 | 本记录只决定 `M3` 验收对象选择，不证明当前仓库候选实例已可用 |

### RECORD-B-006

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-006` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；候选启动尝试使用 adapter `18012` 与 runtime `18765` |
| 验证动作 | 1. 使用当前源码构建 `tools/omnimemora-runtime`；2. 以 `RUNTIME_BIN=... RUNTIME_PORT=18765 PORT=18012 ./start.sh` 启动候选实例；3. 读取 runtime / adapter 启动日志 |
| 观察结果 | adapter 可在 `18012` 启动，但 runtime 仍尝试绑定 `127.0.0.1:8765` 并失败；日志显示 `Server listening on 127.0.0.1:8765` 后立即报 `bind: address already in use`。说明当前 `start.sh -> runtime serve` 路径未把候选 runtime 端口安全带入进程，候选实例无法在不干扰现网 runtime 的前提下独立拉起 |
| 结论适用范围 | `候选不成立`：当前仓库候选实例尚不具备安全启动条件，因此 `M3` 仍不能进入正式验收；若要继续，只能先修复候选 runtime 的双端口启动路径 |
| 备注 | 该阻塞属于候选实例启动链路问题，不是外部运行实例问题，也不直接等同于控制面语义错误 |

### RECORD-B-007

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-007` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；候选实例以 adapter `18012`、runtime `18765`、隔离数据目录 `.tmp/candidate-runtime-data` 启动 |
| 验证动作 | 1. 构建当前源码 `tools/omnimemora-runtime`；2. 以 `OMNIMEMORA_RUNTIME_DATA_DIR=$PWD/.tmp/candidate-runtime-data OMNIMEMORA_DATA_DIR=$PWD/.tmp/candidate-runtime-data RUNTIME_BIN=$PWD/tools/omnimemora-runtime RUNTIME_PORT=18765 PORT=18012 bash ./start.sh` 启动候选实例；3. 访问 `GET http://127.0.0.1:18012/agents/control`、`GET http://127.0.0.1:18012/proxy/status`；4. 读取 `.tmp/candidate-runtime-data/runtime.state` |
| 观察结果 | 候选 runtime 与 adapter 均通过健康检查；`/agents/control` 返回 `200` 与 agent 列表；`/proxy/status` 返回 `200`；隔离状态文件写入 `port=18765`，未污染现网默认 runtime state |
| 结论适用范围 | `候选成立`：当前仓库候选实例已具备安全启动条件，并且可作为 `M3` 控制面正式验收对象 |
| 备注 | 本记录解除 `RECORD-B-006` 所述启动阻塞，但不等同于 `M3` 已完成，只表示可以进入 `M3` 正式验收准备 |

### RECORD-B-008

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-008` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；候选实例以 adapter `18012`、runtime `18765`、隔离数据目录 `.tmp/candidate-runtime-data` 启动 |
| 验证动作 | 1. 访问 `GET http://127.0.0.1:18012/agents/control` 读取当前状态；2. 依次调用 `POST /agents/control/disable` 与 `POST /agents/control/enable`；3. 每次调用后直接读取 `5_connectors/adapter/config/agent_modes.json`；4. 再次访问 `GET /agents/control` 复核返回状态 |
| 观察结果 | `disable` 后 API 返回 `routing_enabled=false`，并且 `agent_modes.json` 中 `openclaw` 写为 `off`；随后 `enable` 后 API 返回 `routing_enabled=true`，并且 `agent_modes.json` 中 `openclaw` 写为 `force_if_possible`；受控复现下未再次出现“API 状态与磁盘状态分叉” |
| 结论适用范围 | `候选成立`：在当前仓库候选实例上，`enable/disable` 已同时影响控制面返回值和 route state 持久化文件；此前观察到的持久化不一致暂未复现，不能再作为当前 `M3` 阻塞项 |
| 备注 | 本记录只覆盖 `openclaw` 的候选实例闭环；不自动外推到其他 family，也不等同于 `M3` 全部验收完成 |

### RECORD-B-009

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-009` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；验证动作在 `4_core/local-runtime/internal/attach` 的隔离测试环境中执行，`HOME` 指向临时目录 |
| 验证动作 | 1. 运行 `go test ./internal/attach -run 'TestAttachThenDetachCodexRestoresOriginalConfig' -v`；2. 复核 [attach_codex_test.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/internal/attach/attach_codex_test.go) 与 [attach.go](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime/internal/attach/attach.go) 中 `DetachAgent -> RestoreBackup` 路径 |
| 观察结果 | 定向测试通过：`AttachCodex()` 先创建备份，`DetachCodex()` 后原始 `config.toml` 被完整恢复，备份文件被移除；代码路径显示通用 `DetachAgent()` 先尝试 `RestoreBackup(agent)`，恢复成功则直接返回，不再继续做片段删除 |
| 结论适用范围 | `候选成立`：当前仓库候选实现已具备 `uninstall/detach -> restore original config` 的测试级证据，可作为 `M3` 的恢复语义支撑 |
| 备注 | 本记录是隔离测试证据，不是对用户真实机器配置的在线卸载验证；若后续需要产品级在线验收，应在不污染用户真实配置的前提下另补候选实例记录 |

### RECORD-B-010

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-010` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；候选实例以 adapter `18012`、runtime `18765`、隔离数据目录 `.tmp/candidate-runtime-data-master` 启动；上游指向 `http://127.0.0.1:19001/v1` |
| 验证动作 | 1. 补入 [runtime_bridge.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/runtime_bridge.py) 以恢复 compile-path 依赖；2. 运行 `python3 -m unittest 5_connectors.adapter.tests.test_llm_proxy_agent_detection 5_connectors.adapter.tests.test_agent_control_api 5_connectors.adapter.tests.test_agent_routing_state`；3. 顺序调用 `POST /agents/control/enable`、读取 `agent_modes.json`、调用 `POST /llm/chat`、读取 `/compile/events?limit=1`、再调用 `POST /agents/control/disable` 并再次读取 `agent_modes.json` |
| 观察结果 | `runtime_bridge` 补入后 `5_connectors.adapter.main` 可正常 import，相关 unittest 通过；`enable(openclaw)` 后 `agent_modes.json` 写为 `force_if_possible`；随后发往 `http://127.0.0.1:18012/llm/chat` 的请求返回 `200`，最新 compile event 的 `trace_id=0855ff3cc8f6`，`compile_status=compile_success`、`compile_path=runtime_compile`、`compile_reason=runtime_compile`；最后 `disable(openclaw)` 后 `agent_modes.json` 恢复为 `off` |
| 结论适用范围 | `候选成立`：当前仓库候选实例下，`openclaw` 在 `route=on` 时已进入 compile path，不再因缺失 `runtime_bridge` 而失败，也不再落入 `agent_route_disabled` 的透明直通路径 |
| 备注 | 本记录证明的是 `route=on -> compile path` 与状态落盘闭环在候选实例上成立；不自动外推到其他 family，也不等同于产品级卸载恢复在线验收完成 |

### RECORD-B-011

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-011` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；候选实例以 adapter `18012`、runtime `18765`、隔离数据目录 `.tmp/candidate-runtime-data-codex-online`、隔离 `HOME=.tmp/candidate-home-codex-online` 启动 |
| 验证动作 | 1. 在隔离 `HOME` 下预写入 `.codex/config.toml` 原始内容 `model_provider = "openai"`；2. 通过 `POST http://127.0.0.1:18012/agents/control/install` 安装 `codex_cli`；3. 读取 `GET /agents/control` 与隔离 `config.toml`；4. 通过 `POST http://127.0.0.1:18012/agents/control/uninstall` 卸载 `codex_cli`；5. 再次读取隔离 `config.toml` 与备份文件状态 |
| 观察结果 | `install` 后控制卡中 `codex_cli.installed=true`，隔离 `config.toml` 被写为 `model_provider = "omnimemora"` 并包含 `[model_providers.omnimemora]`；`uninstall` 后控制卡中 `codex_cli.installed=false`，隔离 `config.toml` 恢复为原始 `model_provider = "openai"`，备份文件 `config.toml.omnimemora.backup` 被移除 |
| 结论适用范围 | `候选成立`：当前仓库候选实例下，`/agents/control/install -> /uninstall` 已能在线完成 `codex_cli` 的接入与恢复原上游配置闭环，可作为 `uninstall -> restore original upstream config` 的更高层级候选证据 |
| 备注 | 本记录绑定的是隔离 `HOME` 的候选实例在线验收，不代表真实用户 `~/.codex` 已被在线验证；同时也修正了 Codex `installed` 判定必须识别 provider-based 配置而非仅识别旧 MCP 标记 |

### RECORD-B-012

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-012` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；候选实例以 adapter `18012`、runtime `18765`、隔离数据目录 `.tmp/candidate-runtime-data-claude-online`、隔离 `HOME=.tmp/candidate-home-claude-online` 启动 |
| 验证动作 | 1. 在隔离 `HOME` 下预写入 `.claude/settings.json` 原始内容 `{\"theme\":\"dark\"}`；2. 通过 `POST http://127.0.0.1:18012/agents/control/install` 安装 `claude_code`；3. 读取 `GET /agents/control` 与隔离 `settings.json`；4. 通过 `POST http://127.0.0.1:18012/agents/control/uninstall` 卸载 `claude_code`；5. 再次读取隔离 `settings.json` 与备份文件状态 |
| 观察结果 | `install` 后控制卡中 `claude_code.installed=true`，隔离 `settings.json` 新增 `memory.provider=omnimemora`、`endpoint=http://127.0.0.1:18011` 等字段，同时保留原有 `theme=dark`；`uninstall` 后控制卡中 `claude_code.installed=false`，隔离 `settings.json` 恢复为原始仅含 `theme=dark`，备份文件 `settings.json.omnimemora.backup` 被移除 |
| 结论适用范围 | `候选成立`：当前仓库候选实例下，`claude_code` 已能通过 `/agents/control/install -> /uninstall` 在线完成接入与恢复原始配置闭环，可作为 `uninstall -> restore original upstream config` 的补充候选证据 |
| 备注 | 本记录绑定的是隔离 `HOME` 的候选实例在线验收，不代表真实用户 `~/.claude` 或 `~/.claude.json` 已被在线验证；同时满足“测试不能影响在使用中的 Codex 本体”约束，因为本轮未触碰真实 `~/.codex` |

### RECORD-B-013

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-013` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；候选实例以 adapter `18012`、runtime `18765`、隔离数据目录 `.tmp/candidate-runtime-data-cursor-online-2`、隔离 `HOME=.tmp/candidate-home-cursor-online` 启动 |
| 验证动作 | 1. 在隔离 `HOME` 下预写入 `.cursor/config/settings.json` 原始内容 `{\"theme\":\"midnight\"}`；2. 通过 `POST http://127.0.0.1:18012/agents/control/install` 安装 `cursor`；3. 读取 `GET /agents/control` 与隔离 `settings.json`；4. 通过 `POST http://127.0.0.1:18012/agents/control/uninstall` 卸载 `cursor`；5. 再次读取隔离 `settings.json` 与备份文件状态 |
| 观察结果 | `install` 后控制卡中 `cursor.installed=true`，隔离 `settings.json` 新增 `memory.provider=omnimemora`、`endpoint=http://127.0.0.1:18011` 等字段，同时保留原有 `theme=midnight`；`uninstall` 后控制卡中 `cursor.installed=false`，隔离 `settings.json` 恢复为原始仅含 `theme=midnight`，备份文件 `settings.json.omnimemora.backup` 被移除 |
| 结论适用范围 | `候选成立`：当前仓库候选实例下，`cursor` 已能通过 `/agents/control/install -> /uninstall` 在线完成接入与恢复原始配置闭环，可作为 `uninstall -> restore original upstream config` 的补充候选证据 |
| 备注 | 本记录绑定的是隔离 `HOME` 的候选实例在线验收，不代表真实用户 `.cursor` 配置已被在线验证；同时未触碰真实 `~/.codex`，满足“测试不能影响在使用中的 Codex 本体”约束 |

### RECORD-B-014

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-014` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区 |
| 验证动作 | 1. 读取 [config.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/config.py) 中 `CloudIntegrationConfig` 默认值；2. 读取 [cloud/models.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/cloud/models.py)、[cloud/usage_reporter.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/cloud/usage_reporter.py)、[main.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/main.py) 的 usage telemetry 路径；3. 运行 `python3 -m unittest 5_connectors.adapter.tests.test_cloud_config 5_connectors.adapter.tests.test_cloud_usage_schema` |
| 观察结果 | `CloudIntegrationConfig` 已固定为：纯本地模式默认 `enabled=false` 且 `usage_report_enabled=false`；开启云端策略更新后默认 `usage_report_enabled=true`。当前 `UsageReport` schema 包含 `request_id / route / version / saved_tokens / savings_ratio / optimization_enabled / latency_ms / error_code / timestamp`，不再包含 `tenant`。测试通过，证明“云端更新默认启用最小 usage telemetry”与“tenant 不进入 payload”均成立 |
| 结论适用范围 | `候选成立`：当前仓库候选实现已具备 `M5` 所需的最小数据集合边界，且上报范围已收敛到低敏元数据集合 |
| 备注 | 本记录是代码与测试对位证据，不代表真实云端服务已接收这些字段；云端服务上线前仍需单独验证服务端契约 |

### RECORD-B-015

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-015` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；候选实例以 adapter `18012`、runtime `18765`、隔离数据目录 `.tmp/candidate-runtime-data-b2` 启动；上游 stub 指向 `http://127.0.0.1:19001/v1` |
| 验证动作 | 1. 以隔离 runtime data 启动候选实例；2. `enable(openclaw)` 后顺序请求 `POST /llm/chat`，读取最新 compile event；3. 杀掉候选 runtime，仅保留 adapter，观察 `GET /health`、`GET /agents/control`、`POST /memory/search`、`POST /llm/chat`；4. 再停掉候选 gateway，观察 `GET /health` 与 `GET /agents/control` 的可达性 |
| 观察结果 | healthy 分支下，`openclaw` 的最新 compile event 为 `runtime_compile / compile_success`。能力层故障注入后，`/health` 返回 `degraded`，`/agents/control` 返回 `503`，`/memory/search` 返回 `500`，但 `/llm/chat` 仍可返回上游结果。入口层故障注入后，`18012` 整体不可达，现有产品接口无法返回任何决策状态 |
| 结论适用范围 | `候选成立`：Track B 当前在候选实例上已具备 healthy 分支基线与能力层故障探测能力，但尚未具备统一的 `degraded-capability` 状态输出，也尚未具备 `user-decision-required` 的产品接口承载 |
| 备注 | 本记录证明的是 Track B 的“当前缺口基线”，不是自愈功能已存在的证据；验证过程未触碰真实 `18011`、未修改真实用户配置 |

### RECORD-B-016

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-016` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实现` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；状态输出实现位于 [track_b_status.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/track_b_status.py) 与 [status_api.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/status_api.py) |
| 验证动作 | 1. 新增 Track B 状态语义模块，基于 backend health 与 route request 推导 `healthy / degraded-capability / recovering-gateway / user-decision-required`；2. 暴露 `GET /proxy/system-status`，并为 `GET /proxy/status?include_system=true` 增加可选聚合输出；3. 运行 `python3 -m unittest 5_connectors.adapter.tests.test_track_b_status 5_connectors.adapter.tests.test_agent_control_api 5_connectors.adapter.tests.test_llm_proxy_agent_detection` |
| 观察结果 | 新接口输出已包含 `status / gateway_health / capability_health / routing_requested / routing_effective / user_action_required / recommended_action / error_code`。默认情况下，gateway 存活且 backend 健康时输出 `healthy`；backend 不健康时输出 `degraded-capability`，推荐动作为 `degrade_to_passthrough`；若后续状态机写入 override 文件，则同一接口可承载 `recovering-gateway` 与 `user-decision-required`，且不会自动引出 `restore backup` 或 `uninstall/detach`。相关 unittest 全部通过 |
| 结论适用范围 | `候选成立`：Track B 已具备最小统一状态输出接口，可表达当前观测状态，并为后续自愈编排提供非破坏性的状态承载面 |
| 备注 | 本记录覆盖的是“状态输出前置层”，不是自动修复或用户决策流程已完整上线；`user-decision-required` 目前仍需未来状态机显式写入 override 才会出现 |

### RECORD-B-017

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-017` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实现` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；override 写入入口位于 [status_api.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/status_api.py)，控制面消费位于 [agent_control_api.py](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/5_connectors/adapter/agent_control_api.py) |
| 验证动作 | 1. 为 Track B 状态 override 增加受 `X-Internal-Token / OMNIMEMORA_INTERNAL_API_TOKEN` 保护的 `POST /proxy/system-status/override` 与 `DELETE /proxy/system-status/override`；2. 将 `GET /agents/control` 与 `POST /agents/control/rescan` 顶层补入 `system_status`；3. 运行 `python3 -m unittest 5_connectors.adapter.tests.test_track_b_status 5_connectors.adapter.tests.test_agent_control_api 5_connectors.adapter.tests.test_llm_proxy_agent_detection` |
| 观察结果 | override 仅接受允许字段并写入 `track_b_status.json`，未知字段被忽略；未配置 internal token 时写入口返回 `500`，token 不匹配时返回 `403`。控制面聚合输出已包含顶层 `system_status`，因此 UI/控制面读取 `GET /agents/control` 即可获得 Track B 当前统一状态，无需自行拼装 runtime health 与 route state |
| 结论适用范围 | `候选成立`：Track B 已具备受限的 override 写入边界与明确的控制面消费路径，后续自愈编排可通过该入口写入 `recovering-gateway / user-decision-required`，且不会直接越权触发 `restore backup` 或 `uninstall/detach` |
| 备注 | 本记录覆盖的是“override 前置基础设施”，不是完整的自愈执行器；实际写入责任方仍需在后续 Track B 编排实现中明确 |

### RECORD-B-018

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-018` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以 `PORT=18013 RUNTIME_PORT=18766 OMNIMEMORA_RUNTIME_DATA_DIR=.tmp/candidate-runtime-data-b3 OMNIMEMORA_DATA_DIR=.tmp/candidate-runtime-data-b3 TRACK_B_RUNTIME_RESTART_ATTEMPTS=1 TRACK_B_RECOVERY_SETTLE_SECONDS=4 bash ./start.sh` 启动 |
| 验证动作 | 1. 正常启动候选 runtime 与 adapter；2. 读取初始 `GET /proxy/system-status`，确认 `healthy`；3. 读取 `.tmp/candidate-runtime-data-b3/runtime.state` 中的 runtime pid 并手动 `kill`；4. 轮询 `GET /proxy/system-status` 观察状态变化；5. 观察 start.sh 会话输出中的 `Runtime unhealthy, attempting restart` 与 `Runtime recovered` |
| 观察结果 | runtime 被杀后，状态先进入 `degraded-capability`，随后进入 `recovering-gateway`，再在恢复窗口结束后回到 `healthy`。会话输出显示 supervisor 实际执行了一次 runtime 重拉起并成功通过 `/health`。由于 `track_b_status.json` 路径现在跟随 `OMNIMEMORA_DATA_DIR`，候选实例 override 不再污染共享默认目录 |
| 结论适用范围 | `候选成立`：Track B 的能力层最小自愈闭环已在候选实例上成立，能够完成 `degraded-capability -> recovering-gateway -> healthy`，且仍未引入自动 `restore backup`、自动 `uninstall/detach` |
| 备注 | 本记录只覆盖 `start.sh` 管理的能力层恢复路径，不覆盖 gateway 自身不可达时的 `user-decision-required` 分支；入口层故障仍需后续单独实现与验证 |

### RECORD-B-019

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-019` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；runtime 重新编译后，以 `PORT=18014 RUNTIME_PORT=18767 OMNIMEMORA_RUNTIME_DATA_DIR=.tmp/candidate-runtime-data-b4 OMNIMEMORA_DATA_DIR=.tmp/candidate-runtime-data-b4 bash ./start.sh` 启动 |
| 验证动作 | 1. 先验证 `GET http://127.0.0.1:18767/gateway/status` 返回 `healthy`；2. 通过 `lsof -iTCP:18014` 找到候选 adapter pid 并手动 `kill`；3. 轮询 runtime internal plane 的 `GET /gateway/status`；4. 读取 `GET /dashboard` 中的故障提示文本 |
| 观察结果 | adapter 被杀后，runtime internal plane 仍保持可用，`/gateway/status` 在短暂窗口后进入 `user-decision-required`，字段为 `gateway_health=unhealthy`、`user_action_required=true`、`recommended_action=disable_route_or_uninstall`、`error_code=gateway_unreachable`。runtime dashboard 顶部同步出现 `Gateway status: user-decision-required` 与 `User decision required before changing install state.` 提示 |
| 结论适用范围 | `候选成立`：Track B 入口层故障现在已有最小 `user-decision-required` 承载面，且该承载面位于 internal plane（runtime `/gateway/status` + dashboard），不依赖已失效的 adapter |
| 备注 | 本记录证明的是“承载与提示”已存在，不代表用户动作接口已完备；当前仍未提供 UI 内直接执行 `disable route` 或 `uninstall/detach` 的 runtime 侧动作接口 |

### RECORD-B-020

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-020` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以 `PORT=18015 RUNTIME_PORT=18768 OMNIMEMORA_RUNTIME_DATA_DIR=.tmp/candidate-runtime-data-b5 OMNIMEMORA_DATA_DIR=.tmp/candidate-runtime-data-b5 OMNIMEMORA_AGENT_MODES_PATH=.tmp/candidate-runtime-data-b5/agent_modes.json bash ./start.sh` 启动 |
| 验证动作 | 1. 预写隔离 `agent_modes.json` 为 `openclaw=force_if_possible`；2. 验证 runtime `POST /gateway/decision/disable-route` 在线可用；3. 手动杀掉候选 adapter，使 runtime 进入 `user-decision-required`；4. 再通过 runtime internal plane 调用 `POST /gateway/decision/disable-route`；5. 读取隔离 `agent_modes.json` |
| 观察结果 | 在 adapter 存活与 adapter 已失效两种情况下，runtime `POST /gateway/decision/disable-route` 都返回 `200`；adapter 失效后，runtime `GET /gateway/status` 维持 `user-decision-required`，同时隔离 `agent_modes.json` 被写为 `openclaw=off`。因此入口层故障下，用户仍可通过 internal plane 明确执行“关闭路由、保留 attach”动作 |
| 结论适用范围 | `候选成立`：Track B 现在已有最小用户动作接口，可在 gateway 故障时通过 runtime internal plane 执行 `disable-route`，且不依赖 adapter 存活 |
| 备注 | 本记录只覆盖 `disable-route`；`/gateway/decision/uninstall` 已实现但未做在线候选验证，以避免在未完全隔离 agent config 前触碰真实用户配置 |

### RECORD-B-021

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-021` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-claude-uninstall`、`PORT=18016`、`RUNTIME_PORT=18769`、`OMNIMEMORA_RUNTIME_DATA_DIR=.tmp/candidate-runtime-data-b6`、`OMNIMEMORA_AGENT_MODES_PATH=.tmp/candidate-runtime-data-b6/agent_modes.json` 启动；仅操作隔离 `.claude/settings.json` 与隔离 backup 目录 |
| 验证动作 | 1. 预写隔离 Claude Code 配置 `theme=dark` 与隔离 `agent_modes.json (claude_code=force_if_possible)`；2. 通过候选 adapter `POST /agents/control/install` 安装 `claude_code`，确认 backup 已生成；3. 手动杀掉候选 adapter，使 runtime 进入 `user-decision-required`；4. 通过 runtime internal plane 调用 `POST /gateway/decision/uninstall`；5. 读取隔离 `.claude/settings.json`、隔离 backup 目录与隔离 `agent_modes.json` |
| 观察结果 | `install` 后隔离 Claude 配置被注入 `memory.provider=omnimemora`，同时生成 `claude.backup / claude.meta.json`。adapter 掉线后，runtime `GET /gateway/status` 进入 `user-decision-required`。随后 runtime `POST /gateway/decision/uninstall` 返回 `200`，并且隔离 `.claude/settings.json` 恢复为原始 `theme=dark`；隔离 backup 目录被清空；隔离 `agent_modes.json` 同步从 `force_if_possible` 变为 `off` |
| 结论适用范围 | `候选成立`：Track B 现在可在入口层故障下通过 runtime internal plane 执行显式 `uninstall`，且动作会同时完成 `restore backup` 与 `route state -> off`，不依赖 adapter 存活，也不触碰真实用户配置 |
| 备注 | 本记录使用的是隔离 `HOME` 与隔离 agent config，只验证 `Claude Code` 路径；按当前安全约束，未对 `codex` 执行同类在线验证 |

### RECORD-B-022

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-022` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-claude-uninstall`、`PORT=18016`、`RUNTIME_PORT=18769`、`OMNIMEMORA_RUNTIME_DATA_DIR=.tmp/candidate-runtime-data-b6` 启动 |
| 验证动作 | 1. 通过候选 adapter `POST /agents/control/install` 安装 `claude_code`；2. 手动杀掉候选 adapter，使 runtime 进入 `user-decision-required`；3. 读取 runtime `GET /dashboard` HTML；4. 检查 dashboard 中是否出现最小用户动作承载元素 |
| 观察结果 | 当 gateway 故障后，runtime dashboard 除了显示 `Gateway status: user-decision-required` 外，还出现 `Family ID` 输入框、`Disable Route` 按钮、`Uninstall` 按钮，以及对应的 `runGatewayAction('disable-route') / runGatewayAction('uninstall')` 前端调用逻辑。说明 internal plane 已不只是文本提示，还具备最小可操作动作入口 |
| 结论适用范围 | `候选成立`：Track B 现在在 runtime dashboard 上已有最小 UI 动作承载，可在入口层故障时为用户提供显式的 `disable-route / uninstall` 操作入口 |
| 备注 | 本记录验证的是 dashboard HTML 承载面，不代表完整 GUI/5173 已完成同等级接入；动作实际仍落到 runtime internal plane 的 `/gateway/decision/*` 接口 |

### RECORD-B-023

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-023` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-claude-uninstall`、`PORT=18016`、`RUNTIME_PORT=18769`、`OMNIMEMORA_RUNTIME_DATA_DIR=.tmp/candidate-runtime-data-b6` 启动 |
| 验证动作 | 1. 启动隔离候选实例；2. 手动杀掉候选 adapter，使 runtime 进入 `user-decision-required`；3. 读取 runtime `GET /gateway/status` 返回的 JSON 字段 |
| 观察结果 | gateway 故障后，runtime `GET /gateway/status` 返回：`status=user-decision-required`、`status_source=gateway-exit-monitor`、`transition_reason=gateway_process_exited`。说明入口层故障状态不仅有结果态，还明确带出了状态写入责任方和转移原因 |
| 结论适用范围 | `候选成立`：Track B 当前已经把最小状态机责任边界写进运行时状态面；`gateway-exit-monitor` 作为写入方只产生 `user-decision-required`，和既定状态机定义一致 |
| 备注 | 本记录只覆盖 `gateway-exit-monitor` 分支；`runtime-restart-monitor` 的恢复/降级写入边界由代码测试和 `start.sh` 实现约束共同保证 |

## 五、Gate B 完成判据

当满足以下条件时，`Gate B` 可视为通过：

- 本文件存在并被执行计划与 runbook 引用
- `RECORD-B-001` 与 `RECORD-B-002` 已建立
- 后续新增行为验证记录沿用本文件模板

## 六、下一步使用规则

- 进入 `M3 / M4 / M5` 前，先在本文件追加对应验证记录
- 若后续显式启动 `仓库候选实例`，必须新增一条候选实例启动记录，再开始候选行为验证
- 若外部运行实例来源改变，必须先更新本文件，再继续验收
- 当前冻结结论：
  - `M3` 控制面验收不得绑定外部运行实例
  - `M3` 若继续推进，只能绑定显式启动后的 `仓库候选实例`
  - `RECORD-B-006` 的候选启动阻塞已由 `RECORD-B-007` 解除
  - `RECORD-B-008` 已确认当前候选实例下 `openclaw` 的 `enable/disable` 可正确落盘
  - `RECORD-B-009` 已确认 `uninstall/detach -> restore original config` 的候选实现具备测试级证据
  - `RECORD-B-010` 已确认当前候选实例下 `openclaw` 的 `route=on` 会进入 `runtime_compile`，`runtime_bridge` 缺口已解除
  - `RECORD-B-011` 已确认当前候选实例下 `codex_cli` 可通过 `/agents/control/install -> /uninstall` 在线恢复原始 provider 配置
  - `RECORD-B-012` 已确认当前候选实例下 `claude_code` 可通过 `/agents/control/install -> /uninstall` 在线恢复原始 settings 配置
  - `RECORD-B-013` 已确认当前候选实例下 `cursor` 可通过 `/agents/control/install -> /uninstall` 在线恢复原始 settings 配置
  - `RECORD-B-014` 已确认当前候选实现下云端 usage telemetry 仅包含最小必要元数据，且不再包含 `tenant`
  - `RECORD-B-015` 已确认 Track B 在候选实例上的 healthy / capability failure / gateway failure 三类当前基线行为
  - `RECORD-B-016` 已确认 Track B 最小统一状态输出接口已落地，可承载 `degraded-capability / recovering-gateway / user-decision-required`
  - `RECORD-B-017` 已确认 Track B override 写入边界与控制面消费路径已落地
  - `RECORD-B-018` 已确认 Track B 能力层最小自愈闭环已在候选实例上成立
  - `RECORD-B-019` 已确认 Track B 入口层故障已有最小 `user-decision-required` 承载面
  - `RECORD-B-020` 已确认 Track B 可在入口层故障时通过 runtime internal plane 执行 `disable-route`
  - `RECORD-B-021` 已确认 Track B 可在入口层故障时通过 runtime internal plane 执行 `uninstall`，并同步完成 `restore backup` 与 `route state -> off`
  - `RECORD-B-022` 已确认 Track B 在 runtime dashboard 上已有最小 UI 动作承载，可在入口层故障时提供 `disable-route / uninstall` 入口
  - `RECORD-B-023` 已确认 Track B 运行时状态面现在显式输出 `status_source / transition_reason`，可区分故障状态责任方
  - `RECORD-B-024` 已确认 Track B 现在会把 runtime 用户动作写成共享决策文件，并由 `start.sh` 接管 gateway 重启编排；当前证据为代码与单元测试级，候选实例需补重测
  - `RECORD-B-025` 已确认本机候选实例阻塞来自 adapter 运行依赖缺失，而非 Track B 状态机逻辑；`start.sh` 已补前置依赖预检
  - `RECORD-B-026` 已确认先前候选实例重测失败的真实根因是 runtime 二进制未随源码更新自动重建；`start.sh` 现已补“源码较新则自动重建 runtime”约束，并在候选实例上完成 `gateway failure -> user action -> gateway restart` 闭环
  - `RECORD-B-027` 已确认 Track B 的 gateway 自动修复窗口已在候选实例上成立；gateway 退出后会先自动重启，再在窗口耗尽后才进入用户决策态
  - `RECORD-B-028` 已确认当自动修复被显式关闭时，Track B 会直接进入 `user-decision-required`，并带出精确的 `transition_reason`
  - `RECORD-B-029` 已确认当恢复窗口过短时，Track B 会以 `gateway_auto_recovery_window_expired` 进入用户决策态
  - `RECORD-B-030` 已确认当重试次数耗尽时，Track B 会以 `gateway_auto_recovery_attempts_exhausted` 进入用户决策态

### RECORD-B-024

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-024` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与单元测试级` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区 |
| 验证动作 | 1. 实现 runtime `/gateway/decision/disable-route` 与 `/gateway/decision/uninstall` 写入共享 `gateway_decision.json`；2. 更新 `start.sh`，在 adapter 退出进入 `user-decision-required` 后轮询该决策文件，并在用户动作后触发 gateway 重启；3. 运行 `go test ./tests ./api` 与 `bash -n start.sh` |
| 观察结果 | Go 测试已确认 runtime 动作接口在写入 `agent_modes.json` / restore backup 之外，还会写入 `gateway_decision.json`；shell 语法检查通过。`start.sh` 现在在 gateway 退出后不再只停留在等待态，而是会读取用户决策、写入 `recovering-gateway`、尝试重启 adapter，并在失败时回写 `user-decision-required` |
| 结论适用范围 | `代码与单元级成立`：Track B 已具备“用户动作 -> 决策文件 -> gateway 重启编排 -> 成功/失败转移”的完整高层编排路径 |
| 备注 | 当前机器上的一次候选实例重测未成功拉起隔离实例，现象更像既有启动环境问题，尚不足以否定本批实现；该分支仍需补一条候选实例级闭环记录 |

### RECORD-B-025

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-025` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例 / 启动阻塞定位` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `PORT=18017`、`RUNTIME_PORT=18770`、隔离 `HOME` 与隔离数据目录启动候选实例 |
| 验证动作 | 1. 以隔离端口启动候选实例；2. 读取 `start.sh` stdout 与 `tools/verification/logs/adapter_start.err.log`；3. 复核 runtime 与 adapter 启动状态 |
| 观察结果 | runtime 在 `18770` 可正常启动并通过 `/health`；adapter 在 `_run_adapter.py` 入口直接因 `ModuleNotFoundError: No module named 'uvicorn'` 退出。因此当前候选实例无法补齐在线闭环的直接原因是 adapter 运行依赖缺失，而不是 Track B 状态机或 gateway 决策编排逻辑错误 |
| 结论适用范围 | `候选阻塞已定位`：本机当前需要先满足 adapter Python 依赖，才能继续 Track B 的候选实例级闭环验收 |
| 备注 | 为避免再次出现“runtime 已启动但 adapter 半失败”的假象，`start.sh` 已补 `uvicorn` 前置依赖预检；这不改变产品语义，只改善候选实例诊断路径 |

### RECORD-B-026

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-026` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例 / 隔离在线闭环` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-trackb-restart-9`、`PORT=18025`、`RUNTIME_PORT=18778`、`OMNIMEMORA_DATA_DIR=.tmp/candidate-data-trackb-restart-9` 启动 |
| 验证动作 | 1. 更新 `start.sh`，当 `4_core/local-runtime` 源码比 `tools/omnimemora-runtime` 更新时自动执行 `go build`；2. 启动隔离候选实例；3. 手动杀掉候选 adapter，使系统进入 `user-decision-required`；4. 通过 runtime internal plane `POST /gateway/decision/disable-route` 写入用户动作；5. 观察 supervisor 日志、状态文件和端口恢复 |
| 观察结果 | `track_b_supervisor.log` 明确记录：`runtime binary is stale -> building runtime binary -> adapter exited -> raw decision lines captured -> gateway restart requested -> gateway restart succeeded`。候选实例数据目录中 `track_b_status.json` 被清除，`gateway_decision.json` 被消费后删除，`agent_modes.json` 持久化为 `claude_code=off`，端口 `18025` 上的 adapter 重新监听成功 |
| 结论适用范围 | `候选成立`：Track B 现在已具备 `gateway failure -> user action -> gateway restart` 的候选实例级闭环证据；先前重测失败不是状态机错误，而是 runtime 二进制与当前源码脱节导致的假阴性 |
| 备注 | 本记录使用隔离 `Claude Code` 配置与隔离数据目录，不触碰真实 `codex`；当前候选实例仍依赖本机 user-site 中的 `uvicorn`，因此通过 `PYTHONPATH` 继承该依赖，仅用于验证，不改变产品语义 |

### RECORD-B-027

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-027` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例 / 隔离在线闭环` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-trackb-auto-1`、`PORT=18026`、`RUNTIME_PORT=18779`、`OMNIMEMORA_DATA_DIR=.tmp/candidate-data-trackb-auto-1` 启动 |
| 验证动作 | 1. 启动隔离候选实例；2. 手动杀掉候选 adapter，模拟 gateway 入口层故障；3. 不执行任何用户动作；4. 观察 `track_b_supervisor.log`、端口恢复和 `track_b_status.json` 状态 |
| 观察结果 | supervisor 记录：`adapter exited -> gateway auto recovery attempt=1/2 -> adapter start requested -> gateway auto recovery succeeded on attempt=1`。`track_b_status.json` 被清除，端口 `18026` 上的 adapter 自动恢复监听成功，`GET /health` 返回 `system_status.status=healthy` |
| 结论适用范围 | `候选成立`：Track B 现在已具备“gateway 退出后先进入自动修复窗口，自动恢复成功则不进入用户决策态”的候选实例证据 |
| 备注 | 本记录仍使用隔离 `Claude Code` 配置与隔离数据目录，不触碰真实 `codex`；当前自动修复窗口的次数与时长由 `TRACK_B_GATEWAY_RESTART_ATTEMPTS / TRACK_B_GATEWAY_RECOVERY_WINDOW_SECONDS` 控制 |

### RECORD-B-028

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-028` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例 / 隔离在线闭环` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-trackb-disabled-1`、`PORT=18027`、`RUNTIME_PORT=18780`、`OMNIMEMORA_DATA_DIR=.tmp/candidate-data-trackb-disabled-1` 启动 |
| 验证动作 | 1. 以 `TRACK_B_SELF_HEAL_ENABLED=0` 启动隔离候选实例；2. 手动杀掉候选 adapter；3. 读取 supervisor 日志、`track_b_status.json` 和 runtime `GET /gateway/status` |
| 观察结果 | supervisor 记录：`adapter exited -> gateway auto recovery skipped because TRACK_B_SELF_HEAL_ENABLED=0 -> gateway auto recovery exhausted result=disabled`。状态文件和 runtime internal plane 一致返回：`status=user-decision-required`、`transition_reason=gateway_auto_recovery_disabled`、`error_code=gateway_unreachable` |
| 结论适用范围 | `候选成立`：Track B 当前不仅区分“自动恢复成功”与“进入用户决策”，还会对“自动恢复被关闭”给出明确的终止原因，便于后续 UI 和运维诊断消费 |
| 备注 | 本记录验证的是关闭自动修复的失败分支；`window_expired / attempts_exhausted` 仍属于后续可补的更细分候选实例证据 |

### RECORD-B-029

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-029` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例 / 隔离在线闭环` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-trackb-expire-3`、`PORT=18030`、`RUNTIME_PORT=18783`、`OMNIMEMORA_DATA_DIR=.tmp/candidate-data-trackb-expire-3` 启动 |
| 验证动作 | 1. 以 `TRACK_B_GATEWAY_RESTART_ATTEMPTS=2`、`TRACK_B_GATEWAY_HEALTH_TIMEOUT_SECONDS=2`、`TRACK_B_GATEWAY_RECOVERY_WINDOW_SECONDS=1` 启动隔离候选实例；2. 启动后临时移走 `tools/_run_adapter.py`，确保 gateway 自动重启失败；3. 手动杀掉候选 adapter；4. 读取 supervisor 日志、状态文件和 runtime `GET /gateway/status` |
| 观察结果 | supervisor 记录：`gateway auto recovery attempt=1/2 -> failed on attempt=1 -> backoff=1s -> gateway auto recovery window expired after 1 seconds -> result=window-expired`。状态文件和 runtime internal plane 一致返回：`status=user-decision-required`、`transition_reason=gateway_auto_recovery_window_expired`、`error_code=gateway_restart_window_expired` |
| 结论适用范围 | `候选成立`：Track B 现在可区分“恢复窗口过短/已过期”这一失败分支，并给出明确终止原因 |
| 备注 | 本记录通过临时移走 `_run_adapter.py` 制造可控的 gateway 重启失败，验证完成后文件已恢复；不触碰真实用户环境 |

### RECORD-B-030

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-030` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例 / 隔离在线闭环` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-trackb-exhaust-2`、`PORT=18031`、`RUNTIME_PORT=18784`、`OMNIMEMORA_DATA_DIR=.tmp/candidate-data-trackb-exhaust-2` 启动 |
| 验证动作 | 1. 以 `TRACK_B_GATEWAY_RESTART_ATTEMPTS=1`、`TRACK_B_GATEWAY_HEALTH_TIMEOUT_SECONDS=2`、`TRACK_B_GATEWAY_RECOVERY_WINDOW_SECONDS=30` 启动隔离候选实例；2. 启动后临时移走 `tools/_run_adapter.py`，确保唯一一次 gateway 自动重启失败；3. 手动杀掉候选 adapter；4. 读取 supervisor 日志、状态文件和 runtime `GET /gateway/status` |
| 观察结果 | supervisor 记录：`gateway auto recovery attempt=1/1 -> failed on attempt=1 -> result=attempts-exhausted`。状态文件和 runtime internal plane 一致返回：`status=user-decision-required`、`transition_reason=gateway_auto_recovery_attempts_exhausted`、`error_code=gateway_restart_attempts_exhausted` |
| 结论适用范围 | `候选成立`：Track B 现在可区分“重试次数耗尽”这一失败分支，并给出明确终止原因 |
| 备注 | 本记录同样通过临时移走 `_run_adapter.py` 制造可控失败，验证完成后文件已恢复；不触碰真实用户环境 |

### RECORD-B-031

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-031` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与单元级` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区 |
| 验证动作 | 1. 在 `track_b_orchestrator.py` 增加联合恢复 contract 合并规则；2. 在 `start.sh` 中为 `disable-route / uninstall` 增加启动前后 route-off 持久化约束；3. 在 runtime `/gateway/decision/*` 响应消息中固定恢复语义；4. 运行 `python3 -m unittest 5_connectors.adapter.tests.test_track_b_status 5_connectors.adapter.tests.test_agent_control_api 5_connectors.adapter.tests.test_llm_proxy_agent_detection`、`go test ./tests ./api`、`bash -n start.sh` |
| 观察结果 | Python 31 项测试全部通过，Go `./tests ./api` 通过，`start.sh` 语法检查通过。新增断言覆盖两类关键场景：1. route 已关闭时，陈旧 override 不得把系统重新抬回 `routing_requested=true / routing_effective=true`；2. `user-decision-required` 的 gateway 级故障优先级高于能力层故障，不会因 route 已关闭而被静默清除。`start.sh` 现在在消费 `disable-route / uninstall` 决策前后都会验证目标 family 的 route 是否已持久化为 `off`，否则拒绝继续恢复并回写 `user-decision-required`。runtime `/gateway/decision/*` 返回文案已与 contract 对齐：`disable-route` 成功后收敛到健康 passthrough，`uninstall` 成功后保持在非产品增强路径 |
| 结论适用范围 | `代码与单元级成立`：Track B 的联合恢复优先级 contract 已落到 `start.sh / track_b_orchestrator.py / runtime decision flow`，但能力层故障与入口层故障的更高层联合恢复编排仍是后续批次 |
| 备注 | 本记录不包含新的候选实例在线闭环；该批次只收实现级 contract，不扩大验证面 |

### RECORD-B-032

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-032` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与单元级` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区 |
| 验证动作 | 1. 在 `start.sh` 中增加 gateway 恢复后的 runtime postcheck；2. 当 gateway 已恢复但 runtime 仍不健康且 route 仍开启时，写回 `degraded-capability` 而不是直接清空状态；3. 运行 `bash -n start.sh`、`python3 -m unittest 5_connectors.adapter.tests.test_track_b_status 5_connectors.adapter.tests.test_agent_control_api 5_connectors.adapter.tests.test_llm_proxy_agent_detection`、`go test ./tests ./api` |
| 观察结果 | 脚本语法检查通过，Python 31 项测试全部通过，Go `./tests ./api` 通过。`start.sh` 现在在两类 gateway 恢复成功分支后都会执行统一 postcheck：若 runtime 已健康则清状态；若 runtime 仍不健康但 route 已关闭，则也清状态并回到 passthrough；若 runtime 仍不健康且 route 仍开启，则写入 `status=degraded-capability`、`transition_reason=gateway_recovered_runtime_still_unhealthy` 或 `gateway_recovered_after_user_action_runtime_still_unhealthy`，避免出现“gateway 恢复即假健康”的短暂错误窗口 |
| 结论适用范围 | `代码与单元级成立`：Track B 现在已具备入口层恢复成功后对能力层健康的最小联合恢复后检查，但尚缺新的候选实例级联合恢复证据 |
| 备注 | 本记录仍不新增在线候选实例验证；验证面控制在当前计划内的脚本与回归测试 |

### RECORD-B-033

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-033` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例 / 隔离在线闭环` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-trackb-combined-4`、`OMNIMEMORA_DATA_DIR=.tmp/candidate-data-trackb-combined-4`、`PORT=18035`、`RUNTIME_PORT=18788` 启动；仅临时继承 `PYTHONPATH=/Users/sc/Library/Python/3.9/lib/python/site-packages` 以满足本机已有 `uvicorn` 依赖，不改变项目 Python 基线 |
| 验证动作 | 1. 以 `TRACK_B_RUNTIME_RESTART_ATTEMPTS=0` 启动隔离候选实例，并让 `claude_code` route state 保持 `force_if_possible`；2. 手动杀掉候选 runtime，再手动杀掉候选 adapter，制造“能力层先失效、入口层随后失效”的联合故障；3. 等待 gateway 自动恢复；4. 读取 `GET /proxy/system-status`、`GET /health`、隔离 `track_b_status.json` 与 supervisor 日志 |
| 观察结果 | gateway 在 `18035` 上自动恢复监听成功，runtime 仍保持失效；`/proxy/system-status` 与 `/health.system_status` 一致返回 `status=degraded-capability`、`status_source=runtime-restart-monitor`、`transition_reason=gateway_recovered_runtime_still_unhealthy`、`routing_requested=true`、`routing_effective=false`、`recommended_action=degrade_to_passthrough`。隔离 `track_b_status.json` 与 supervisor 日志也一致记录了 `gateway recovered but runtime remains unhealthy; degrading capability`。隔离 `agent_modes.json` 保持 `claude_code=force_if_possible`，未被错误改写为 `off` |
| 结论适用范围 | `候选成立`：Track B 现在已具备 `route=on` 下“入口层恢复成功但能力层仍失效”时收敛到 `degraded-capability` 的联合恢复证据，不会误清成健康 passthrough |
| 备注 | 本记录对应的隔离 `.tmp/candidate-*` 工件已在验证后清理；在验证前还发现一个独立启动回归：`main.py` 中 diagnostics surface 配置调用顺序错误导致 `SUPPORT_SCHEMA_VERSION` 未定义，该问题已在本批修复，不属于联合恢复语义本身 |

### RECORD-B-034

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-034` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库候选实例 / 隔离在线闭环` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；以隔离 `HOME=.tmp/candidate-home-trackb-combined-off-1`、`OMNIMEMORA_DATA_DIR=.tmp/candidate-data-trackb-combined-off-1`、`PORT=18036`、`RUNTIME_PORT=18789` 启动；仅临时继承 `PYTHONPATH=/Users/sc/Library/Python/3.9/lib/python/site-packages` 以满足本机已有 `uvicorn` 依赖 |
| 验证动作 | 1. 让 `claude_code` route state 保持 `off`；2. 以 `TRACK_B_RUNTIME_RESTART_ATTEMPTS=0` 启动隔离候选实例；3. 手动杀掉候选 runtime，再手动杀掉候选 adapter，制造联合故障；4. 读取 `GET /proxy/system-status`、`GET /health`、隔离 `track_b_status.json`、`agent_modes.json` 与 supervisor 日志 |
| 观察结果 | gateway 在 `18036` 上自动恢复监听成功；最终 `GET /proxy/system-status` 与 `GET /health.system_status` 一致返回 `status=healthy`、`routing_requested=false`、`routing_effective=false`、`recommended_action=none`，隔离 `track_b_status.json` 已不存在，隔离 `agent_modes.json` 仍保持 `claude_code=off`。supervisor 日志显示 gateway 自动恢复成功；本次运行最终未留下 `degraded-capability` 残留 |
| 结论适用范围 | `候选成立`：Track B 现在已具备 `route=off` 下联合故障后的稳定收敛证据，最终会回到健康 passthrough，而不会把 route-off 用户置于故障状态 |
| 备注 | 该记录证明的是 `route=off` 的稳定收敛结果，不主张 runtime 必然持续失效；对应隔离 `.tmp/candidate-*` 工件已在验证后清理 |

### RECORD-B-035

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-035` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 定向风险判断` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；基于 `gateway_decision.go`、`routes.go`、`attach.DetachAgent()`、既有 `RECORD-B-021/B-022/B-033/B-034` 综合判断 |
| 验证动作 | 1. 复核 runtime `/gateway/decision/uninstall` 的执行前提；2. 复核 runtime dashboard 对 `Disable Route / Uninstall` 的承载方式；3. 对照既有候选实例证据，判断 `uninstall` 在联合故障场景下的可执行边界 |
| 观察结果 | 当前 `uninstall` 用户动作的唯一正式承载面是 runtime internal plane：`POST /gateway/decision/uninstall` 与 runtime dashboard 按钮都依赖 `8765` 存活。既有 `RECORD-B-021` 已证明当 `gateway dead + runtime alive` 时，`uninstall` 可执行并能完成 `route off + detach + restore backup`。但当 `runtime` 也已不可用时，当前架构下不存在独立于 runtime 的第二决策承载面，因此无法安全执行同一动作 |
| 结论适用范围 | `结构性限制已确认`：本阶段不应把 `uninstall + runtime already unavailable` 当作“再补一条普通验证”来继续硬做；这条路径需要未来把 internal decision carrier 从 runtime 能力层进一步解耦后再实现 |
| 备注 | 这不是当前代码的单点 bug，而是现阶段 mixed architecture 的边界；后续若进入模块拆分，应把该问题并入新的 decision carrier / control-plane decoupling 子工程 |

### RECORD-B-036

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-036` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/control_carrier_store.go`、`gateway_status.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 `gateway/status` 与 `gateway/decision/*` 的文件承载逻辑从 gateway handler 文件中抽离为独立 control-carrier store；2. 运行 `gofmt -w api/control_carrier_store.go api/gateway_status.go`；3. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `control_carrier_store.go`，统一承载 `gatewayStatusPayload`、`gatewayDecisionPayload`、状态文件路径、决策文件路径以及读写逻辑；`gateway_status.go` 退回为薄文件，不再承担 decision/status 文件持久化职责。`go test ./tests ./api` 全部通过 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第一批低风险逻辑解耦已经落地，decision/control carrier 的文件承载职责已从 runtime gateway handler 中分离出来，且未引入 runtime API 行为回归 |
| 备注 | 本记录证明的是逻辑边界收敛与测试级稳定性，不等同于 `runtime dead + uninstall` 已解决 |

### RECORD-B-037

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-037` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/control_carrier_surface.go`、`routes.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 `handleGatewayStatus`、`handleGatewayDecisionDisableRoute`、`handleGatewayDecisionUninstall` 以及相关 agent-modes helper 从原有 `gateway_*` / `routes.go` 文件中抽离为独立 `control_carrier_surface.go`；2. 运行 `gofmt -w api/control_carrier_store.go api/control_carrier_surface.go api/routes.go`；3. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `control_carrier_surface.go`，统一承载 control-carrier 的 HTTP surface；`routes.go` 不再内联 `gateway/status` handler，原有 `gateway_decision.go` 与 `gateway_status.go` 被清退。`go test ./tests ./api` 全部通过 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第二批低风险逻辑解耦已经落地，decision/control carrier 的 HTTP surface 已与 runtime capability 主 surface 形成更清晰的模块入口，且未引入 runtime API 行为回归 |
| 备注 | 本记录证明的是 control-carrier surface 的模块化边界收敛，不等同于极端故障承载问题已完全解决 |

### RECORD-B-038

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-038` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/control_carrier_dashboard.go`、`routes.go` 与既有 runtime dashboard tests |
| 验证动作 | 1. 将 runtime dashboard 中与 `gateway/status`、`user-decision-required`、`runGatewayAction(...)` 相关的 control-carrier 呈现与脚本抽离为独立 `control_carrier_dashboard.go`；2. 运行 `gofmt -w api/control_carrier_dashboard.go api/routes.go`；3. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `control_carrier_dashboard.go`，承载 gateway alert HTML 与 gateway action script；`routes.go` 不再内联该部分 control-carrier 片段。`go test ./tests ./api` 全部通过，既有 dashboard 相关测试未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第三批低风险逻辑解耦已经落地，runtime dashboard 中的 decision/control 呈现职责已与 capability dashboard 主体进一步分离，且未引入回归 |
| 备注 | 本记录证明的是 dashboard 级 control-carrier 片段解耦，不等同于 runtime dead 极端承载问题已解决 |

### RECORD-B-039

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-039` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/control_carrier_surface.go`、`server.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 runtime server 中 `GET /gateway/status`、`POST /gateway/decision/disable-route`、`POST /gateway/decision/uninstall` 的路由注册从 `server.go` 抽离为 `registerControlCarrierRoutes(...)`；2. 运行 `gofmt -w api/control_carrier_surface.go api/server.go`；3. 运行 `go test ./tests ./api` |
| 观察结果 | `server.go` 不再内联 control-carrier route 注册，转而通过 `registerControlCarrierRoutes(...)` 完成 wiring；`go test ./tests ./api` 全部通过，runtime API 行为未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第四批低风险逻辑解耦已经落地，control-carrier 的 server wiring 已与 runtime capability 主路由注册形成更清晰的入口边界 |
| 备注 | 本记录证明的是 route registration 层面的逻辑边界收敛，不等同于极端故障承载问题已完全解决 |

### RECORD-B-040

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-040` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/agent_control.go`、`server.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 runtime low-frequency install layer 的 `/agents/control*` 路由注册从 `server.go` 抽离为 `registerInstallControlRoutes(...)`；2. 运行 `gofmt -w api/agent_control.go api/server.go`；3. 运行 `go test ./tests ./api` |
| 观察结果 | `server.go` 不再内联 `/agents/control*` 的 route wiring，转而通过 `registerInstallControlRoutes(...)` 完成低频 install layer 注册；`go test ./tests ./api` 全部通过，runtime API 行为未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第五批低风险逻辑解耦已经落地，runtime install-control route wiring 已与 capability 主路由注册形成更清晰的入口边界 |
| 备注 | 本记录证明的是 low-frequency install layer wiring 的边界收敛，不等同于 control-plane 承载问题已最终解决 |

### RECORD-B-041

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-041` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/bootstrap_surface.go`、`server.go`、`routes.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 `POST /internal/metrics` 的 bootstrap/internal metrics 承载从 `routes.go` 抽离为独立 `bootstrap_surface.go`；2. 通过 `registerBootstrapRoutes(...)` 从 `server.go` 注册该入口；3. 运行 `gofmt -w api/bootstrap_surface.go api/server.go api/routes.go`；4. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `bootstrap_surface.go`，`server.go` 不再内联 bootstrap route 注册，`routes.go` 不再承载 bootstrap metrics handler。`go test ./tests ./api` 全部通过，runtime API 行为未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第六批低风险逻辑解耦已经落地，bootstrap/internal metrics 的 route 与 handler 已从 runtime capability 主体中进一步分离 |
| 备注 | 本记录证明的是 bootstrap/internal metrics 入口边界的收敛，不等同于极端故障承载问题已完全解决 |

### RECORD-B-042

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-042` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/operator_dashboard_surface.go`、`server.go`、`routes.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 runtime operator dashboard surface 从 `routes.go` 抽离为独立 `operator_dashboard_surface.go`；2. 通过 `registerOperatorDashboardRoutes(...)` 从 `server.go` 注册 `GET /dashboard`；3. 运行 `gofmt -w api/operator_dashboard_surface.go api/server.go api/routes.go`；4. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `operator_dashboard_surface.go`，承载 dashboard route、hero、trend、efficiency 与 runtime status card 相关 HTML 组装逻辑；`server.go` 不再内联 dashboard route wiring，`routes.go` 不再承载 operator dashboard 主 surface。`go test ./tests ./api` 全部通过，既有 gateway alert / dashboard 相关测试未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第七批低风险逻辑解耦已经落地，runtime operator dashboard 主 surface 已与 capability handler 主体进一步分离 |
| 备注 | 本记录证明的是 operator dashboard surface 的模块边界收敛，不等同于 control-plane 已物理解耦 |

### RECORD-B-043

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-043` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/bootstrap_state.go`、`server.go`、`bootstrap_surface.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 runtime bootstrap/control 状态从 `Server` 主结构中抽离为独立 `bootstrapState`；2. 通过 `newBootstrapState()` 在 `server.go` 中注入；3. 由 `bootstrap_surface.go` 通过独立 state carrier 写入 bootstrap success；4. 运行 `gofmt -w api/bootstrap_state.go api/server.go api/bootstrap_surface.go`；5. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `bootstrap_state.go`，`Server` 不再直接承载 `bootstrapSuccess` 布尔状态，而是通过 `bootstrap *bootstrapState` 间接承载 bootstrap/control 状态；`go test ./tests ./api` 全部通过，未引入 runtime API 回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第八批低风险逻辑解耦已经落地，runtime bootstrap/control 状态已进一步从 server 主结构中分离 |
| 备注 | 本记录证明的是 bootstrap state carrier 的边界收敛，不等同于 runtime/control-plane 已物理解耦 |

### RECORD-B-044

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-044` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/control_carrier_dashboard.go`、`operator_dashboard_surface.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 operator dashboard 对 gateway status / action script 的直接消费收敛为统一 `buildControlCarrierDashboardFragment()`；2. 运行 `gofmt -w api/control_carrier_dashboard.go api/operator_dashboard_surface.go`；3. 运行 `go test ./tests ./api` |
| 观察结果 | operator dashboard surface 不再直接调用 `loadGatewayStatus()` 或 `gatewayActionScriptHTML()`，改为只消费 control-carrier dashboard fragment；`go test ./tests ./api` 全部通过，既有 dashboard / gateway alert 行为未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第九批低风险逻辑解耦已经落地，operator dashboard 与 control-carrier 呈现细节的耦合进一步降低 |
| 备注 | 本记录证明的是 control-carrier fragment 消费边界的收敛，不等同于 control-plane 已独立为新宿主 |

### RECORD-B-045

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-045` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/root_surface.go`、`server.go`、`mcp.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 `/` 的 operator-facing redirect surface 从 `mcp.go` 抽离为独立 `root_surface.go`；2. 通过 `registerRootRoutes(...)` 从 `server.go` 注册 `GET /`；3. 运行 `gofmt -w api/root_surface.go api/server.go api/mcp.go`；4. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `root_surface.go`，`mcp.go` 不再同时承载 MCP transport 与 `/` redirect/operator 入口；`go test ./tests ./api` 全部通过，未出现 runtime API 回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第十批低风险逻辑解耦已经落地，root/operator surface 已与 MCP transport 主体进一步分离 |
| 备注 | 本记录证明的是 root/operator 入口边界的收敛，不等同于 runtime decision/control 已物理解耦 |

### RECORD-B-046

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-046` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/mcp_state.go`、`server.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 MCP startup error 状态从 `Server` 主结构中抽离为独立 `mcpState`；2. 通过 `newMCPState()` 在 `server.go` 中注入；3. 保持既有 `setMCPStartupError(...)` / `getMCPStartupError()` API 不变；4. 运行 `gofmt -w api/mcp_state.go api/server.go`；5. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `mcp_state.go`，`Server` 不再直接持有 `mcpLastStartupError` 字段，而是通过 `mcpState` 间接承载；`go test ./tests ./api` 全部通过，MCP 相关 metrics / handler 行为未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第十一批低风险逻辑解耦已经落地，MCP startup error 状态已进一步从 server 主结构中分离 |
| 备注 | 本记录证明的是 MCP startup error state carrier 的边界收敛，不等同于 MCP session registry 已完成解耦 |

### RECORD-B-047

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-047` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/mcp_transport_state.go`、`server.go`、`mcp.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 MCP session registry 从 `Server` 主结构中抽离为独立 `mcpTransportState`；2. 通过 `newMCPTransportState()` 在 `server.go` 中注入；3. 由 `mcp.go` 通过 `putSession/getSession/deleteSession` 使用 transport state；4. 运行 `gofmt -w api/mcp_transport_state.go api/server.go api/mcp.go`；5. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `mcp_transport_state.go`，`Server` 不再直接持有 `mcpMu` 和 `mcpSessions`，而是通过 `mcpTransport` 间接承载 MCP session registry；`go test ./tests ./api` 全部通过，MCP transport 行为未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第十二批低风险逻辑解耦已经落地，MCP session registry 已进一步从 server 主结构中分离 |
| 备注 | 本记录证明的是 MCP transport session registry 的边界收敛，不等同于 MCP metrics / counters 已完成解耦 |

### RECORD-B-048

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-048` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/mcp_metrics_state.go`、`server.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 MCP metrics / counters 从 `Server` 主结构中抽离为独立 `mcpMetricsState`；2. 通过 `newMCPMetricsState()` 在 `server.go` 中注入；3. 保持既有 `recordMCPHandshake(...)`、`recordMCPToolCallByName(...)`、`getMCPStats()`、`getMCPDetailedStats()` 调用面不变；4. 运行 `gofmt -w api/mcp_metrics_state.go api/server.go`；5. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `mcp_metrics_state.go`，`Server` 不再直接持有 handshake/tool-call/write/search counters，而是通过 `mcpMetrics` 间接承载；`go test ./tests ./api` 全部通过，MCP metrics / dashboard / handler 行为未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第十三批低风险逻辑解耦已经落地，MCP metrics / counter state 已进一步从 server 主结构中分离 |
| 备注 | 本记录证明的是 MCP metrics state carrier 的边界收敛，不等同于 MCP transport / protocol surface 已完全独立 |

### RECORD-B-049

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-049` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/mcp_protocol.go`、`mcp.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 MCP protocol types 与 tool response helpers 从 `mcp.go` 抽离为独立 `mcp_protocol.go`；2. 保持 handler 与 tool dispatch 行为不变；3. 运行 `gofmt -w api/mcp_protocol.go api/mcp.go`；4. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `mcp_protocol.go`，`mcp.go` 不再同时承载 protocol type definitions 与 response helper；`go test ./tests ./api` 全部通过，MCP transport / tool dispatch 行为未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第十四批低风险逻辑解耦已经落地，MCP protocol surface 已进一步从 MCP handler 主体中分离 |
| 备注 | 本记录证明的是 MCP protocol type/helper 边界的收敛，不等同于 MCP handler / transport lifecycle 已完成物理解耦 |

### RECORD-B-050

| 字段 | 内容 |
|------|------|
| 记录编号 | `RECORD-B-050` |
| 日期 | `2026-04-18` |
| 实例分类 | `仓库现实 / 代码与回归测试` |
| 实例路径/来源 | `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora` 当前工作区；涉及 `4_core/local-runtime/api/mcp_tool_catalog.go`、`mcp.go` 与既有 runtime API tests |
| 验证动作 | 1. 将 `tools/list` 的静态 MCP tool catalog 与默认 MCP scope 构造从 `mcp.go` 抽离为独立 `mcp_tool_catalog.go`；2. 保持 handler 与 tool dispatch 行为不变；3. 运行 `gofmt -w api/mcp_tool_catalog.go api/mcp.go`；4. 运行 `go test ./tests ./api` |
| 观察结果 | runtime 侧新增独立 `mcp_tool_catalog.go`，`mcp.go` 不再内联静态 tool catalog 和默认 scope 构造；`go test ./tests ./api` 全部通过，MCP tools/list 与 tool dispatch 行为未出现回归 |
| 结论适用范围 | `仓库现实成立`：本阶段 `Track B` 的第十五批低风险逻辑解耦已经落地，MCP 静态 catalog / default scope surface 已进一步从 MCP handler 主体中分离 |
| 备注 | 本记录证明的是 MCP 静态 catalog 边界的收敛，不等同于 MCP tool dispatch 本体已完成解耦 |
