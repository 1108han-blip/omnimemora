# OmniMemora 本机稳定化与迁移执行计划（Phase 3）

---

## 一、目标定义

本阶段目标：

> **将当前本机运行实例打磨为"可迁移版本"，并在新 Mac 上一次通过验收。**

执行路径：

```
稳定化 → 可迁移 → 上线验收
```

---

## 二、阶段 1：本机稳定化（Stabilization）

## 目标

> 系统不再依赖偶然成功，而是具备稳定运行能力

---

## 1. 启动与运行稳定

### 必须达成

* [x] Runtime 可连续启动 / 停止 ≥ 20 次无异常（2026-04-12 已完成 20 次重启循环）
* [ ] 端口冲突有明确错误提示（非 silent fail）
* [ ] 缺配置时返回可读错误信息（非崩溃）
* [x] 重启后数据保持一致（write → query → restart → query 已通过）

### 验收标准

```
启动 → 写入 → 查询 → 重启 → 再查询 → 数据一致
```

---

## 2. 核心接口完整性

### 必测接口

* [ ] `/memory/write`
* [ ] `/memory/query` / search
* [ ] 空结果返回正常（非异常）
* [ ] `/health` 返回真实状态
* [ ] 错误码统一（401 / 404 / 501）

### 要求

> 行为必须稳定一致，而非"偶尔成功"

---

## 3. Scope 治理（核心红线）

### 必须验证

* [ ] agent scope 隔离
* [ ] workspace scope 隔离
* [ ] user scope 隔离
* [ ] custom scope（如存在）行为正确
* [ ] sharing mode（isolated / shared）有效

### 验收标准

```
不同 agent / workspace 不得读取非授权数据
```

---

## 4. Token Savings 链路（核心能力）

### 必须达成

* [ ] 每次 query 产生 metering event
* [ ] raw / compressed / saved 数值合理
* [ ] 无重复计数（重试不重复）
* [ ] 日志可追踪完整计算过程

### 验收标准

```
能够解释每次 token 节省的来源
```

---

## 5. 异常场景覆盖

### 必测场景

* [ ] runtime 挂掉
* [ ] connector 断开
* [ ] 空 memory
* [ ] 超大输入
* [ ] 非法 scope

---

## 三、阶段 2：可迁移版本（Migration-Ready）

## 目标

> 从"能跑"转变为"可复制部署"

---

## 1. 项目结构净化

### 删除

* [ ] node_modules
* [ ] .venv
* [ ] build / dist
* [ ] 临时脚本

### 保留

* [ ] src
* [ ] config 模板
* [ ] migration 工具

---

## 2. 配置分层

* [ ] `.env` 不入库
* [x] 提供 `.env.example`（根目录新增模板）
* [x] 所有端口/路径可配置（`PORT`/`MEMORY_BACKEND_URL` 模板化）
* [ ] 禁止硬编码路径（Windows / localhost）

---

## 3. 一键启动能力（必须）

### 必须提供

* [x] `start.sh` / `make start`（已提供根目录 `start.sh` + `Makefile`）

### 自动完成

* [x] 依赖检查（`start.sh` 校验 `curl`/`python`，缺 runtime binary 时自动 `go build`）
* [x] runtime 启动（8765）
* [x] connector 启动（18011）

### 验收标准

```
新机器一条命令启动
```

当前实现：

* `make start` 或 `bash ./start.sh`

---

## 4. 数据与代码解耦

* [x] memory 数据独立目录（Adapter meter: `OMNIMEMORA_METER_DATA_DIR`）
* [x] SQLite 不与代码混放（Runtime: `OMNIMEMORA_RUNTIME_DATA_DIR`）
* [x] logs 独立目录（Runtime: `OMNIMEMORA_RUNTIME_LOG_DIR`）
* [ ] 支持备份 / 恢复

---

## 5. 迁移 SOP（必须文档化）

### 必须包含

1. clone 项目
2. 安装依赖
3. 配置 `.env`
4. 启动服务
5. 验证步骤

### 验收标准

```
30 分钟内完成新机器部署
```

文档状态：

