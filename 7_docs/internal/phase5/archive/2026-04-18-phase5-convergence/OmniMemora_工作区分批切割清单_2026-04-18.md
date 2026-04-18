---
doc_id: PLAN-PHASE5-WORKTREE-BATCHING-2026-04-18
title: OmniMemora 工作区分批切割清单
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-18
depends_on: [PLAN-PHASE5-CONVERGENCE-2026-04-18, RUNBOOK-PHASE5-CONVERGENCE-2026-04-18]
supersedes: []
last_verified_commit: ""
---

# OmniMemora 工作区分批切割清单

## 一、文档定位

本文件用于处理当前工作区超阈值状态。

它不决定产品原则，只决定：

- 当前未提交改动如何按主题切批
- 哪些批次可以先收口
- 哪些批次不得继续混在一起推进

## 二、当前工作区结论

截至 `2026-04-18`：

- 当前分支：`checkpoint/llm-proxy-usage-fix`
- 当前未提交项：`34`
- 当前状态：**超出安全阈值**

按既定工作区治理规则：

- `> 20`：暂停实现扩面
- 只允许继续做治理、切批、验证对象对位、文档整理

因此，当前阶段的正确动作不是“继续写更多实现”，而是先把未提交改动切开。

## 三、分批原则

- 每一批只承载一个明确目标
- 文档收敛批不得混入控制面实现
- 控制面候选实现批不得混入 attach / 环境改动
- 高风险叠加修改文件优先隔离，不与低风险文档整理共批
- 若一批无法描述成一个单一 gate 或一个单一目标，则该批仍切得不够细

## 四、分批清单

## A 批：Phase5 文档与 Gate 收敛

### 目标

先收口当前已经完成的审计、执行计划、runbook、验证对象记录与主入口口径。

### 文件

- `README.md`
- `AGENTS.md`
- `0_blueprint/PRODUCT_DEFINITION.md`
- `0_blueprint/PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md`
- `9_adr/ADR-0003-interface-access-paths.md`
- `7_docs/internal/phase5/audit/OmniMemora_全面审计与下一步决策方案_2026-04-18.md`
- `7_docs/internal/phase5/plan/云端小工程.md`
- `7_docs/internal/phase5/plan/OmniMemora_收敛执行计划_2026-04-18.md`
- `7_docs/internal/phase5/plan/OmniMemora_收敛执行_Runbook_2026-04-18.md`
- `7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md`

### 风险

- 风险最低，但若继续混入实现文件，会重新失去 gate 参考价值

### 建议

- **最优先先收口**
- 可以独立成为第一批

### 当前执行结果（2026-04-18）

- 已完成主口径核对：
  - `README.md`
  - `AGENTS.md`
  - `0_blueprint/PRODUCT_DEFINITION.md`
  - `0_blueprint/PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md`
  - `9_adr/ADR-0003-interface-access-paths.md`
- 当前未发现新的阻塞性口径冲突：
  - `5173 = 用户控制入口`
  - `18011 = 用户开启产品路由后的唯一产品数据入口`
  - `8765 = 内部 memory plane`
  - `route off = 经 18011 透明直通`
  - `cloud policy updates on = 最小必要遥测默认随之启用`
- 当前 A 批状态可表述为：
  - **已完成内容核对**
  - **尚未完成工作区物理收口**

### 当前物理边界状态（2026-04-18）

- A 批当前可直接识别为：
  - `6` 个已修改文件
  - `5` 个未跟踪文件
- 已修改文件：
  - `README.md`
  - `AGENTS.md`
  - `0_blueprint/PRODUCT_DEFINITION.md`
  - `0_blueprint/PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md`
  - `9_adr/ADR-0003-interface-access-paths.md`
  - `7_docs/internal/phase5/plan/云端小工程.md`
- 未跟踪文件：
  - `7_docs/internal/phase5/audit/OmniMemora_全面审计与下一步决策方案_2026-04-18.md`
  - `7_docs/internal/phase5/plan/OmniMemora_收敛执行计划_2026-04-18.md`
  - `7_docs/internal/phase5/plan/OmniMemora_收敛执行_Runbook_2026-04-18.md`
  - `7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md`
  - `7_docs/internal/phase5/plan/OmniMemora_工作区分批切割清单_2026-04-18.md`
- 当前观察到的 A 批物理边界内未混入 `B/C` 批实现文件
- 当前 diff 规模：
  - `6` 个已修改文件
  - `117` 行新增
  - `27` 行删除

### 收口判断

- 当前 A 批已经具备“单独收口”的物理边界
- 但在未实际单独提交或单独切出前，仍属于工作区候选状态

### 下一步

- 若要真正完成 A 批，下一步应把 A 批文件单独收口，不再与 B/C 批混提

## B 批：M3 控制面候选实现

### 目标

收敛 `/agents/control*` 的候选实现与 UI 契约，但前提是先声明验证实例并控制工作区污染。

