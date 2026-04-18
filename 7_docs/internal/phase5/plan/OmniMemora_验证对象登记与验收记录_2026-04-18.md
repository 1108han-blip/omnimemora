---
doc_id: RECORD-PHASE5-VALIDATION-OBJECTS-2026-04-18
title: OmniMemora 验证对象登记与验收记录
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5-CONVERGENCE-2026-04-18]
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

1. [OmniMemora 收敛执行计划（管理里程碑版）](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_收敛执行计划_2026-04-18.md)
2. 本文件
3. [OmniMemora 收敛执行 Runbook / Checklist](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_收敛执行_Runbook_2026-04-18.md)

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
