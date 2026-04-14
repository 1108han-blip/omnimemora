整体目标严格收敛为：

```text
Phase 3.5 = 发布可下载版本
目标：下载 → 启动 → 自动打开 dashboard → 自动看到 token savings
```

对齐当前 Phase 3 已完成能力与产品边界：

---

# OmniMemora 上线交付工程大纲（给 CC 执行）

## 0. 目标定义

本轮不做：

- 收费
    
- Stripe
    
- 云端增强
    
- 新策略
    
- 新智能能力
    
- 新 retrieval pipeline
    

本轮只做：

- 本地可执行包
    
- 首次启动流程
    
- dashboard 自动打开
    
- demo 数据 / demo query
    
- 一键可见价值
    
- 基础接入命令
    
- 发布物产出
    

---

## 1. 交付标准

### 用户视角完成标准

用户在一台干净机器上：

```text
1. 下载压缩包 / 安装包
2. 双击启动
3. 浏览器自动打开 dashboard
4. 页面出现：
   - OmniMemora is active
   - token savings 数值
   - 最近一次 query 的 savings
5. 无需手改配置
```

### 工程完成标准

```text
1. 可构建 macOS / Windows 二进制
2. 首次运行自动初始化 ~/.omnimemora
3. 自动选择可用端口
4. 自动写入 demo 数据（仅首次）
5. 自动执行 demo search（仅首次）
6. GET /dashboard 可直接展示结果
7. start / status / stop 命令可用
8. 提供 connect codex / connect claude 的最小命令骨架
```

---

# 2. 模块拆分

---

## 模块 A：Release Packaging

### 目标

产出用户可下载的发布物。

### 任务

1. 增加 release build 脚本
    
2. 输出平台二进制：
    
    - macOS amd64
        
    - macOS arm64
        
    - Windows amd64
        
3. 统一发布目录结构
    
4. 生成压缩包
    
5. 生成版本号与校验信息
    

### 推荐目录结构

```text
release/
  omnimemora-darwin-amd64/
    omnimemora
    README.txt
    LICENSE.txt
  omnimemora-darwin-arm64/
    omnimemora
    README.txt
    LICENSE.txt
  omnimemora-windows-amd64/
    omnimemora.exe
    README.txt
    LICENSE.txt
```

### CC 输出物

- `scripts/release/build_release.sh`
    
- `scripts/release/build_release.ps1` 或 Windows zip 生成逻辑
    
- `release/README.txt` 模板
    
- `VERSION` 注入逻辑
    

### 验收

- 本地执行一次命令即可生成所有压缩包
    
- 每个压缩包都能独立运行
    

---

## 模块 B：CLI Lifecycle 命令

### 目标

提供统一启动入口，不让用户碰内部细节。

### 命令范围

```bash
omnimemora start
omnimemora status
omnimemora stop
omnimemora dashboard
```

### start 命令行为

按顺序执行：

```text
1. 检查并创建数据目录
2. 加载/生成默认配置
3. 检测端口是否可用
4. 若 8765 被占用，自动顺延
5. 启动 runtime HTTP server
6. 首次运行时写入 demo 数据
7. 首次运行时执行 demo query
8. 自动打开浏览器到 /dashboard
9. 控制台输出当前状态与 URL
```

### status 命令行为

输出：

```text
- running / stopped
- 当前端口
- dashboard URL
- 数据目录
- version
```

### stop 命令行为

- 优雅关闭 runtime
    
- 正常返回状态
    

### dashboard 命令行为

- 直接打开当前 dashboard URL
    

### CC 输出物

- `cmd/omnimemora/main.go` 扩展命令入口
    
- `internal/cli/start.go`
    
- `internal/cli/status.go`
    
- `internal/cli/stop.go`
    
- `internal/cli/dashboard.go`
    

### 验收

- `start` 成功后，浏览器自动打开
    
- `status` 能正确显示运行态
    
- 重复 `start` 不会重复初始化 demo 数据
    

---

## 模块 C：First-Run Bootstrap

### 目标

把“首次运行体验”做完整。

### 首次运行判定

使用以下任一方案均可，优先简单稳定：

- `~/.omnimemora/bootstrap/first_run_done`
    
- 或配置文件里的 `initialized: true`
    

### 首次运行任务

1. 创建目录：
    
    - `config/`
        
    - `runtime/`
        
    - `logs/`
        
    - `bootstrap/`
        
2. 生成默认配置
    
3. 写入 demo 数据
    
4. 执行 demo query
    
