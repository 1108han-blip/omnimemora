# OmniMemora Promotion Workflow Runbook

## 概述

本 runbook 提供 promotion workflow 的逐命令执行指南，包含三个完整样例。

**前置阅读**：执行计划 中已定义触发条件、验证矩阵、失败分类，务必先读。

---

## Runtime-only Promotion 样例

### 场景

假设在 `4_core/local-runtime` 中修改了 runtime 的健康检查逻辑，需要将变更提升到 running reality。

### 步骤

#### 1. 确认 promotion 触发条件

```bash
# 确认变更已在 repo reality 成立
cd /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora
git log --oneline -3

# 确认工作区可控（无未提交变更影响构建）
git status
```

#### 2. 构建

```bash
cd /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/local-runtime

# 执行构建（根据项目实际构建命令调整）
# 示例：假设是 Go 项目
# go build -o /Users/sc/.omnimemora/service/current/tools/omnimemora-runtime ./cmd/server

# 验证二进制已部署
ls -la /Users/sc/.omnimemora/service/current/tools/omnimemora-runtime
```

#### 3. 受控重载

```bash
# 先停止现有实例
launchctl stop gui/$(id -u)/com.omnimemora.runtime

# 重新加载
launchctl load gui/$(id -u)/com.omnimemora.runtime

# 或使用 kickstart 组合
# launchctl kickstart -k gui/$(id -u)/com.omnimemora.runtime
# launchctl load gui/$(id -u)/com.omnimemora.runtime
```

#### 4. 复验

```bash
# 4.1 launch reality 验证
launchctl print gui/$(id -u)/com.omnimemora.runtime

# 预期输出应包含 service 状态信息，无 error

# 4.2 健康检查
curl -s http://localhost:8765/health

# 预期输出应包含健康状态（根据实际返回格式判断）

# 4.3 产品接口验证（按本次变更涉及接口调整）
# 示例：检查 runtime 是否正常响应
curl -s http://localhost:8765/api/status
```

#### 5. 记录

```bash
# 记录本次 promotion
# 格式：时间 | 组件 | 来源 | 验证结果

# 创建 promotion 记录（追加到验证记录）
cat >> /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md << 'EOF'

## Promotion Record: $(date)

- **组件**: runtime
- **来源**: 4_core/local-runtime (git commit: $(git rev-parse --short HEAD))
- **部署目标**: ~/.omnimemora/service/current/tools/omnimemora-runtime
- **验证结果**:
  - launch reality: PASS
  - /health (8765): PASS
  - 产品接口: PASS
- **running reality vs repo reality**: 对齐到本次变更
EOF
```

---

## Adapter-only Promotion 样例

### 场景

假设修改了 adapter 的 `/health` 端点逻辑，需要将变更提升到 running reality。

### 步骤

#### 1. 确认 promotion 触发条件

```bash
# 确认变更已在 repo reality 成立
cd /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora
git log --oneline -3

# 确认工作区可控
git status
```

#### 2. 明确文件集合

```bash
# 列出本次涉及的实际运行文件
# 示例：假设只修改了 adapter.py
ls -la /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/adapter/*.py

# 确认 plist 配置
cat /Users/sc/Library/LaunchAgents/com.omnimemora.adapter.plist
```

#### 3. 同步

```bash
# 将实际运行所需文件同步到 service/current
# 示例：同步整个 adapter 目录
rsync -av --progress \
  /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/4_core/adapter/ \
  /Users/sc/.omnimemora/service/current/

# 验证同步结果
ls -la /Users/sc/.omnimemora/service/current/
```

#### 4. 受控重启

```bash
# 停止 adapter
launchctl stop gui/$(id -u)/com.omnimemora.adapter

# 确认进程已停止
ps aux | grep _run_adapter | grep -v grep

# 启动 adapter
launchctl start gui/$(id -u)/com.omnimemora.adapter

# 确认进程已启动
sleep 2
ps aux | grep _run_adapter | grep -v grep
```

#### 5. 复验（三层并列）

```bash
# 5.1 plist reality
cat /Users/sc/Library/LaunchAgents/com.omnimemora.adapter.plist | grep ProgramArguments

# 预期：ProgramArguments 指向 service/current 中的文件

# 5.2 process reality
ps aux | grep _run_adapter | grep -v grep

# 预期：进程存在

# 5.3 API reality
curl -s http://localhost:18011/health

# 预期：返回健康状态

# 5.4 本次变更涉及的控制面接口（按实际情况调整）
# 示例：检查路由控制
curl -s http://localhost:18011/api/route/status
```

#### 6. 记录

```bash
# 创建 promotion 记录
cat >> /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md << 'EOF'

## Promotion Record: $(date)

- **组件**: adapter
- **来源**: 4_core/adapter/*.py
- **部署目标**: ~/.omnimemora/service/current/
- **验证结果**:
  - plist reality: PASS
  - process reality: PASS
  - /health (18011): PASS
  - 产品接口: PASS
- **running reality vs repo reality**: 对齐到本次变更
EOF
```

---

## UI-only Promotion 样例

### 场景

假设修改了前端控制卡的展示逻辑，需要将变更提升到 running reality。

### 步骤

#### 1. 确认 promotion 触发条件

