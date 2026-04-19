# OmniMemora Promotion Automation

## 概述

统一 promotion 入口，将 runtime / adapter / UI 从"人工按 runbook 执行"推进成自动化流程。

## 入口

```bash
./tools/promotion/promotion.sh <target>
```

### 支持的目标

| 目标 | 说明 |
|------|------|
| `runtime` | 仅 runtime |
| `adapter` | 仅 adapter |
| `ui` | 仅 UI |
| `runtime+adapter` | runtime + adapter |
| `adapter+ui` | adapter + UI |
| `runtime+adapter+ui` | 全部组件 |

## 前置条件校验

自动化入口在执行前会校验：

1. 当前目录是 git worktree
2. promotion 目标已明确
3. 源码目录存在（4_core/local-runtime, 5_connectors/adapter, 6_console/demo-dashboard）
4. 必要的构建工具可用（Go, Node.js, npm 等）

## 组件自动化

### Runtime Promotion

1. 从 `4_core/local-runtime` 构建
2. 输出到 `~/.omnimemora/service/current/tools/omnimemora-runtime`
3. 通过 launchd 受控重载
4. 验证：
   - `launchctl print gui/$(id -u)/com.omnimemora.runtime`
   - `http://127.0.0.1:8765/health`

### Adapter Promotion

1. 分析实际运行文件集合
2. 只同步运行所需 Python 文件到 `~/.omnimemora/service/current`
3. 通过 launchd 重启 adapter
4. 三层验证：
   - plist reality
   - process reality
   - API reality (`:18011`)

### UI Promotion

1. 检查 Node.js / npm
2. `npm install`（如需要）
3. `npm run build`
4. `npm run dev`
5. 验证：
   - `http://127.0.0.1:5173/`
   - `http://127.0.0.1:5173/agents?tenant=all`
6. 基本对位（与 adapter API 对照）

## 结构化输出

Promotion 结果写入日志，包含：

- promotion 目标组件
- repo revision
- running reality 组件状态
- 每一步成功/失败
- 最终结论

### 最终结论

| 结论 | 说明 |
|------|------|
| `running_reality_promoted` | 全部组件成功 |
| `running_reality_partial` | 部分成功 |
| `promotion_failed` | 失败 |
| `prerequisite_failed` | 前置条件不满足 |

## 失败分类

- `build` - 构建失败
- `file_sync` - 文件同步失败
- `reload` - 重载失败
- `health_check` - 运行存活但接口不达标
- `ui_bringup` - UI bring-up 失败
- `ui_alignment` - UI 对位失败

## 日志位置

```
tools/verification/logs/promotion_YYYYMMDD_HHMMSS.log
```

## 记录材料

自动化输出标准化记录材料，供后续写入验证记录：

```
## Promotion Record

**promotion_type**: runtime
**input_components**: local-runtime
**running_reality_result**: healthy
**base_complete**: true
**primary_breakpoint**: none
```