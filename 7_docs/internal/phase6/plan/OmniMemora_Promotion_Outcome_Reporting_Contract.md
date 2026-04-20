---
doc_id: PROMOTION-OUTCOME-REPORTING-001
title: OmniMemora Promotion Outcome Reporting Contract
owner: doc-team
status: active
version: 1.0.0
effective_date: 2026-04-20
---

# OmniMemora Promotion Outcome Reporting Contract

本文檔定義 promotion 結果的**讀者面向報告格式**，規範：
- 每次 promotion 執行後，誰寫什麼、寫到哪裡
- 何時只寫 record，何時允許提升為 phase 結論
- 何時允許提升到根 README

**目標**：讓 promotion 結果在任何地方都能被一致地閱讀，無需理解底層腳本邏輯。

---

## 1. Canonical Outcome Vocabulary

每次 promotion 執行後的 `final_status` 必須是以下四個值之一：

| Value | 意義 | Layer 1 | Layer 2 | Layer 3 | README |
|-------|------|---------|---------|---------|--------|
| `running_reality_promoted` | 全部目標組件成功promote，無未契約化warning | ✓ 寫 | ✓ 寫 | 見§3 | 見§4 |
| `running_reality_partial` | 部分目標組件成功，但不是全部 | ✓ 寫 | ✓ 寫 | ✗ | ✗ |
| `promotion_failed` | 執行中斷，未完成promotion | ✓ 寫 | ✓ 寫 | ✗ | ✗ |
| `prerequisite_failed` | 前置條件不滿足（環境/工具/路徑），未進入執行 | ✓ 寫 | ✓ 寫 | ✗ | ✗ |

**定義：**

- `running_reality_promoted`：promotion target 包含的所有組件都達到了各自的成功標準（見 [OmniMemora_Promotion_Success_Definition.md](./OmniMemora_Promotion_Success_Definition.md)），且不存在任何未契約化的 warning。
- `running_reality_partial`：至少一個組件 promotion 成功，但不是全部。組合驗證在中間某步停止。
- `promotion_failed`：任何關鍵步驟（build/file_sync/reload/health_check/ui_bringup/ui_alignment）失敗，且未能通過 fallback 完成。
- `prerequisite_failed`：執行在到達第一步之前就因為目錄不存在、工具鏈缺失、worktree 問題等原因停止。

---

## 2. Layer 2 — Adoption Verification Record

### 2.1 觸發條件

**每次 promotion 都必須寫 Layer 2**，無論 result 是哪個值。

### 2.2 標準寫入位置

```
7_docs/internal/phase6/plan/OmniMemora_Adoption_Verification_Records_<YYYY-MM-DD>.md
```

文件名中的日期 = promotion 實際執行的日期。

### 2.3 標準欄位（Layer 2 Reader-Facing Summary）

每條記錄必須包含以下所有欄位：

| 欄位 | 說明 | 示例 |
|------|------|------|
| `target` | 執行時指定的 target | `runtime` / `adapter+ui` / `runtime+adapter+ui` |
| `datetime` | promotion 開始的ISO 8601時間 | `2026-04-20T08:42:15` |
| `repo_revision` | 執行時的 git commit (short) | `d0d4fe7` |
| `result` | 從 §1 canonical vocabulary 中取值 | `running_reality_promoted` |
| `primary_breakpoint` | 若失敗，唯一主斷點；若成功則為 `none` | `health_check` / `none` |
| `warning_status` | 存在的 warning 及其契約狀態；若無 warning 為 `none` | `plist reality (contractized non-blocking)` / `none` |
| `declaration_status` | 本記錄是否可作為 phase 結論依據 | `record only` / `phase_conclusion_allowed` / `readme_surface_allowed` |

### 2.4 Warning Status 契約清單（截至2026-04-20）

| 組件 | Warning | 契約狀態 |
|------|---------|----------|
| Adapter | `plist reality` 未通過 launchctl 檢查 | 契約化非阻塞 |

