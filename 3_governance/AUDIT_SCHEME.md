---
doc_id: GOV-AUDIT-SCHEME-001
title: OmniMemora Audit Trigger Rules and Scheme
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.0.0
effective_date: 2026-04-19
depends_on: []
supersedes: []
last_verified_commit: 2f67f40
---

# AUDIT_SCHEME.md

**Status:** ACTIVE
**Role:** 審計觸發規則、審計執行骨架、結論路由 — 強制執行

---

# 一、審計觸發規則

## 1.1 強制觸發條件

以下任一成立，**必須**觸發審計：

| 觸發類型 | 條件 |
|---------|------|
| **階段末審計** | 當前 active docs 中的 phase README 被標記為 `✅ 已完成` 的階段項累計 `>= 3`，且 worktree 乾淨或已凍結 |
| **Gate 前審計** | 即將進入新主線，且會觸及：產品邊界 / 控制面契約 / running topology / promotion / deployment / 第二真實客戶端擴展 |
| **高風險改動後審計** | 本批改動觸及：ingress/gateway、runtime、control API、attach/install/uninstall、routing state、deployment path/launchd/service/current |
| **現實衝突審計** | doc/repo/candidate/running 任兩層結論互相衝突，或用戶明確指出「當前說法和現實不一致」 |

> **觸發判斷基準**：默認以當前 active docs 中的 phase README 為準，不依賴「主線」等主觀詞。

## 1.2 審計類型

| 類型 | 目標 | 默認輸出 |
|------|------|---------|
| **輕審計** | 判斷是否需要升級 | findings + 結論（Pass / Conditional Pass / Fail） |
| **階段審計** | 判斷某階段是否可正式收口 | findings + 結論 + 必要回填 |
| **專項審計** | 圍繞單一高風險面定位 | 單專題 findings + 結論 |

默認從輕審計開始。發現 `P0/P1` 時才升級。

---

# 二、現實層隔離

每次審計必須明確：**觀察的是哪一層現實**

| 層 | 定義 |
|----|------|
| `doc reality` | active docs / README / SOP / contract 是否自洽 |
| `repo reality` | 當前代碼實現是否與文檔結論一致 |
| `candidate reality` | 隔離候選實例的實際行為是否與結論一致 |
| `running reality` | `~/.omnimemora/service/current` + launchd 實際在線服務 |

驗證記錄屬於**證據登記層**，不構成獨立 reality layer。

審計結論中必須標注每條 finding 針對哪一層。

---

# 三、證據等級

| 等級 | 定義 |
|------|------|
| **A** | 運行實測（live endpoint / launchctl / 實際 curl） |
| **B** | 候選實例行為驗證 |
| **C** | 代碼 / 測試源讀取 |
| **D** | 文檔 / 歷史記錄 |

結論優先級：`A > B > C > D`。**不能用低等級證據覆蓋高等級現實**。

每條 finding 必須同時標注：`[層] + [證據等級]`。

---

# 四、Finding 分級

每條 finding 至少包含：**現實層、證據等級、風險等級、觀察事實、適用範圍**。

| 等級 | 定義 |
|------|------|
| `P0` | 直接推翻當前階段完成結論，或導致產品主路徑失效 |
| `P1` | 不推翻當前結論，但阻塞下一階段 |
| `P2` | 文檔 / 契約 / 展示漂移，需儘快收口 |
| `P3` | 次要優化項，不阻塞 gate |

---

# 五、審計最低觀察清單（輕審計默認）

每次輕審計**至少**覆蓋以下五項：

1. active docs 是否與當前 phase 狀態一致
2. worktree 是否乾淨或已凍結
3. `8765 / 18011 / 5173` 的當前 running reality 是否與 README 結論一致
4. 當前主契約是否存在明顯 drift
5. 當前是否存在會阻塞下一主线的 `P0/P1` finding

輕審計默認不擴面。只有在發現 `P0/P1` 時才升級到專項或階段審計。

---

# 六、審計結論出口

## 6.1 Pass
- 當前階段或目標可收口
- 允許進入下一主線
- README / 驗證記錄回填當前結論

## 6.2 Conditional Pass
- 當前主結論成立
- 但存在 `P1/P2` 漂移
- **必須**形成明確整改輸入：
  - 下一批修什麼
  - **誰來接**（默認為當前執行者）
  - 驗收點是什麼

## 6.3 Fail
- 當前階段不得收口
- 下一主線凍結
- 必須先修當前主斷點
- 必要時生成回滾或降級建議

---

# 七、過渡期獨立性規則

當前不假設存在獨立審計組。過渡期規則：

- 審計者可以與實施者是同一人
- **強制要求**：結論中必須聲明角色重疊
- **複核機制**：
  - 有第二人時：由第二人做輕量複核
  - 無第二人時：將整改輸入和結論寫入公開文檔，作為後續外部或延遲複核依據

---

# 八、輸出收窄（默認模式）

| 輸出項 | 是否強制 |
|--------|---------|
| findings 列表（含分級） | ✅ 強制 |
| 審計結論（Pass / Conditional Pass / Fail） | ✅ 強制 |
| runbook 或執行計劃 | ⚪ 可選 |

**何時升級到完整材料包**：階段審計需對外匯報 / 涉及高風險回滾決策 / 多人協作需明確分工 / 審計結果將作為後續多階段治理基線。

---

# 九、開放項（待確認）

以下項目需在下一階段確認後再補入本文件：

- **「明顯衝突」的客觀判定標準** — 影響 Phase 5 輕審計的 `Pass / Conditional Pass / Fail` 判斷
  - active docs 明显冲突
  - running reality 明显冲突
  - promotion automation 明显冲突
  - dashboard contract 明显冲突

---

# 十、一句話總結

審計不是開發總結。審計回答的是：**「當前說法是否被當前現實支持，如果不被支持，差距在哪、如何分級、後續誰來處理」**。
