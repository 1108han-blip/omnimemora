# Phase 5 Docs Index

## Active Docs

- [云端小工程](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/云端小工程.md)
- [OmniMemora OpenClaw-first Real Client Recovery + Visual Validation 执行计划](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_OpenClaw_First_Real_Client_Recovery_Visual_Validation_执行计划_2026-04-19.md)
- [OmniMemora OpenClaw-first Real Client Recovery + Visual Validation Runbook](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_OpenClaw_First_Real_Client_Recovery_Visual_Validation_Runbook_2026-04-19.md)
- [OmniMemora 验证对象登记与验收记录](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)
- [OmniMemora Decision Carrier / Control-Plane Decoupling Bounded Scan](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Decision_Carrier_Control_Plane_Decoupling_Bounded_Scan_2026-04-18.md)

## Current Phase Boundary

- 当前执行主线：`Running Topology Clarification`
- 阶段状态：**进行中**
- 当前阶段目标：
  - 明确三层现实（repo reality / candidate reality / running reality）的关系与边界
  - 固定 promotion 的触发条件与最小步骤
  - 固定运行观察模型，避免观察口径混乱
  - 明确 dev-mode 是后续选项，不是默认结构

### 拓扑契约（三层现实）

- **repo reality**：当前工作区代码与文档事实
- **candidate reality**：基于 repo 启动的隔离验证实例
- **running reality**：`~/.omnimemora/service/current` + launchd 当前实际在线服务

关键约束：
- running reality 默认不从 repo 直接读取代码
- running reality 的成功行为不能反推 repo 已自动具备同等行为
- repo 修改默认不会自动进入 running reality，除非显式 promotion
- `service/current` 是独立目录，不是 symlink，保持独立部署为正式结构

### promotion 模型（已固定）

- promotion 是**显式动作**，不是隐式同步
- promotion 的标准输入：
  - runtime：从 `4_core/local-runtime` 构建并部署到 `service/current/tools/omnimemora-runtime`
  - adapter：同步 `service/current` 中实际运行的 Python 文件
- promotion 后必须重新验证 running reality，不能只凭部署动作宣布成功

### 观察模型（已固定）

- runtime launch reality：`launchctl print gui/$(id -u)/com.omnimemora.runtime`
- adapter launch reality：plist 文件 + 实际进程 + launchctl 可见性（注意：launchctl print 不能稳定枚举 adapter service）
- product API reality：`18011`（adapter）、`8765`（runtime）、`5173`（UI）

**重要**：”adapter 进程存在”与”launchctl print 能稳定枚举 adapter service”不是同一层信号，以后报告里不得把这两者混用。

## 上一阶段（OpenClaw-first）收口结论

- `Decision Carrier / Control-Plane Decoupling` 已阶段性完成并转为结构前置成果
- `5173` 已恢复为正式用户控制入口
- `OpenClaw` 已完成接入层 / 路由层控制闭环
- OpenClaw 的”安装成立”标准已升级为：`MCP 接入 + main 实际生效请求入口接入 18011`
- OpenClaw 的 MCP 运行期端点已定位为 `/sse`
- OpenClaw marker 已迁移到独立文件 `~/.openclaw/.omnimemora.attach.marker`
- 真实 OpenClaw 请求已进入 `18011`
- `route off -> agent_route_disabled` 语义成立
- `route on -> runtime_compile` 语义成立
- **`Control Activity Semantics` 已完成**：compile events 是 `active / last_seen_at` 主 truth source

## 下一阶段候选

- **`Promotion Workflow Formalization`**（默认推荐）：把 runtime/adapter promotion 做成正式 SOP，包括标准输入、标准命令、标准重载、标准验证
- **`Adapter Launch Visibility Clarification`**：收口 adapter plist/进程/launchctl 可见性三层不对等现象

明确排除：继续改 OpenClaw attach（已收口）、GUI 物理独立、`trial / internal admin`、compile/strategy 大拆、dev-mode 提速方案（本阶段结论为 dev-mode 如需存在，后续单开主线规划）

## Supplemental Docs

- [OmniMemora V2遗产映射与后备优化清单](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_V2遗产映射与后备优化清单_2026-04-18.md)

## Archived Phase 5 Convergence Docs

- [Archive Folder](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/archive/2026-04-18-phase5-convergence)
- [Phase 5.5 Product Hardening Archive](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/archive/2026-04-18-phase5_5-product-hardening)

Only the files listed under `Active Docs` should be treated as current execution docs.