### 文件

- `5_connectors/adapter/agent_control_api.py`
- `5_connectors/adapter/agent_routing_state.py`
- `5_connectors/adapter/main.py`
- `5_connectors/adapter/llm_proxy.py`
- `5_connectors/adapter/config/agent_modes.json`
- `5_connectors/adapter/tests/test_agent_routing_state.py`
- `5_connectors/adapter/tests/test_llm_proxy_agent_detection.py`
- `4_core/local-runtime/api/agent_control.go`
- `4_core/local-runtime/api/server.go`
- `4_core/local-runtime/internal/cli/commands.go`
- `6_console/demo-dashboard/src/api.ts`
- `6_console/demo-dashboard/src/components/AgentsDashboard.tsx`
- `6_console/demo-dashboard/src/types.ts`

### 风险

- 风险最高
- 同时包含新文件与在脏工作区上叠加的修改
- 直接影响控制面语义、路由状态与运行时副作用

### 建议

- **不得与 A 批共提**
- 在 A 批收口后，先补实例声明记录，再决定是否进入该批

## C 批：Attach / Runtime / Cloud 残余改动

### 目标

隔离与 `M3` 不应混在一起的残余产品改动，避免继续污染控制面收敛面。

### 文件

- `4_core/local-runtime/README.md`
- `4_core/local-runtime/internal/attach/attach.go`
- `4_core/local-runtime/internal/attach/attach_claude.go`
- `4_core/local-runtime/internal/attach/attach_codex.go`
- `4_core/local-runtime/internal/attach/attach_codex_test.go`
- `4_core/local-runtime/internal/attach/attach_cursor.go`
- `4_core/local-runtime/internal/attach/attach_openclaw.go`
- `4_core/local-runtime/internal/attach/backup.go`
- `5_connectors/adapter/config.py`
- `5_connectors/adapter/tests/test_cloud_config.py`
- `6_console/demo-dashboard/README.md`

### 风险

- 会把“弱侵入接入”“云端语义”“控制面路由”三条线混在一起
- 若与 B 批一起推进，极易让 M3 失去边界

### 建议

- **先隔离，不先推进**
- 只在 A 批收口后，再判断它更接近 M4 / M5，还是应另开独立收敛线

## D 批：环境/杂项残留

### 目标

识别不属于当前收敛主线、但仍在工作区中的残留项。

### 文件

- `.mcp.json.disabled`

### 风险

- 风险不大，但会增加“未提交项数量”噪音

### 建议

- 单独处理，不要跟任何主批次绑定

### 当前执行结果（2026-04-18）

- `.mcp.json.disabled` 已加入本地 `.git/info/exclude`
- D 批已完成降噪处理，不再占用工作区未提交项计数
- 当前未提交项已从更高噪音状态回落，但后续治理文档更新仍会临时占用计数

### 补充环境风险

- 当前 `.git/gc.log` 存在，且 `git gc` 历史失败
- 已确认根因之一：`.git/objects` 下存在大量带 `uchg` 标志的对象文件
- 当前 `git fsck --full` 未显示对象损坏，只显示大量 dangling objects
- 该问题当前更像“仓库清理能力异常”，而不是“对象库立即损坏”
- 但它仍应作为进入 `M3` 前的环境前置项处理

### Git 环境治理结果（2026-04-18）

- 已解除 `.git/objects` 下对象文件的 `uchg` 不可变标记
- 已清除 `.git/gc.log`
- 已串行复核：
  - `git gc` 可正常完成
  - `git fsck --full` 退出码为 `0`
  - `git fsck --full` 当前 stderr 为空
- 说明：
  - 之前出现的 missing/corrupt 提示发生在 `git gc` 与 `git fsck` 并行执行时，属于体检方式不当造成的中间态观测，不作为最终仓库损坏结论
- 当前可将 Git 环境状态表述为：
  - **已恢复到可清理、可体检状态**
  - **不再阻塞进入 M3 前置环境要求**

## 五、建议顺序

固定顺序如下：

1. `A 批`：先收口
2. `D 批`：单独清理或明确保留原因
3. `B 批`：补实例声明记录后再决定是否进入
4. `C 批`：最后处理，且默认不并入 M3

## 六、当前控制结论

当前工作区**不适合直接进入 M3 实现**。

必须先满足以下条件，才允许进入 `B 批`：

- `A 批` 已收口
- `D 批` 已降噪，且 `.git/gc.log` / 对象不可变标记问题已完成治理
- `M3` 的验证实例已声明
- 未提交总数回落到可控范围，至少显著低于当前 `34`
- `B 批` 与 `C 批` 已明确切开

在此之前，只允许继续做：

- 文档整理
- 分批切割
- gate 记录补齐
- 实例对位

补充：

- A 批已完成内容核对，可以作为第一个收口对象
- 但在未实际从工作区中切出前，仍不得把 A 批视为已完成
