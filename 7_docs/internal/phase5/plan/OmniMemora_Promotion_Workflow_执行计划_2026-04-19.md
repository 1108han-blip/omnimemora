# OmniMemora Promotion Workflow 执行计划

## 目标

把当前已"口头固定"的 promotion 规则收敛成**正式 SOP**，使任何后续实施者能在不混淆 `repo reality / candidate reality / running reality` 的前提下，稳定完成变更提升到 `~/.omnimemora/service/current` 并完成复验。

## 前置条件（已固定）

- `service/current` 是独立目录，不是 symlink
- runtime 运行入口：`~/.omnimemora/service/current/tools/omnimemora-runtime serve`
- adapter 运行入口：`~/.omnimemora/service/current/tools/_run_adapter.py`
- UI 运行入口：`5173`（当前为手动启动方式，尚未正式托管）
- runtime 的 `launchctl print` 可作为强观察面
- adapter 当前存在 plist + 进程，但 `launchctl print` 不能稳定作为唯一强观察面
- UI 当前由手动启动保持，尚未纳入 launchd 托管体系

## 拓扑契约

```
repo reality          →  当前工作区代码与文档事实
        ↓ build / sync
candidate reality     →  基于 repo 启动的隔离验证实例
        ↓ promotion
running reality       →  ~/.omnimemora/service/current + launchd 当前实际在线服务
```

关键约束：
- running reality 的成功行为不能反推 repo 已自动具备同等行为
- repo 修改不会自动进入 running reality，除非显式 promotion

## Running Reality 正式组件集合

running reality 正式定义为**三组件**：

| 组件 | 端口 | 托管方式 | 备注 |
|------|------|----------|------|
| runtime | 8765 | launchd | `launchctl print` 可作为强观察面 |
| adapter | 18011 | launchd | plist + 进程，launchctl print 不稳定 |
| UI | 5173 | **手动启动** | 尚未正式托管，必须单独验证在线状态 |

**重要**：
- `5173` 是正式用户控制入口
- 在正式 running reality 中，`5173` 不是可有可无的观察面
- 如果 `5173` 未在线，不能把 running reality 描述成"正式控制入口完整成立"

### 双层表达约定

- **能力层结论**：`5173` 作为正式控制入口的工程能力已恢复
- **运行层结论**：`5173` 是否在线，属于 running reality 的当前状态，必须单独验证

以后文档中不能把：
- "UI 工程已修好"
和
- "正式 running reality 中 5173 当前在线"
写成一句话。

## promotion 触发条件（必须全部满足）

1. 变更已经在 `repo reality` 或 `candidate reality` 明确成立
2. 验证目标已命名
3. 结论适用范围已写清
4. 工作区处于可控状态
5. 要提升的组件范围已明确：
   - `runtime-only`
   - `adapter-only`
   - `ui-only`
   - `runtime + adapter`
   - `adapter + ui`
   - `runtime + adapter + ui`

**新增约束**：
- 只要本次变更影响正式用户控制入口契约、控制卡展示、控制动作流或前端依赖接口，就必须把 `ui` 纳入 promotion 范围。

### 明确禁止

- 因"想让 running reality 跟上"就直接 promotion
- 在验证对象未锁定时 promotion
- 把 running reality 的成功行为回写成 repo 已成立的证据

## Runtime Promotion SOP

### 触发输入

- 组件：`runtime`
- 构建来源：`4_core/local-runtime`
- 部署目标：`~/.omnimemora/service/current/tools/omnimemora-runtime`

### 标准步骤

1. **构建**
   - 在 `4_core/local-runtime` 执行构建
   - 输出二进制到 `~/.omnimemora/service/current/tools/omnimemora-runtime`

2. **受控重载**
   ```bash
   launchctl kickstart -k gui/$(id -u)/com.omnimemora.runtime
   launchctl load gui/$(id -u)/com.omnimemora.runtime
   ```
   或使用 `launchctl stop/start` 组合

3. **验证（必须逐项通过）**
   - `launchctl print gui/$(id -u)/com.omnimemora.runtime` — launch reality
   - `GET /health` on port `8765` — 健康检查
   - 必要的运行期产品接口（见验收矩阵）

### 注意事项

- 仅替换二进制不等于 promotion 完成，必须带复验
- 必须从 `4_core/local-runtime` 执行构建，不能从其他路径

## Adapter Promotion SOP

### 触发输入

- 组件：`adapter`
- 同步来源：`service/current` 中实际运行的 Python 文件集合
- 部署目标：`~/.omnimemora/service/current`

### 标准步骤

1. **明确文件集合**
   - 列出本次涉及的实际运行文件
   - 不同步未使用的文件

2. **同步**
   - 将实际运行所需文件同步到 `~/.omnimemora/service/current`

3. **受控重启**
   ```bash
   launchctl stop gui/$(id -u)/com.omnimemora.adapter
   launchctl start gui/$(id -u)/com.omnimemora.adapter
   ```

4. **验证（三层并列，必须全部通过）**
   - plist reality：`plist` 仍指向 `service/current`
   - process reality：进程真实存在
   - API reality：`18011` 上的对应接口行为正确

### 观察口径（已固定）

adapter 当前观察口径固定为三层并列：
- plist reality
- process reality
- API reality

**明确写入**：
- 在 adapter launchctl 可见性未稳定前，不把 `launchctl print gui/$(id -u)/com.omnimemora.adapter` 作为唯一成功标准
- "进程存在"与"launchctl print 可枚举"不可混写成一句"adapter 由 launchd 正常托管"

