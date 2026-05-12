---
doc_id: ADOPTION-RUNBOOK-001
title: OmniMemora Promotion Adoption Runbook
owner: doc-team
status: active
version: 1.0.0
effective_date: 2026-04-20
---

# OmniMemora Promotion Adoption Runbook

> **2026-05-10 supersession**: 当前用户控制/展示面是 OmniMemora Desktop app。`5173` 仅 legacy/dev；本 runbook 中 `5173` 检查仅用于显式 legacy dashboard 任务。

## 1. 入口命令

```bash
cd /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora
./tools/promotion/promotion.sh <target>
```

### 支持的 Targets

| Target | 說明 |
|--------|------|
| `runtime` | 僅 runtime |
| `adapter` | 僅 adapter |
| `ui` | 僅 UI |
| `runtime+adapter` | runtime + adapter |
| `adapter+ui` | adapter + UI |
| `runtime+adapter+ui` | 全部組件 |

---

## 2. 推薦執行順序

### Batch A：單組件驗證

```bash
# 1. Runtime 單組件
./tools/promotion/promotion.sh runtime

# 2. Adapter 單組件
./tools/promotion/promotion.sh adapter

# 3. UI 單組件
./tools/promotion/promotion.sh ui
```

### Batch B：組合驗證

```bash
# 4. Runtime + Adapter 組合
./tools/promotion/promotion.sh runtime+adapter

# 5. Adapter + UI 組合
./tools/promotion/promotion.sh adapter+ui
```

### Batch C：全鏈路驗證

```bash
# 6. 全鏈路
./tools/promotion/promotion.sh runtime+adapter+ui
```

---

## 3. 驗證命令（手動核查）

### 健康檢查

```bash
# Runtime
curl -sf http://127.0.0.1:8765/health && echo "runtime:OK"

# Adapter
curl -sf http://127.0.0.1:18011/health && echo "adapter:OK"

# Desktop GUI（当前默认）
echo "Desktop app should be openable and able to refresh data from 18011"

# Legacy UI（仅在显式 legacy dashboard 验证任务中执行）
curl -sf http://127.0.0.1:5173/ && echo "legacy-ui:OK"
```

### Launchd 檢查

```bash
# Runtime plist
launchctl print gui/$(id -u)/com.omnimemora.runtime

# Adapter plist
launchctl print gui/$(id -u)/com.omnimemora.adapter
```

### Process 檢查

```bash
# Runtime process
pgrep -f "omnimemora-runtime.*serve"

# Adapter process
pgrep -f "_run_adapter"

# UI process
pgrep -f "vite"
```

---

## 4. 記錄模板

### Promotion Record Template

```markdown
## Promotion Record - YYYYMMDD_HHMMSS

**promotion_type**: <runtime|adapter|ui|runtime+adapter|adapter+ui|runtime+adapter+ui>
**target**: <exact target passed to script>
**input_components**: <components involved>
**repo_revision**: <git rev-parse --short HEAD>
**execution_time**: <YYYY-MM-DD HH:MM:SS>

**running_reality_before**:
- runtime: <healthy|not_running|unreachable>
- adapter: <healthy|not_running|unreachable>
- ui: <healthy|not_running|no_node>

**running_reality_after**:
- runtime: <healthy|not_running|unreachable>
- adapter: <healthy|not_running|unreachable>
- ui: <healthy|not_running|no_node>

**result**: <running_reality_promoted|running_reality_partial|promotion_failed|prerequisite_failed>
**primary_breakpoint**: <none|build|file_sync|reload|health_check|ui_bringup|ui_alignment|prerequisite_failed|unknown>
**evidence_level**: <high|medium|low>

**log_file**: <path to promotion log>

**notes**:
- <any observations, warnings, or issues>
```

### Full Stack Adoption Verified Template

```markdown
## Full Stack Adoption Verified - YYYYMMDD_HHMMSS

**date**: <YYYY-MM-DD>
**repo_revision**: <git revision>
**promotion_target**: runtime+adapter+ui

**component_results**:
- runtime: <promoted|failed>
- adapter: <promoted|failed with warning>
- ui: <promoted|failed>

**running_reality_final**: <healthy|partial|failed>
**full_stack_adoption**: <true|false>

**evidence**:
- Runtime health: <curl result>
- Adapter health: <curl result>
- Desktop app refresh from 18011: <pass|fail>
- Legacy UI root (optional): <curl result|skipped>
- Legacy UI agents (optional): <curl result|skipped>

**primary_breakpoint**: <none|build|file_sync|reload|health_check|ui_bringup|ui_alignment|prerequisite_failed|unknown>
**next_steps**: <if any>
```

`unknown` 表示 promotion log 只給出 `component:failed`，沒有可操作的 failure reason；此時應人工回看對應 promotion log。

---

## 5. 常見問題處理

### Adapter plist reality Warning

**現象：** `launchctl print` 無輸出，但 API 和 process 正常

**處理：**
1. 確認 `curl http://127.0.0.1:18011/health` 返回 200
2. 確認 `pgrep -f "_run_adapter"` 有結果
3. 記錄為 `plist reality warning`，不升級為失敗
4. 繼續執行

### UI 對位失敗

**現象：** Desktop app（或 legacy UI）顯示與 adapter API 不對位

**處理：**
1. 檢查 adapter `/agents/control` 響應
2. 檢查 UI 請求是否發往正確的 adapter 端口
3. 記錄為 `ui_alignment` 主斷點
4. 停止執行，不繼續組合

### Build 失敗

**現象：** `go build` 或 `npm run build` 失敗

**處理：**
1. 查看對應日誌
2. 記錄為 `build` 主斷點
3. 停止執行，不嘗試部署

---

## 6. 日誌位置

所有 promotion 相關日誌位於：

```
/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/tools/verification/logs/
```

| 文件類型 | 模式 |
|----------|------|
| Promotion 主日誌 | `promotion_YYYYMMDD_HHMMSS.log` |
| Runtime stdout | `runtime_promotion.out.log` |
| Runtime stderr | `runtime_promotion.err.log` |
| Adapter stdout | `adapter_promotion.out.log` |
| Adapter stderr | `adapter_promotion.err.log` |
| UI build | `ui_build.log` |
| UI dev | `ui_dev.log` |
| UI npm install | `ui_npm_install.log` |

---

## 7. 前置條件

執行 promotion 前確認：

1. 當前目錄是 git worktree
2. 源碼目錄存在：
   - `4_core/local-runtime`
   - `5_connectors/adapter`
   - `6_console/demo-dashboard`（如 target 包含 ui）
3. 必要工具可用：Go, Node.js, npm, python3
4. `~/.omnimemora/service/current` 目錄可寫
