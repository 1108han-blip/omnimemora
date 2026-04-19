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

### 目標
讓 `tools/promotion/` 成為真實工作流，驗證運轉起來的效果。

### 成功標準（四個問題）

1. **誰可以用**：哪些人/角色有權限調用 `tools/promotion/`
2. **哪些場景必須用**：哪些變更必須走 promotion，哪些場景不該用
3. **promotion 成功後必須回填哪些記錄**：哪些文件需要更新，什麼內容不能遺漏
4. **什麼條件下可以正式宣告 `running_reality_promoted`**：成功的判斷基準是什麼

### 明確排除
- 再新建 promotion automation（已落地）
- 再改 `tools/promotion/` 的基礎架構
- 把 promotion 變成 ci/cd 強制流程（當前沒有這個需求）

---

## 憲法 / Roadmap 關係說明

| 層 | 狀態 |
|----|------|
| `0_blueprint/PRODUCT_CONSTITUTION.md` | 不改 |
| `0_blueprint/ROADMAP.md` | 未更新（phase 仍為 5） |
| `0_blueprint/PRODUCT_DEFINITION.md` | 不改 |
| 本文檔 | 內部執行 workstream 記錄 |

`internal Phase 6 workstream` 只是執行標籤，直到 roadmap 正式更新，phase 編號仍為 5。