5. 记录 first-run 完成标记
    

### 默认配置要求

- local mode
    
- cloud.enabled = false
    
- 默认 dashboard 端口与 runtime 端口一致
    
- 默认 scope 维持现有安全口径，不暴露给用户
    

### CC 输出物

- `internal/bootstrap/first_run.go`
    
- `internal/bootstrap/default_config.go`
    

### 验收

- 删除 `~/.omnimemora` 后重新运行，可完整初始化
    
- 第二次运行不会重复灌 demo 数据
    

---

## 模块 D：Port Management

### 目标

解决真实用户机器上的端口冲突。

### 行为规则

默认尝试：

```text
8765 → 8766 → 8767 → 8775
```

### 要求

- 自动寻找可用端口
    
- 若发生切换，在终端提示人话
    
- dashboard 打开正确端口
    
- status 返回正确端口
    

### 提示文案

```text
Port 8765 is occupied, switched to 8766.
```

### CC 输出物

- `internal/runtime/port_resolver.go`
    

### 验收

- 手动占用 8765 后仍可成功启动
    
- dashboard 自动跳到新端口
    

---

## 模块 E：Demo Data & Demo Query

### 目标

让用户首次打开时立刻看到价值。

### 任务

1. 内置 5~10 条 demo memory
    
2. 首次运行自动写入
    
3. 首次运行自动执行 1 次 demo search
    
4. 把结果记入本地 metrics，使 dashboard 有内容
    

### demo 数据要求

内容贴近产品用途，例如：

- context optimization
    
- token savings
    
- memory retrieval
    
- long-context compression
    
- agent workflow continuity
    

### demo search 示例

```text
keyword: context optimization
assemble_context: true
context_mode: balanced
context_strategy: auto
```

### 注意

- demo 数据必须写入单独标记，方便后续识别
    
- 不污染真实用户数据统计口径时，至少要可区分 `source=demo`
    

### CC 输出物

- `internal/demo/seed.go`
    
- `internal/demo/query.go`
    

### 验收

- 首次 dashboard 打开就有 savings 数字
    
- 第二次启动不重复增加 demo 数据
    

---

## 模块 F：Dashboard 收口优化

### 目标

把 dashboard 从“工程页”收成“产品页”。

### 页面只保留三块核心区域

#### 1. Hero 区

展示：

- OmniMemora is active
    
- Total saved tokens
    
- Today / Week / Month
    

#### 2. Last Query 区

展示：

- Raw
    
- Compressed
    
- Saved
    
- Compression ratio
    

#### 3. Trend 区

展示：

- 最近 7 天或 30 天 trend
    

### 默认不展示

- strategy
    
- mode
    
- scope
    
- breakdown 细节大段解释
    

这些可作为：

- details 折叠区
    
- `/dashboard?debug=1`
    
- 或页面底部开发信息区
    

### UI 要求

- 极简 HTML/CSS 即可
    
- 不引入重前端框架
    
- 无 JS 复杂依赖也可以
    
- 首屏突出 savings
    

### CC 输出物

- `api/routes.go` 中 `/dashboard` 模板重构
    
- `web/dashboard.html` 若你们拆模板
    

### 验收

- 用户一眼先看到 savings，不先看到技术词
    
- 页面在无数据时也有清晰提示
    

---

## 模块 G：No Data / Error States

### 目标

避免用户打开后“空白”或“像坏了”。

### 需要覆盖的状态

#### 1. 尚无真实查询

文案：

```text
No live queries detected yet.
OmniMemora is running. Connect your agent to start saving tokens.
```

#### 2. demo 已完成但暂无更多数据

文案：

```text
Demo completed. Connect Codex or Claude Code to see live savings.
```

#### 3. runtime 正常但 metrics 为空

显示空态，不报错堆栈

#### 4. dashboard 异常

只显示简洁错误，不显示内部 panic/stack

### CC 输出物

- dashboard 空态模板
    
- runtime 错误页最简处理
    

### 验收

- 任何情况下用户都能知道“现在发生了什么”
    

---

## 模块 H：Minimal Connect Commands

### 目标

为后续接入做好最小命令入口，哪怕先做骨架版。

### 命令

```bash
omnimemora connect codex
omnimemora connect claude
```

### 本轮要求

先不追求全自动 patch 全生态，只做：

1. 输出当前 runtime 地址
    
2. 生成接入提示
    
3. 若能安全修改本地配置，则做最小 patch
    
4. 失败时不破坏现有配置
    

### 最低可接受输出

