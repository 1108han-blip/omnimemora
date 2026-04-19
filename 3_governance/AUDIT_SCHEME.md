---
doc_id: GOV-AUDIT-SCHEME-001
title: OmniMemora Audit Trigger Rules and Scheme
owner: doc-team
reviewers: [arch-lead]
status: active
version: 1.1.0
effective_date: 2026-04-20
depends_on: []
supersedes: []
last_verified_commit: 7dc3045
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

# 九、明顯衝突判定標準

「明顯衝突」是指 active docs 的階段結論與 A/B/C 級證據之間存在直接且可驗證的矛盾，無需主觀解讀即可判定。

---

## 9.1 四類明顯衝突

### Ⅰ. Active Docs 明顯衝突

**定義：** active docs / phase README 明確宣告某結論成立，但同一階段內更高等級證據（A/B/C）直接否定該結論。

**典型場景：**
- README 寫「完整 running reality 成立」，但 live curl 證明 `5173` 離線
- Phase README 聲稱某組件處於健康狀態，但同時期 A 級實測返回非 200

**默認等級：** 至少 `P1`

### Ⅱ. Running Reality 明顯衝突

**定義：** README 或階段結論聲稱基礎/完整 running reality 成立，但對應組件 health / UI / control API 不可達，或關鍵端口狀態不符。

**典型場景：**
- 文檔聲稱 `8765/health = 200`，但 A 級 curl 實際返回 500 或超時
- 文檔聲稱 UI 已上線，但 `5173` 完全不可達

**注意：** 必須有 A 級實測才能判定 running reality 明顯衝突。沒有實測的情況下，僅因「未驗證」不能直接判為明顯衝突（參見 RECORD-B-076 校準案例）。

**默認等級：** 至少 `P1`

### Ⅲ. Promotion Automation 明顯衝突

**定義：** automation 文檔或腳本宣稱某 target 成功，但輸出結論與 adoption contract / success definition 的正式條件明顯不一致。

**典型場景：**
- 腳本輸出 `running_reality_promoted`，但 `primary_breakpoint ≠ none`
- 腳本輸出 `running_reality_promoted`，但存在未契約化的 warning
- 文檔聲稱「full stack promotion verified」，但未滿足 `runtime+adapter+ui` 七項正式宣告條件（見 `OmniMemora_Promotion_Evidence_Routing.md`）
- 單組件 promotion 被錯誤地當作 full-stack 結論寫入 phase README

**默認等級：** 至少 `P1`

### Ⅳ. Dashboard Contract 明顯衝突

**定義：** 用戶面默認路徑仍暴露 raw/internal identity，或 canonical identity / diagnostics 隔離規則被當前 UI 直接違反，或 overview / control / flow 在已固定 truth source 上出現直接矛盾。

**典型場景：**
- 默認首頁暴露內部 identity字段，而非 canonical identity
- Overview 與 Control 使用的 truth source 不一致且直接矛盾

**默認等級：**
- 若只在展示層（不影響控制判斷）：`P2`
- 若導致控制判斷失真：`P1`

---

## 9.2 等級映射速查

| 明顯衝突類型 | 默認等級 | 升級條件 |
|-------------|---------|---------|
| Active Docs 直接推翻階段結論 | `P0` | — |
| Active Docs 不推翻階段結論 | `P1` | — |
| Running Reality 端口不可達 | `P1` | 直接推翻階段結論時升至 `P0` |
| Promotion Automation 結論與 success definition 不符 | `P1` | 直接推翻階段結論時升至 `P0` |
| Dashboard Contract 展示層漂移 | `P2` | 控制判斷失真時升至 `P1` |

---

## 9.3 校準案例

### 案例 A：RECORD-B-076（Phase 5 輕審計）

**背景：** Phase 5 輕審計得出 Conditional Pass，發現 F-01（P2 文檔內部結論自洽性問題）。

**為何 F-01 不是明顯衝突：**
- F-01 的問題是「文檔內部有失真引用」（如 README 指向不存在的 SSOT 文件）
- 這屬於「文檔內部一致性漂移」，不是「文檔結論與更高級證據直接矛盾」
- 同場景的 A 級實測結果（8765+18011+5173 均在線，口徑一致）**支持**了 phase5 主結論
- 因此 F-01 是 `P2`（文檔/展示漂移），不是明顯衝突

**若在當前標準下重新審視：**
- 該審計發現的「README 指向不存在文件」→ 文檔內部引用失真 → 構成 active docs 漂移
- 但 phase5 README 的核心結論（running reality 成立）與 A 級證據一致 → 不構成 active docs 明顯衝突
- 故 F-01 定為 `P2` 仍然成立

### 案例 B：Promotion Evidence Routing 的 Full-Stack Success

**背景：** `runtime+adapter+ui` 全鏈路 promotion 成功，可提升至 phase6 層結論。

**什麼情況會構成 Promotion Automation 明顯衝突：**
- 若腳本輸出 `running_reality_promoted`，但 `primary_breakpoint` 記為 `build` → 結論與 success definition 不符 → 明顯衝突 `P1`
- 若文檔聲稱「full running reality promotion verified」，但未滿足七項正式宣告條件（如 UI 未達 200）→ 結論超越實際 → 明顯衝突 `P1`
- 若存在未契約化 warning（如新出現的 adapter 層面 plist 以外 warning）且未被記錄 → warning 未被認領 → 明顯衝突 `P1`

**什麼情況 NOT 構成明顯衝突：**
- `plist reality` warning 已存在，API/process 正常，符合契約 → 不是衝突，是契約化 warning
- 單組件 promotion 結論寫入 adoption verification records → 符合三層落點規則 → 不是衝突

---

## 9.4 非明顯衝突的邊界說明

以下情況**不是**明顯衝突：

| 情況 | 為何不是 |
|------|---------|
| 尚未做 A 級實測，只能用 C/D 級證據 | 證據等級不夠，不能直接判定衝突 |
| 文檔內部引用失真但核心結論被更高級證據支持 | 文檔漂移，不是結論衝突 |
| 候選現實領先於已提交現實 | 候選不等於事實，需收斂後才能作準 |
| 已知非阻塞 warning 已契約化記錄 | 契約化 warning 是已知狀態，不是衝突 |

---

# 十、一句話總結

審計不是開發總結。審計回答的是：**「當前說法是否被當前現實支持，如果不被支持，差距在哪、如何分級、後續誰來處理」**。
