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

## 憲法 / Roadmap 關係說明

| 層 | 狀態 |
|----|------|
| `0_blueprint/PRODUCT_CONSTITUTION.md` | 不改 |
| `0_blueprint/ROADMAP.md` | 未更新（phase 仍為 5） |
| `0_blueprint/PRODUCT_DEFINITION.md` | 不改 |
| 本文檔 | 內部執行 workstream 記錄 |

`internal Phase 6 workstream` 只是執行標籤，直到 roadmap 正式更新，phase 編號仍為 5。
