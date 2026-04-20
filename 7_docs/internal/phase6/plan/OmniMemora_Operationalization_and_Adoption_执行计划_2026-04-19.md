---
doc_id: PLAN-PHASE6-OPERATIONALIZATION-2026-04-19
title: OmniMemora Operationalization and Adoption
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-19
depends_on: [GOV-AUDIT-SCHEME-001]
supersedes: []
last_verified_commit: 5ff812c
---

# Operationalization and Adoption

**Status:** ACTIVE WORKSTREAM
**Label:** internal Phase 6 workstream
**Scope:** 不是新產品 phase，不是 roadmap 改號

---

## 階段定位

本文檔描述 `Operationalization and Adoption`，是 phase5 收口後的下一條內部執行主線。

它不等於正式產品 roadmap phase 改號。`ROADMAP.md` 未被更新前，本文檔所有內容均屬於內部執行口徑。

---

## 主線目標

把 phase5 已完成的東西，變成可持續運行的工程實踐：

- `tools/promotion/` 從「已建好」到「真實使用」
- promotion workflow 可被正式宣告成功或失敗
- adoption 邊界明確：誰可以用、什麼場景用、什麼場景不該用

---

## 第一子線：Promotion Workflow Adoption

### 狀態：**已收口 ✓**

| 完成標準 | 狀態 |
|----------|------|
| 四個問題已回答 | ✓ |
| 六個組合驗證通過 | ✓ |
| adoption 文檔四件套落地 | ✓ |
| `running_reality_promoted` 可正式宣告 | ✓ |

**收口日期：** 2026-04-20
**Repo Revision：** d627029

### Adoption 文檔四件套

| 文檔 | 說明 |
|------|------|
| `OmniMemora_Adoption_Contract.md` | 誰可以用、哪些場景必須用、不該用的場景 |
| `OmniMemora_Promotion_Success_Definition.md` | runtime/adapter/ui 成功標準、組合標準、失敗定義 |
| `OmniMemora_Adoption_Runbook.md` | 入口命令、推薦順序、驗證命令、記錄模板 |
| `OmniMemora_Adoption_Verification_Records_2026-04-20.md` | 三批六組驗證記錄 |

### 已知非阻塞 Warning

| 組件 | Warning | 狀態 |
|------|---------|------|
| Adapter | `plist reality` 未通過 launchctl 檢查 | 已知非阻塞，不影響 `running_reality_promoted` 結論 |

### 收口結論

1. `running_reality_promoted` 已可正式宣告
2. 後續執行者不需要再重新定義 adoption 規則
3. adapter 的 plist warning 屬於已知非阻塞 warning
4. 執行 `tools/promotion/promotion.sh <target>` 即完成 promotion 工作流

---

## 第二子線：Promotion Evidence Routing

### 狀態：**已收口 ✓**

| 完成標準 | 狀態 |
|----------|------|
| 三層落點固定 | ✓ |
| 結果路由矩陣固定 | ✓ |
| 正式宣告條件固定 | ✓ |
| Warning 升級規則固定 | ✓ |

**收口日期：** 2026-04-20
**Repo Revision：** d627029

### Evidence Routing 文檔

| 文檔 | 說明 |
|------|------|
| `OmniMemora_Promotion_Evidence_Routing.md` | 三層落點、路由矩陣、宣告條件、Warning 規則、快速參考卡 |

### 收口結論

1. 三層落點已固定：原始日誌 → 執行記錄 → 階段結論
2. 結果路由矩陣已固定：四種結果各有所歸
3. 正式宣告 `running_reality_promoted` 的條件已固定（七項必要條件）
4. Warning 升級規則已固定：只有契約化 warning 才能繼續作為 warning
5. 後續執行者不需要再臨場判斷寫哪裡、何時能宣告成功

---

## 第三子線：Operational Drift Detection

### 狀態：**已收口 ✓**

| 完成標準 | 狀態 |
|----------|------|
| `operational_drift_check.py` 可執行並通過 smoke test | ✓ |
| Drift register 模板創建 | ✓ |
| `promotion.sh` 更新為寫入 deployed-state marker | ✓ |
| 本文檔更新為引用本 workstream | ✓ |
| Phase6 plan README 更新為引用本 workstream | ✓ |
| 一次真實 promotion 整合驗證完成 | ✓ |

