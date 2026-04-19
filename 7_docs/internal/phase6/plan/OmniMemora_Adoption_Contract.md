---
doc_id: ADOPTION-CONTRACT-001
title: OmniMemora Promotion Adoption Contract
owner: doc-team
status: active
version: 1.0.0
effective_date: 2026-04-20
---

# OmniMemora Promotion Adoption Contract

## 1. 允許操作者

### 默認（可直接執行）
- 當前執行者（維護 running reality 的工程執行者）
- 持有 `~/.omnimemora/service/current` 寫權限的人

### 非默認（需額外確認）
- 未持有 running reality 責任的人不得直接對 `service/current` 做 promotion
- 如需執行，應先諮詢維護者

## 2. 必須走 promotion 的場景

以下場景**必須**使用 `tools/promotion/promotion.sh`：

| 場景 | 說明 |
|------|------|
| 觸及 runtime 變更 | `4_core/local-runtime` 的任何變更要提升到 running reality |
| 觸及 adapter 變更 | `5_connectors/adapter` 的任何變更要提升到 running reality |
| 觸及 UI running reality | `6_console/demo-dashboard` 的任何變更要提升到 running reality |
|要把 repo reality 提升到 `~/.omnimemora/service/current` | 任何需要部署到運行環境的變更 |

## 3. 不該走 promotion 的場景

以下場景**不應該**使用 promotion：

| 場景 | 原因 |
|------|------|
| 純文檔改動 | 不影響運行環境 |
| 僅 repo 內部實現、未準備提升到 running reality | 未達到部署標準 |
| 客戶端本地環境問題 | 不涉及 service/current |
| 憲法/roadmap 文案澄清 | 不影響運行環境 |
| 僅代碼重構（不改 runtime behavior） | 若不改變運行時行為，則無需 promotion |

## 4. Promotion 輸出不是實現完成聲明

**重要區分：**

| 輸出結論 | 含義 |
|----------|------|
| `running_reality_promoted` | **只表示** running reality 提升完成或失敗 |
| `running_reality_promoted` | **不自動等价于**「產品階段完成」 |

Promotion 只負責把構建物部署到運行環境，不負責判斷產品/功能是否「完成」。

## 5. 失敗分類與主斷點

| 分類 | 說明 | 處理方式 |
|------|------|----------|
| `build` | 構建失敗 | 停在 build，不繼續 |
| `file_sync` | 文件同步失敗 | 停在 sync，不繼續 |
| `reload` | 重載失敗 | 停在 reload，不繼續 |
| `health_check` | 運行存活但接口不達標 | 停在 health check，不繼續 |
| `ui_bringup` | UI bring-up 失敗 | 停在 UI bring-up，不繼續 |
| `ui_alignment` | UI 對位失敗 | 停在對位，不繼續 |
| `prerequisite_failed` | 前置條件不滿足 | 停在校驗，不繼續 |

### 失敗處理規則

1. **單組件失敗** → 停在该組件，不繼續跑後續組合
2. **組合失敗** → 標記唯一主斷點，不並行修多個面
3. **若 automation 與文檔口徑 drift** → 先收斂文檔/腳本一致性，再繼續 adoption 驗證
4. **若 launchd 可見性問題但 API/process 正常** → 記為 warning，不自動升級成失敗

## 6. 回填規則

### 每次 adoption 驗證都必須記錄

每次執行 promotion 都**必須**落一條驗證記錄，內容包括：

```
## Promotion Record

**promotion_type**: <runtime|adapter|ui|runtime+adapter|adapter+ui|runtime+adapter+ui>
**input_components**: <涉及的組件>
**running_reality_result**: <healthy|partial|failed>
**base_complete**: <true|false>
**primary_breakpoint**: <若失敗，唯一主斷點>
**repo_revision**: <當前 git revision>
**evidence_level**: <high|medium|low>
```

### 若改變運行狀態判斷或 adoption 規則

- 更新 `OmniMemora_Operationalization_and_Adoption_執行計劃_2026-04-19.md`

### 若影響 phase5 既有結論

- **僅在必要時**回填 phase5 README / 驗證記錄
- **不默認每次都改**