* [x] 已提供迁移 SOP：`7_docs/internal/phase3/MIGRATION_SOP_WIN_TO_MAC.md`
* [x] 已完成一次本机冷启动演练（Step C 验收通过）

---

## 6. 跨平台兼容（Win → Mac）

* [ ] 无 `.exe` 依赖
* [ ] 无 `C:\` 路径
* [ ] shell 使用 LF
* [ ] 权限正确（chmod）
* [ ] Python / Node / Go 可跨平台安装

---

## 四、阶段 3：上线验收（Local Production Readiness）

## 目标

> 达到"可交付版本"标准

---

## 1. Observability（必须）

* [x] request_id 日志
* [x] 错误日志
* [x] token savings 统计
* [x] 按 agent / workspace 区分

---

## 2. 性能基线

* [x] 单请求延迟稳定（P50/P95 已记录）
* [x] 连续 100 请求无崩溃
* [x] 无明显内存泄漏（10 分钟采样，runtime +2MB，adapter -1.32MB）

---

## 3. 接入验证

至少完成：

* [x] Claude Code / Codex / OpenClaw 任一接入（Codex 已验证）
* [x] memory 正常调用
* [x] 不影响 agent 主流程

---

## 4. 回归测试体系

每次变更必须执行：

* [x] 写入 → 查询 → 删除
* [x] scope 测试
* [x] token savings
* [x] 异常场景

---

## 5. 最终验收标准

全部满足才允许迁移：

* [ ] 新机器一次启动成功
* [ ] 核心接口正常
* [ ] scope 不串
* [ ] token savings 正常
* [ ] 日志可追踪
* [ ] 连续运行 24h 无崩溃

---

## 五、时间预估

| 阶段     | 时间     |
| ------ | ------ |
| 可迁移版本  | 5–7 天  |
| 本地上线验收 | 7–12 天 |

---

## 六、核心原则

> ❗不要在脏环境中修 bug 再迁移
> ❗先做成"可复制系统"，再换机器

否则将出现：

```
旧机器能跑 → 新机器失败 → 无法定位问题来源
```

---

## 七、下一步文档（必须继续）

下一步必须产出：

```
MAC_MINI_COLD_START_ACCEPTANCE_CHECKLIST.md
```

用于：

> 从 0 到启动 → 完整验收路径

---

## 八、关联文档

| 文档 | 路径 |
|------|------|
| 框架修复审计报告 | `7_docs/internal/phase3/audit/AUDIT_REPORT_LOGIC_CORE_FIXES_2026-04-12.md` |
| 三实例恢复测试计划 | `7_docs/internal/phase4/THREE_INSTANCE_RECOVERY_TEST_PLAN.md` |
| P0-3 验收模板 | `7_docs/internal/phase4/p0-3_验收模板.md` |
| P0-3 手工 SOP | `7_docs/internal/phase4/p0-3_手工SOP_openclaw.md` |

---

**创建日期**: 2026-04-12
**版本**: 1.0
**状态**: 执行中

---

## 九、Phase 1 执行记录（2026-04-12）

### Step 1（今日）执行结果

* [x] 启动/重启 >= 10 次（实际 10 轮，每轮 2 次重启，共 20 次）
* [x] write → query → 重启 → 再 query 验证通过
* [x] adapter query 联动验证通过（request_count 持续增长）

证据文件：

* `tools/verification/logs/phase1_step1_restart_validation_20260413_001638.md`
* `tools/verification/logs/stability_probe_20260413_001810_summary.json`

### Step 2（明日）

* [x] Scope 隔离验证
* [x] 异常场景（runtime down / 空 memory / 非法 scope）

证据文件：

* `tools/verification/logs/phase1_step2_step3_validation_20260413_030125.md`

### Step 3（后日）

* [x] Token savings 可解释性验证（可解释“为什么省”）

关键观测：

* Decision query：`baseline=108, actual=71, saved=37, ratio=0.343`
* Implementation query：`task_type=implementation, context_bypass=True, memory_tokens_injected=0`

---

## 十、Phase 2 已落地项（2026-04-13）

* [x] 根目录 `.env.example` 模板
* [x] 根目录 `start.sh` 一键启动脚本（Runtime + Adapter + health 检查）
* [x] 根目录 `Makefile`（`make start`）
* [x] 迁移 SOP 文档（Win → Mac）
* [x] 硬编码扫描脚本与报告（`tools/verification/scan_phase2_hardcoding.ps1`）
* [x] meter 持久化目录支持外置（`OMNIMEMORA_METER_DATA_DIR`，与代码目录解耦）

验证补充（2026-04-13）：

* 对 `stability-tenant` 执行 query 后，meter 文件写入外置目录 `tools/verification/meter_data_test`，默认目录 `5_connectors/data` 时间戳未变化（证明外置路径生效）

---

## 十一、会话同步与恢复点（2026-04-13）

* [x] 本轮文档同步完成
* [x] 运行进程已记录（8765/18011 的 PID 与命令）
* [x] 下轮从 Phase 2 顺序继续（见 `SESSION_HANDOFF_2026-04-13.md`）

---

## 十二、Phase 2 Step A 进展（2026-04-13）

* [x] `tools/memrun.py`：adapter 地址改为环境变量优先，TCP fallback 不再硬编码 `127.0.0.1:18011`
* [x] `tools/dashboard.py`：adapter 地址改为环境变量优先
* [x] `5_connectors/adapter/backends/factory.py`：backend `base_url` 默认值改为 `MEMORY_BACKEND_URL` 驱动
* [x] `5_connectors/adapter/backends/omnimemora_runtime_backend.py`：runtime `base_url` 默认值改为 `MEMORY_BACKEND_URL` 驱动
* [x] 语法回归：上述改动文件 `py_compile` 全通过

---

## 十三、Phase 2 Step B 进展（2026-04-13）

目标：Runtime 侧数据/状态/SQLite/日志路径统一环境变量化，完成与代码目录解耦。

已完成：

* [x] Runtime 状态目录 `GetDataDir()` 支持 `OMNIMEMORA_RUNTIME_DATA_DIR` / `OMNIMEMORA_DATA_DIR`
* [x] Config Loader 支持 `OMNIMEMORA_CONFIG` 显式配置文件路径
* [x] Config Loader 支持 runtime/cloud 关键字段 env override（含 data_path）
* [x] CLI 启动日志改为写入可配置目录（`OMNIMEMORA_RUNTIME_LOG_DIR` / `OMNIMEMORA_LOG_DIR`）
* [x] Demo/metering 的 first-run marker 路径与统一 data dir 对齐

实测验收（8775 端口，独立测试二进制）：

* [x] `/health` 正常
* [x] `runtime.state` 写入外置 data 目录
* [x] `memory.db` 写入外置 data 目录
* [x] `runtime.out.log` / `runtime.err.log` 写入外置 logs 目录

证据文件：

* `tools/verification/logs/phase2_stepb_runtime_data_log_decoupling_20260413_104949.md`

下一步：

* Phase 2 Step C：按 `MIGRATION_SOP_WIN_TO_MAC.md` 执行一次完整冷启动演练并回填文档勾选项

---

## 十四、Phase 2 Step C 进展（2026-04-13）

目标：按迁移 SOP 做一次可复现冷启动演练，验证“新机器可复制部署”链路。

已落地：

* [x] 新增演练脚本：`tools/verification/run_phase2_stepc_migration_rehearsal.ps1`
* [x] 完成健康检查（8765 / 18011）
* [x] 完成 runtime write → query 闭环
* [x] 完成 adapter query 与 usage 验证（`request_count` 增长）
* [x] token savings endpoint 可用

最终验收证据：

* `tools/verification/logs/phase2_stepc_migration_rehearsal_20260413_105259.md`（7/7 PASS）

阶段结论：

* Phase 2 Step C 通过，可进入 Phase 3（上线验收）准备工作。

---

## 十五、Phase 3 Baseline 进展（2026-04-13）

目标：完成 Observability 与性能基线的首轮可复现验收。

代码改进（runtime）：

* [x] middleware 日志升级：记录 request_id / method / path / tenant / user / workspace / agent / scope / status / took_ms / bytes
* [x] request_id 回传：响应头统一写入 `X-OmniMemora-Request-Id`
* [x] handler 请求链路：`Write/Query/Search/Delete` 默认使用 middleware request_id（避免链路断裂）
* [x] metering 错误日志：输出 request_id + tenant/workspace/agent 维度

验证脚本与结果：

* [x] 新增脚本：`tools/verification/run_phase3_observability_perf_baseline.ps1`
* [x] 验证报告：`tools/verification/logs/phase3_observability_perf_baseline_20260413_110311.md`
* [x] 检查项：6/6 PASS
  - response header includes request_id
  - response body includes request_id
  - `/metrics` 包含 by_scope + token_savings
  - 错误路径 501 可观测
  - 100 请求后 request_count 增长
  - 100 请求期间 runtime/adapter 无崩溃

性能快照（adapter 100 请求）：

* success=100, failed=0
* min=44ms, p50=81ms, p95=107ms, max=130ms, avg=75.2ms

阶段结论：

* Phase 3 的 Observability 与性能基线首轮通过，可进入接入验证与回归体系补齐。

---

## 十六、Phase 3 完整化进展（2026-04-13）

目标：补齐接入验证、回归体系、内存泄漏风险评估。

执行与证据：

* [x] 接入验证 + 回归脚本：`tools/verification/run_phase3_integration_and_regression.ps1`
* [x] 报告：`tools/verification/logs/phase3_integration_regression_20260413_120957.md`（8/8 PASS）
  - Codex attach 成功（已配置）
  - attach 后 memory 调用正常
  - 主流程未受影响
  - write→query→delete→query、scope、token savings、异常路径均通过
* [x] 内存采样脚本：`tools/verification/run_phase3_memory_leak_sampling.ps1`
* [x] 报告：`tools/verification/logs/phase3_memory_leak_sampling_20260413_121042.md`
  - 10 分钟采样，282 请求全成功，fail rate=0%
  - runtime private memory: 53.36MB → 55.36MB（+2MB）
  - adapter private memory: 64.56MB → 63.24MB（-1.32MB）
  - verdict: `no_obvious_memory_leak=True`

阶段结论：

* Phase 3 核心项已补齐；当前剩余硬门槛主要是最终验收中的 24h 稳定性与迁移端到端一次通过证据。

---

## 十七、Final Gate 进展（2026-04-13）

目标：启动最终 24h 稳定性门槛验证，形成可交付最终证据。

执行状态：

* [x] 24h 稳定性探针已启动（后台）
  - 脚本：`tools/verification/run_stability_probe.ps1`
  - 启动参数：`-DurationHours 24 -IntervalSeconds 30 -Tenant final-24h-tenant -Agent codex`
  - 启动时间：2026-04-13 12:21:44 +08:00
  - 进程 PID：`29888`（powershell）
  - 实时日志：`tools/verification/logs/stability_probe_20260413_122144.jsonl`

待完成：

* [ ] 24h 运行结束后回收 `stability_probe_*_summary.json`
* [ ] 回填最终验收条目“连续运行 24h 无崩溃”
* [ ] 输出全量最终交付总结

---

## 十八、Final Gate 实时状态补充（2026-04-13 12:25 +08:00）

补充结论：

* [x] 2h 连续稳定性门槛已完成（历史有效证据）
  - 证据：`tools/verification/logs/stability_probe_20260413_002429.jsonl`
  - 汇总：`tools/verification/logs/stability_probe_20260413_002429_summary.json`
  - 结果：`iterations=240`，`runtime_failures=0`，`query_failures=0`，`adapter_failures=0`，`request_count_growth=240`
* [x] 24h 探针运行中（Final Gate 长跑）
  - 进程：`powershell.exe` PID `29888`
  - 日志：`tools/verification/logs/stability_probe_20260413_122144.jsonl`
  - 当前健康信号：`runtime_ok=true`、`adapter_ok=true`、`query_ok=true` 且 `usage_request_count` 持续增长

Final Gate 剩余：

* [ ] 等待 24h 运行自然结束并生成 `stability_probe_20260413_122144_summary.json`
* [ ] 回填第 5 节最终验收勾选项“连续运行 24h 无崩溃”
* [ ] 输出最终交付总结（含风险与下一步）