## UI Promotion SOP

### 触发输入

- 组件：`ui`
- 同步来源：前端构建产物
- 部署目标：`5173` 启动目录

### 标准步骤

1. **明确输入**
   - 前端代码或构建产物
   - 运行方式（当前为手动启动）

2. **明确启动方式**
   - UI 组件当前是**必验组件**
   - 但其 running strategy **仍需手动启动 / 手动保持**
   - 不能假装它已经被 launchd 或其他 supervisor 正式托管

3. **启动/复验**
   ```bash
   # 确认 5173 在线
   curl -s http://127.0.0.1:5173/ | head -c 100

   # 若未启动，手动启动（根据实际项目调整）
   cd /path/to/ui && npm run dev -- --port 5173
   ```

4. **验证（必须逐项通过）**
   - `http://127.0.0.1:5173/` — UI 首页可访问
   - `http://127.0.0.1:5173/agents?tenant=all` — 控制面可渲染
   - 页面能正确消费正式 `18011` API
   - 验证 UI 与 control API 一致：`installed`、`routing_enabled`、`active`

### 若 5173 不在线时的处理

- 必须在验证记录中明确记录"UI 当前离线"
- 不能将"UI 工程能力已恢复"等同于"UI 当前在线"
- running reality 结论应描述为："UI 离线，能力已具备但运行态未就绪"

## Promotion 后复验矩阵（三组件）

### runtime-only

| 验证项 | 方法 | 端口 |
|--------|------|------|
| runtime launch reality | `launchctl print gui/$(id -u)/com.omnimemora.runtime` | - |
| 健康检查 | `GET /health` | 8765 |
| 必要的 runtime API | 按本次变更涉及接口 | 8765 |

### adapter-only

| 验证项 | 方法 | 端口 |
|--------|------|------|
| adapter plist reality | 检查 plist 文件 | - |
| adapter process reality | 进程存在 | - |
| API reality | `GET /health` | 18011 |
| 本次变更涉及的控制面/API | 按本次变更涉及接口 | 18011 |

### ui-only

| 验证项 | 方法 | 端口 |
|--------|------|------|
| UI 在线 | `curl -s http://127.0.0.1:5173/` | 5173 |
| UI 首页 | `curl -s http://127.0.0.1:5173/` | 5173 |
| 控制面渲染 | `curl -s http://127.0.0.1:5173/agents?tenant=all` | 5173 |
| UI 与 API 一致性 | 检查 `installed/routing_enabled/active` 显示 | - |

### adapter + ui

| 验证项 | 方法 | 端口 |
|--------|------|------|
| adapter plist reality | 检查 plist 文件 | - |
| adapter process reality | 进程存在 | - |
| API reality | `GET /health` | 18011 |
| UI 在线 | `curl -s http://127.0.0.1:5173/` | 5173 |
| UI 与 `/agents/control` 一致 | 验证控制面数据 | - |

### runtime + adapter + ui

| 验证项 | 方法 | 端口 |
|--------|------|------|
| runtime 所有项 | 见 runtime-only 矩阵 | 8765 |
| adapter 所有项 | 见 adapter-only 矩阵 | 18011 |
| UI 所有项 | 见 ui-only 矩阵 | 5173 |
| 端到端产品路径 | 控制面可见 → 控制动作可触发 → 产品行为变化 | - |

### 记录要求

每次 promotion 后必须记录：
- 明确写出实例路径/来源
- 明确写出本次 promotion 的输入组件
- 明确写出 running reality 是否与 repo reality 对齐到哪一层
- **新增**：UI 在线状态必须单独记录

## 失败分支与回滚口径

### 失败分类

1. **build 失败**
2. **文件同步失败**
3. **重载失败**
4. **运行存活但接口不达标**
5. **运行达标但产品路径回归**

### 标准动作

- 停在当前组件边界，不顺手扩大修复范围
- 保留 failure evidence
- 如需回滚，只回滚本次提升的组件，不混入其他修复
- 回滚后重新验证 running reality，不能只看进程存活

### UI 特有处理

- 若 UI promotion 后 5173 不达标准，但 adapter/runtime 正常，应记录为"UI 运行态未就绪"
- UI 的失败不算 runtime/adapter 失败，不触发整个系统的回滚

## 输出文档

1. **执行计划**（本文件）：定义 SOP 结构与标准步骤
2. **Runbook**：提供逐命令执行的详细操作指南
3. **README 更新**：将执行计划和 runbook 加入 Active Docs

## 验收检查

- active docs 能清楚回答：
  - 何时允许 promotion
  - runtime promotion 如何做
  - adapter promotion 如何做
  - ui promotion 如何做（新增）
  - promotion 后如何复验
  - promotion 失败后如何停住
  - 如何区分"UI 工程能力成立"与"UI 当前在线成立"（新增）
- 新窗口只读 active docs，就不会再把 repo 改动误认为 running reality 已生效
- 任何后续实施者都能按 SOP 完成一次 runtime-only promotion、一次 adapter-only promotion 和一次 ui-only promotion，而无需重新发明步骤

## 样例要求

本阶段文档中必须包含两个标准样例：
- 一个 runtime-only promotion 样例
- 一个 adapter-only promotion 样例
- **新增**：一个 ui-only promotion 样例

（样例详见 Runbook）