```bash
# 确认变更已在 repo reality 成立
cd /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora
git log --oneline -3

# 确认工作区可控
git status

# 确认本次变更影响正式用户控制入口
# 属于必须带 ui 的 promotion
```

#### 2. 构建（若需构建）

```bash
cd /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/6_console/demo-dashboard

# 执行前端构建
npm run build

# 验证构建产物
ls -la dist/
```

#### 3. 同步（方案 C 分层常驻无需同步构建产物）

方案 C 下 UI 使用 vite dev server 直接启动，不需同步到 service/current。

#### 4. 启动/检查 UI

```bash
# 检查 5173 是否在线
curl -s http://127.0.0.1:5173/ 2>&1 | head -c 100

# 若未启动，手动启动
cd /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/6_console/demo-dashboard
npm run dev

# 确认进程已启动
ps aux | grep vite | grep -v grep
```

#### 5. 复验

```bash
# 5.1 UI 首页可访问
curl -s http://127.0.0.1:5173/ | head -c 200

# 预期：返回 HTML 页面

# 5.2 控制面渲染
curl -s http://127.0.0.1:5173/agents?tenant=all | head -c 200

# 预期：返回包含 agent 列表的页面

# 5.3 UI 与 API 一致性
# 检查页面中的 installed/routing_enabled/active 状态是否与 18011 API 一致
curl -s http://localhost:18011/agents/control

# 对比页面渲染与 API 返回是否一致
```

#### 6. 记录

```bash
# 创建 promotion 记录
cat >> /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/7_docs/internal/phase5/plan/OmniMemora_验证对象登记与验收记录_2026-04-18.md << 'EOF'

## Promotion Record: $(date)

- **组件**: ui
- **来源**: 4_core/ui (git commit: $(git rev-parse --short HEAD))
- **部署方式**: 手动启动
- **验证结果**:
  - UI 在线 (5173): PASS/FAIL（必须记录实际状态）
  - 首页可访问: PASS/FAIL
  - 控制面渲染 (/agents?tenant=all): PASS/FAIL
  - UI 与 18011 API 一致性: PASS/FAIL
- **running reality vs repo reality**: 对齐到本次变更
- **UI 在线状态**: PASS（在线）/ FAIL（离线）
- **重要**: 若 UI 离线，running reality 结论应为"UI 运行态未就绪"
EOF
```

---

## 失败处理速查

| 失败类型 | 立即动作 |
|----------|----------|
| build 失败 | 停在 build，保留错误输出，不继续部署 |
| 文件同步失败 | 停在 sync，检查目标路径权限 |
| 重载失败 | 查看 `launchctl print` 错误信息，保留证据 |
| 接口不达标 | 停在验证，记录失败接口响应 |
| 产品路径回归 | 停在端到端，记录回归的产品路径 |
| UI 启动失败 | 停在 UI，记录启动错误，不触发 runtime/adapter 回滚 |

### 回滚命令（runtime）

```bash
# 停止
launchctl stop gui/$(id -u)/com.omnimemora.runtime

# 从备份恢复（如果有）
# cp /path/to/backup/omnimemora-runtime ~/.omnimemora/service/current/tools/omnimemora-runtime

# 重新加载
launchctl load gui/$(id -u)/com.omnimemora.runtime

# 重新验证
launchctl print gui/$(id -u)/com.omnimemora.runtime
curl -s http://localhost:8765/health
```

### 回滚命令（adapter）

```bash
# 停止
launchctl stop gui/$(id -u)/com.omnimemora.adapter

# 从备份恢复（如果有）
# rsync -av --progress /path/to/backup/ ~/.omnimemora/service/current/

# 重新启动
launchctl start gui/$(id -u)/com.omnimemora.adapter

# 重新验证三层
ps aux | grep _run_adapter | grep -v grep
curl -s http://localhost:18011/health
```

### UI 回滚说明

UI 的失败不算 runtime/adapter 失败，不触发整个系统的回滚。若 UI promotion 后不达标：
- 记录为"UI 运行态未就绪"
- 若 UI 由手动启动，可尝试重新启动
- 不需要回滚 runtime 或 adapter

---

## 快速检查清单

每次 promotion 前快速确认：

```
[ ] 变更已在 repo/candidate reality 明确成立
[ ] 验证目标已命名
[ ] 结论适用范围已写清
[ ] 工作区处于可控状态（git status clean 或已知状态）
[ ] promotion 组件范围已明确（runtime / adapter / ui / 组合）
[ ] 若影响正式用户控制入口，ui 已纳入范围
[ ] 不在验证对象未锁定时 promotion
[ ] 不把 running reality 成功行为回写成 repo 证据
```

promotion 后必做：

```
[ ] launch reality 验证通过（runtime/adapter）
[ ] 健康检查通过（8765/18011/5173 按范围）
[ ] 产品接口验证通过（按变更范围）
[ ] UI 在线状态必须单独记录
[ ] 记录写入验证记录
[ ] 确认 running reality 与 repo reality 对齐层级
```

---

## 双层表达速查

| 能力层 | 运行层 |
|--------|--------|
| UI 工程能力已恢复 | UI 当前在线 / UI 当前离线 |
| 5173 作为正式控制入口能力具备 | 5173 实际运行态 |

- 不能把上排写成一句
- 记录时必须明确当前是哪一层