**收口日期：** 2026-04-20
**Repo Revision：** 843eea5
**Adoption Gate：** `./tools/promotion/promotion.sh adapter` (RIR-1) — PASSED
**Marker:** `~/.omnimemora/service/current/.omnimemora_promotion_state.json` — written and verified
**Drift Check Post-Promotion:** 0 signals, exit 0
**已解決信號：** ADE-001（root README phase entry → phase6）
**已知非阻塞 Warning：** Adapter plist reality（per adoption contract）

### 收口結論

1. `operational_drift_check.py` 已完成並與 `promotion.sh` 整合
2. Deployed-state marker 機制已驗證可用
3. Drift checker 可正確讀取新 log/marker 組合
4. ADE-001 已關閉
5. Phase6 plan README 已更新為 `已收口 ✓`
6. 後續執行者不需要再臨場判斷 drift check 路由

---

## 第四子線：Promotion Outcome Reporting

### 狀態：**已收口 ✓**

| 完成標準 | 狀態 |
|----------|------|
| Canonical outcome vocabulary 定義 | ✓ |
| Layer 2 標準欄位固定 | ✓ |
| Declaration status 判定邏輯固化 | ✓ |
| Layer 3 / Root README 寫入規則固定 | ✓ |
| 結果判定決策樹覆蓋全4種 outcome | ✓ |
| 5 日誌 replay 測試全部通過 | ✓ |

**收口日期：** 2026-04-20
**Repo Revision：** d943c84
**文檔位置：** `OmniMemora_Promotion_Outcome_Reporting_Contract.md`

### Canonical Outcome Vocabulary

| Value | 意義 |
|-------|------|
| `running_reality_promoted` | 全部目標組件成功 promote，無未契約化 warning |
| `running_reality_partial` | 部分成功，但不是全部 |
| `promotion_failed` | 執行中斷，未完成 promotion |
| `prerequisite_failed` | 前置條件不滿足，未進入執行 |

### Layer 2 標準欄位

`target` / `datetime` / `repo_revision` / `result` / `primary_breakpoint` / `warning_status` / `declaration_status`

### Declaration Status 判定

`record only` / `phase_conclusion_allowed` / `readme_surface_allowed`

### Replay 測試結果

| # | 日誌 | result | declaration_status | 結論 |
|---|------|--------|-------------------|------|
| R-1 | `promotion_20260420_000136.log` (runtime only) | `running_reality_promoted` | `record only` | ✓ PASS |
| R-2 | `promotion_20260420_000143.log` (adapter only, plist warning) | `running_reality_promoted` | `record only` | ✓ PASS |
| R-3 | `promotion_20260420_000151.log` (runtime+adapter+ui full stack) | `running_reality_promoted` | `readme_surface_allowed` | ✓ PASS |
| R-4 | `promotion_20260420_004133.log` (adapter+ui) | `running_reality_promoted` | `phase_conclusion_allowed` | ✓ PASS |
| R-5 | `promotion_20260420_000203.log` (adapter only, plist warning) | `running_reality_promoted` | `record only` | ✓ PASS |

### 收口結論

1. 每次 promotion 的結果報告格式已固定，無需臨場判斷
2. `declaration_status` 決策樹已覆蓋全部4種 outcome
3. Layer 3 / README 寫入條件已明確定義
4. 後續執行者不需要再判斷「結果出來後寫哪裡」

---

## 憲法 / Roadmap 關係說明

| 層 | 狀態 |
|----|------|
| `0_blueprint/PRODUCT_CONSTITUTION.md` | 不改 |
| `0_blueprint/ROADMAP.md` | 未更新（phase 仍為 5） |
| `0_blueprint/PRODUCT_DEFINITION.md` | 不改 |
| 本文檔 | 內部執行 workstream 記錄 |

`internal Phase 6 workstream` 只是執行標籤，直到 roadmap 正式更新，phase 編號仍為 5。
