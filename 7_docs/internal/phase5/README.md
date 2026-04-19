# Phase 5 Docs Index

## Active Docs

- [云端小工程](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/云端小工程.md)
- [OmniMemora OpenClaw-first Real Client Recovery + Visual Validation 执行计划](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_OpenClaw_First_Real_Client_Recovery_Visual_Validation_执行计划_2026-04-19.md)
- [OmniMemora OpenClaw-first Real Client Recovery + Visual Validation Runbook](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_OpenClaw_First_Real_Client_Recovery_Visual_Validation_Runbook_2026-04-19.md)
- [OmniMemora 验证对象登记与验收记录](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md)
- [OmniMemora Decision Carrier / Control-Plane Decoupling Bounded Scan](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Decision_Carrier_Control_Plane_Decoupling_Bounded_Scan_2026-04-18.md)
- [OmniMemora Promotion Workflow 执行计划](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Promotion_Workflow_执行计划_2026-04-19.md)
- [OmniMemora Promotion Workflow Runbook](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_Promotion_Workflow_Runbook_2026-04-19.md)

## Current Phase Boundary

- 当前执行主线：`UI Running Strategy Clarification`
- 阶段状态：**进行中**
- 当前阶段目标：
  - 明确 `5173` 在正式 running reality 中的运行策略
  - 固定 UI 的托管边界
  - 固定 UI promotion 的真实完成标准
  - 收敛 active docs 对 `5173` 的表述不再冲突

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
- **UI reality**：`5173`（**必须单独验证在线状态**）

### Running Reality 正式组件集合（方案 C：分层常驻）

| 组件 | 端口 | 托管层级 | 备注 |
|------|------|----------|------|
| runtime | 8765 | 基础层 · launchd 常驻 | `launchctl print` 可作为强观察面 |
| adapter | 18011 | 基础层 · launchd 常驻 | plist + 进程，launchctl print 不稳定 |
| UI | 5173 | **控制入口层 · 分层常驻** | 可手动启动，默认应可验证，但不强制常驻 |

**方案 C（分层常驻）的定义**：
- `18011/8765` 构成**基础 running reality**，必须常驻在线
- `5173` 是”正式控制入口层”，默认应可启动并可验证
- `5173` 不要求 24/7 常驻，但要求在使用时可快速启动并验证
- 本方案保留 `5173` 作为正式用户控制入口的产品地位，不强迫当前把 dev server 方式硬塞进 launchd 常驻托管

**Running Reality 完整成立的判断**：
- 基础层在线（8765 + 18011）→ **基础 running reality 成立**
- 基础层在线 + 5173 在线 → **完整 running reality 成立**

### 双层表达约定

- **能力层结论**：`5173` 作为正式控制入口的工程能力已恢复
- **运行层结论**：`5173` 是否在线，属于 running reality 的当前状态，必须单独验证

**禁止**把”UI 工程已修好”和”正式 running reality 中 5173 当前在线”写成一句话。

### UI Promotion 完成标准（三层）

| 层级 | 内容 | 验收方式 |
|------|------|----------|
| **能力层** | UI 工程可构建、可启动、路由正确、控制卡正确 | `npm run build` + 代码审查 |
| **运行层** | 当前 `5173` 在线，`/` 与 `/agents?tenant=all` 可访问 | `curl http://127.0.0.1:5173/` |
| **托管层** | UI 当前的正式运行方式已被文档承认并固定 | 本文档确认 |

**重要**：若托管层未定义完成，不能声称”running reality 完整成立”。

### UI 当前运行状态

| 层级 | 状态 | 说明 |
|------|------|------|
| 能力层 | ✅ 已恢复 | UI 工程可构建、可启动、路由正确 |
| 运行层 | ⏳ 待验证 | 5173 当前是否在线需单独确认 |
| 托管层 | ✅ 已定义（方案 C） | 分层常驻，5173 可手动启动，不强制常驻 |

### 当前 5173 实际状态

```bash
# 检查 5173 在线状态
curl -s http://127.0.0.1:5173/ | head -c 100
```

- 若返回 HTML → **运行层在线**
- 若连接失败 → **运行层离线**，但不影响基础 running reality 成立

## 上一阶段（OpenClaw-first）收口结论

- `Decision Carrier / Control-Plane Decoupling` 已阶段性完成并转为结构前置成果
- **`5173` 能力层已恢复**：作为正式用户控制入口的工程能力已具备（但当前运行层状态需单独验证）
- `OpenClaw` 已完成接入层 / 路由层控制闭环
- OpenClaw 的”安装成立”标准已升级为：`MCP 接入 + main 实际生效请求入口接入 18011`
- OpenClaw 的 MCP 运行期端点已定位为 `/sse`
- OpenClaw marker 已迁移到独立文件 `~/.openclaw/.omnimemora.attach.marker`
- 真实 OpenClaw 请求已进入 `18011`
- `route off -> agent_route_disabled` 语义成立
- `route on -> runtime_compile` 语义成立
- **`Control Activity Semantics` 已完成**：compile events 是 `active / last_seen_at` 主 truth source

## 下一阶段候选

（将在本阶段结束后更新）

明确排除：继续改 OpenClaw attach（已收口）、GUI 物理独立、`trial / internal admin`、compile/strategy 大拆、dev-mode 提速方案（本阶段结论为 dev-mode 如需存在，后续单开主线规划）

## Supplemental Docs

- [OmniMemora V2遗产映射与后备优化清单](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_V2遗产映射与后备优化清单_2026-04-18.md)

## Archived Phase 5 Convergence Docs

- [Archive Folder](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/archive/2026-04-18-phase5-convergence)
- [Phase 5.5 Product Hardening Archive](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/archive/2026-04-18-phase5_5-product-hardening)

Only the files listed under `Active Docs` should be treated as current execution docs.