> 新增契約化非阻塞 warning 必須同時記錄：現象描述、為何不影響 running reality 判斷、更新本欄位、通知 phase owner。

### 2.5 Declaration Status 判定邏輯

```
declaration_status:
    ↓
result == running_reality_promoted？
    ↓
target == runtime+adapter+ui？
    ↓
primary_breakpoint == none？
    ↓
所有 warning 都是契約化非阻塞？
    ↓
全部滿足 → "readme_surface_allowed"（含 phase 結論）
否則 → "phase_conclusion_allowed"（作為 Layer 3 依據，但不寫 README）
否則 → "record only"
```

---

## 3. Layer 3 — Phase-Level Declaration

### 3.1 觸發條件

只有當 Layer 2 的 `declaration_status` 為 `readme_surface_allowed` 時，才能寫入 Layer 3。

### 3.2 寫入位置

- **Phase 主計劃**：`7_docs/internal/phase6/plan/README.md`
- **Phase README（若存在）**：`7_docs/internal/phase6/README.md`

### 3.3 寫入格式

Layer 3 宣告使用以下固定格式：

```
## Promotion Outcome — <YYYY-MM-DD>

**Target**: <target>
**Result**: <result>
**Repo Revision**: <short-hash>
**Date**: <ISO 8601>
**Primary Breakpoint**: <breakpoint or none>
**Warning Status**: <warning or none>
**Status**: <phase conclusion>
```

### 3.4 何時允許寫 Layer 3

| 結果 | Layer 3 允許？ | 理由 |
|------|---------------|------|
| `running_reality_promoted`（full stack，無未契約化 warning） | ✓ 是 | 正式宣告條件滿足 |
| `running_reality_promoted`（單組件） | ✗ 否 | 單組件 promotion 不是階段結論 |
| `running_reality_partial` | ✗ 否 | 部分成功不是結論 |
| `promotion_failed` | ✗ 否 | 失敗需要記錄為 finding，不寫結論 |
| `prerequisite_failed` | ✗ 否 | 前置失敗不等於產品失敗 |

---

## 4. Root README — 什麼時候寫

### 4.1 觸發條件

只有在以下**所有條件同時滿足**時，才能寫入根 `README.md` 的主內容區（而非歷史存檔）：

1. Layer 2 `declaration_status` = `readme_surface_allowed`
2. 且本次 promotion 代表一個**里程碑**（非例行單組件 promotion）

### 4.2 里程碑判定

| 場景 | 是否里程碑 |
|------|-----------|
| `runtime+adapter+ui` 全鏈路成功，無未契約化 warning | ✓ 是 |
| 某個 phase 的核心目標第一次達到 | ✓ 是 |
| 單組件 promotion（runtime 或 adapter） | ✗ 否 |
| 例行 daily promotion（已多次重複的 full stack） | ✗ 否 |

### 4.3 禁止在 Root README 中出現的內容

- 單個組件的 promotion 結果
- 失敗的 promotion 記錄
- 沒有經過 Layer 2 記錄驗證的聲明

---

## 5. 結果判定決策樹

```
promotion 執行完成
    ↓
final_status = ？
    ├── running_reality_promoted
    │       ↓
    │   target = runtime+adapter+ui？
    │       ├── 是 → primary_breakpoint = none？→ 所有 warning 契約化非阻塞？
    │       │           ├── 全部滿足 → Layer 2: declaration_status=readme_surface_allowed
    │       │           │                    → Layer 3: 寫 phase plan
    │       │           │                    → README: 若為里程碑則寫
    │       │           └── 任一不滿足 → Layer 2: declaration_status=phase_conclusion_allowed
    │       └── 否（單組件）→ Layer 2: declaration_status=record only
    │                          → Layer 3: ✗ 不寫
    │                          → README: ✗ 不寫
    ├── running_reality_partial
    │       → Layer 2: declaration_status=record only
    │       → Layer 3: ✗ 不寫
    ├── promotion_failed
    │       → Layer 2: primary_breakpoint=唯一主斷點, declaration_status=record only
    │       → Layer 3: ✗ 不寫（若觸及主線目標，須形成 finding）
    └── prerequisite_failed
            → Layer 2: declaration_status=record only
            → Layer 3: ✗ 不寫
```