运行命令后输出：

- runtime URL
    
- 需要填到哪里
    
- 一个最小示例配置片段
    

### 更优实现

- 自动检测常见配置文件路径
    
- 先备份
    
- 再写入/追加配置
    

### CC 输出物

- `internal/connect/codex.go`
    
- `internal/connect/claude.go`
    

### 验收

- 至少具备“半自动可接入”
    
- 不因 patch 失败破坏用户原配置
    

---

## 模块 I：User-Level E2E Tests

### 目标

从“代码能跑”升级到“用户真能用”。

### 必须新增的测试类型

#### 1. First Run E2E

验证：

- 初始化目录
    
- 启动 runtime
    
- demo seed 成功
    
- dashboard 可访问
    

#### 2. Port Conflict E2E

验证：

- 8765 被占用时自动切换
    

#### 3. Repeated Start E2E

验证：

- 重启不重复 seed
    
- 状态稳定
    

#### 4. Dashboard Render E2E

验证：

- dashboard 返回 200
    
- 包含关键字：
    
    - OmniMemora is active
        
    - saved tokens
        

### CC 输出物

- `tests/e2e_first_run_test.go`
    
- `tests/e2e_port_conflict_test.go`
    
- `tests/e2e_dashboard_test.go`
    

### 验收

- 测试通过后，基本可以进入手工发布验证
    

---

# 3. 建议执行顺序

按这个顺序排，不要乱：

## P0

1. CLI start/status/stop
    
2. first-run bootstrap
    
3. port management
    

## P1

4. demo data / demo query
    
5. dashboard 收口
    
6. no-data / error states
    

## P2

7. packaging / release scripts
    
8. connect codex / claude 骨架
    

## P3

9. user-level e2e tests
    
10. 手工验收脚本
    

---

# 4. 给 CC 的硬性约束

把这段原样给它：

```text
本轮目标是“发布可下载版本”，不是继续做平台能力扩展。

严格禁止：
1. 引入新的 context strategy
2. 引入 query understanding / reranking / multi-stage retrieval
3. 引入收费、stripe、billing 相关逻辑
4. 引入云端前置依赖
5. 引入重前端框架或复杂前端工程
6. 暴露 runtime / scope / strategy 等技术概念给普通用户
7. 为兼容旧测试而回退 Phase 3 行为

允许做的只有：
- packaging
- CLI lifecycle
- first-run bootstrap
- demo seed/query
- dashboard polish
- connect commands
- e2e release validation
```

---

# 5. 最终里程碑定义

## Milestone 1：本地跑通

```text
omnimemora start
→ 自动启动
→ 自动打开 dashboard
```

## Milestone 2：首次价值可见

```text
首次运行即出现 demo savings
```

## Milestone 3：可发布

```text
生成 macOS / Windows 发布包
```

## Milestone 4：可接入

```text
至少具备 codex / claude 的最小接入说明或 connect 命令
```

---

# 6. 你给 CC 的单段任务书

你可以直接发这段：

```text
实现 OmniMemora 发布可下载版本的工程交付，目标是“下载→启动→自动打开dashboard→自动看到token savings”。

请按以下模块执行：

1. CLI lifecycle：
   - start / status / stop / dashboard
   - start 时自动初始化数据目录、自动选端口、启动 runtime、打开浏览器

2. First-run bootstrap：
   - 首次运行创建 ~/.omnimemora 目录结构
   - 生成默认配置
   - 仅首次写入 demo 数据并执行 demo query
   - 写入 initialized 标记，防止重复 seed

3. Port management：
   - 默认尝试 8765，冲突时自动顺延
   - dashboard 和 status 必须返回真实端口

4. Dashboard polish：
   - 首屏突出 total/today/week/month saved tokens
   - 展示 last query savings 和 trend
   - 默认隐藏 strategy/mode/scope 等技术信息
   - 处理 no-data 和 error states

5. Release packaging：
   - 产出 macOS amd64/arm64 和 Windows amd64 二进制
   - 输出统一 release 目录和压缩包
   - 附带最小 README

6. Minimal connect commands：
   - connect codex / connect claude
   - 至少输出 runtime URL 和最小配置示例
   - 如做自动 patch，必须先备份，失败不得破坏原配置

7. E2E tests：
   - first run
   - port conflict
   - repeated start
   - dashboard render

约束：
- 不引入任何新智能能力
- 不做收费和云端依赖
- 不为兼容旧测试而回退 Phase 3 行为
- 不引入重前端框架
```
