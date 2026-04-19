---
doc_id: PROMOTION-SUCCESS-DEF-001
title: OmniMemora Promotion Success Definition
owner: doc-team
status: active
version: 1.0.0
effective_date: 2026-04-20
---

# OmniMemora Promotion Success Definition

本文檔定義 `running_reality_promoted` 的正式標準，用於判斷 promotion 是否成功。

---

## 1. Runtime-Only 成功標準

| 檢查項 | 標準 |
|--------|------|
| 構建成功 | `go build` 在 `4_core/local-runtime` 目錄執行成功 |
| 部署成功 | 二進制文件存在於 `~/.omnimemora/service/current/tools/omnimemora-runtime` |
| 重載成功 | launchd 重載或受控 fallback 完成 |
| 健康檢查 | `http://127.0.0.1:8765/health` 返回 200 |

**結論關鍵字：** `runtime:promoted`

---

## 2. Adapter-Only 成功標準

| 檢查層 | 標準 |
|--------|------|
| Python 文件同步成功 | 所有 `.py` 文件（除 `__pycache__`）同步到 `~/.omnimemora/service/current/5_connectors/adapter/` |
| launcher 同步成功 | `_run_adapter.py` 存在於 `~/.omnimemora/service/current/tools/` |
| 重啟成功 | launchd restart 或 fallback 完成 |
| API 健康 | `http://127.0.0.1:18011/health` 返回 200 |

### Adapter plist reality Warning 處理

| 情況 | 判斷 |
|------|------|
| `launchctl print` 可見 | 視為正常 |
| `launchctl print` 不可見，但 API/process 正常 | **記為 `plist reality warning`，不自動判失敗** |

**結論關鍵字：** `adapter:promoted`

---

## 3. UI-Only 成功標準

| 檢查項 | 標準 |
|--------|------|
| 環境正確 | `PATH=/usr/local/bin:$PATH` |
| npm build 成功 | `npm run build` 在 `6_console/demo-dashboard` 目錄執行成功 |
| 端口在線 | `5173` 可訪問 |
| 根路徑可訪問 | `http://127.0.0.1:5173/` 返回 200 |
| Agents 頁面可訪問 | `http://127.0.0.1:5173/agents?tenant=all` 返回 200 |
| 基本對位成立 | UI 與 `18011 /agents/control` 數據基本對位 |

**結論關鍵字：** `ui:promoted`

---

## 4. 組合成功標準

### Runtime + Adapter

- Runtime: 滿足 runtime-only 成功標準
- Adapter: 滿足 adapter-only 成功標準
- 兩者同時運行，端口 `8765` 和 `18011` 均返回 200

**結論關鍵字：** `runtime:promoted` + `adapter:promoted`

### Adapter + UI

- Adapter: 滿足 adapter-only 成功標準
- UI: 滿足 ui-only 成功標準
- UI 基本對位基於 adapter API (`18011`)，**不是** runtime API (`8765`)

**結論關鍵字：** `adapter:promoted` + `ui:promoted`

### Runtime + Adapter + UI (Full Stack)

- Runtime: 滿足 runtime-only 成功標準
- Adapter: 滿足 adapter-only 成功標準
- UI: 滿足 ui-only 成功標準
- 三組件均返回 200
- 結構化日誌生成成功

**結論關鍵字：** `running_reality_promoted`

---

## 5. 失敗結論定義

### `running_reality_partial`

| 條件 | 說明 |
|------|------|
| 部分組件成功 | 至少一個組件 promotion 成功，但不是全部 |

### `promotion_failed`

| 條件 | 說明 |
|------|------|
| 關鍵組件失敗 | runtime 或 adapter promotion 失敗 |
| 組合中斷 | 任何單組件失敗導致組合無法繼續 |

### `prerequisite_failed`

| 條件 | 說明 |
|------|------|
| 前置條件不滿足 | 目錄不存在、工具鏈缺失、worktree 問題 |

---

## 6. 結構化日誌格式

每個 promotion 執行的日誌包含：

```
promotion_target: <target>
repo_revision: <git revision>
running_reality_before: runtime=<state> adapter=<state> ui=<state>
running_reality_after: runtime=<state> adapter=<state> ui=<state>
final_status: <running_reality_promoted|running_reality_partial|promotion_failed|prerequisite_failed>
log_file: <path>
```

---

## 7. 驗證矩陣

| Target | 必須通過 | 可選 Warning |
|--------|----------|-------------|
| `runtime` | build + sync + reload + health | - |
| `adapter` | file_sync + restart + API | plist reality |
| `ui` | build + bringup + root + agents + alignment | - |
| `runtime+adapter` | runtime 全過 + adapter 全過 | plist reality |
| `adapter+ui` | adapter 全過 + ui 全過 | plist reality |
| `runtime+adapter+ui` | runtime 全過 + adapter 全過 + ui 全過 | plist reality |