---

## 6. Replay 測試矩陣（實現者驗證用）

| 現有日誌 | 預期 result | 預期 declaration_status | 預期 Layer 3 | 預期 README |
|---------|-------------|------------------------|-------------|-------------|
| 單 runtime 成功日誌 | `running_reality_promoted` | `record only` | ✗ 不寫 | ✗ 不寫 |
| 單 adapter 成功日誌（帶 plist warning） | `running_reality_promoted` | `record only` | ✗ 不寫 | ✗ 不寫 |
| `runtime+adapter+ui` 全鏈路成功日誌 | `running_reality_promoted` | `readme_surface_allowed` | ✓ 寫 phase plan | 若里程碑則寫 |
| `runtime+adapter` 成功（非 full stack）日誌 | `running_reality_promoted` | `phase_conclusion_allowed` | ✗ 寫 | ✗ 不寫 |
| 任一帶非契約化 warning 的日誌 | `running_reality_promoted` | `phase_conclusion_allowed` | ✗ 寫 | ✗ 不寫 |

---

## 7. 現有文檔引用

本文檔不替換以下文檔：

| 文檔 | 關係 |
|------|------|
| [OmniMemora_Promotion_Success_Definition.md](./OmniMemora_Promotion_Success_Definition.md) | 定義各組件成功標準（§1 的上游） |
| [OmniMemora_Promotion_Evidence_Routing.md](./OmniMemora_Promotion_Evidence_Routing.md) | 定義三層落點架構（§2-3 的上層框架） |
| [OmniMemora_Operational_Drift_Detection.md](./OmniMemora_Operational_Drift_Detection.md) | 負責 drift 檢測，本 contract 不觸發 drift 信號 |

---

## 8. 契約狀態

| 欄位 | 值 |
|------|---|
| Status | `active` |
| Version | 1.0.0 |
| Effective Date | 2026-04-20 |
| Validation Date | 2026-04-20 |

### 8.1 Replay 測試結果

| # | 日誌 | result | declaration_status | Layer 3 | README | 結論 |
|---|------|--------|-------------------|---------|--------|------|
| R-1 | `promotion_20260420_000136.log` (runtime only) | `running_reality_promoted` | `record only` | ✗ 不寫 | ✗ 不寫 | ✓ PASS |
| R-2 | `promotion_20260420_000143.log` (adapter only, plist warning) | `running_reality_promoted` | `record only` | ✗ 不寫 | ✗ 不寫 | ✓ PASS |
| R-3 | `promotion_20260420_000151.log` (runtime+adapter+ui full stack) | `running_reality_promoted` | `readme_surface_allowed` | ✓ 寫 phase plan | 若里程碑則寫 | ✓ PASS |
| R-4 | `promotion_20260420_004133.log` (adapter+ui, non-full-stack) | `running_reality_promoted` | `phase_conclusion_allowed` | ✗ 不寫 | ✗ 不寫 | ✓ PASS |
| R-5 | `promotion_20260420_000203.log` (adapter only, plist warning) | `running_reality_promoted` | `record only` | ✗ 不寫 | ✗ 不寫 | ✓ PASS |

> 所有 5 個 replay 測試通過。沒有找到 `promotion_failed` 或 `prerequisite_failed` 的單獨日誌（這些結果寫入 Layer 2 但日誌本身不會單獨存在於 Phase6 的驗證範圍內）。`promotion_20260420_000216.log` 與 R-5 完全相同，跳過重複。

**更新規則：** 本 contract 為只讀約定。若需調整 reporting 格式，必須先更新本 contract 並走 adoption 流程。
