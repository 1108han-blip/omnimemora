---
doc_id: PROMOTION-EVIDENCE-ROUTING-001
title: OmniMemora Promotion Evidence Routing
owner: doc-team
status: active
version: 1.0.0
effective_date: 2026-04-20
---

# OmniMemora Promotion Evidence Routing

本文檔定義 promotion 結果的正式路由規則，確保每次 `running_reality_promoted` 都有統一的落點、統一的聲明條件、統一的 phase 回填方式。

---

## 1. 三層落點架構

每次 promotion 執行後，結果必須進入三層：

### Layer 1：運行層證據（原始日誌）

| 屬性 | 說明 |
|------|------|
| 位置 | `tools/verification/logs/promotion_YYYYMMDD_HHMMSS.log` |
| 性質 | 原始證據，不做人工改寫 |
| 保留期限 | 永久（不自動清理） |
| 用途 | 爭議時的唯一事實源 |

### Layer 2：執行層記錄（Adoption Verification Records）

| 屬性 | 說明 |
|------|------|
| 位置 | `OmniMemora_Adoption_Verification_Records_YYYY-MM-DD.md` |
| 性質 | 人工歸檔層，結構化摘要 |
| 觸發 | **每次 promotion 都必須寫入** |
| 用途 | 記錄本次 target、repo revision、result、primary breakpoint、warning |

### Layer 3：階段層結論（Phase 文檔）

| 屬性 | 說明 |
|------|------|
| 位置 | phase6 主計劃 / phase6 README |
| 性質 | 已提升的結論，不逐條記錄所有 promotion |
| 觸發 | 只在滿足正式宣告條件時允許寫入 |
| 用途 | 跨執行總結、階段完成聲明 |

---

## 2. 結果路由矩陣

| 結果類型 | → Layer 1 | → Layer 2 | → Layer 3 | 特殊處理 |
|----------|-----------|-----------|-----------|----------|
| `running_reality_promoted` | ✓ 必寫 | ✓ 必寫 | 見章節 3 | 若 runtime+adapter+ui 且全組件健康，可提升為 "full running reality promotion verified" |
| `running_reality_partial` | ✓ 必寫 | ✓ 必寫 | ✗ 不得寫 | 必須附唯一主斷點 |
| `promotion_failed` | ✓ 必寫 | ✓ 必寫 | ✗ 不得寫 | 若觸及當前主線目標，必須形成 phase6 finding |
| `prerequisite_failed` | ✓ 必寫 | ✓ 必寫 | ✗ 不得寫 | 只視為環境/前置條件阻塞，不自動歸類為產品失敗 |

---

## 3. 正式宣告 `running_reality_promoted` 的條件

不是每次腳本輸出成功都能升格成階段結論。正式宣告必須**同時滿足**以下條件：

### 必要條件

| 條件 | 說明 |
|------|------|
| promotion target 已明確 | target 必須是 `runtime+adapter+ui` |
| 結構化日誌已生成 | `promotion_*.log` 存在於 `tools/verification/logs/` |
| runtime health 通過 | `http://127.0.0.1:8765/health = 200` |
| adapter health 通過 | `http://127.0.0.1:18011/health = 200` |
| UI 可訪問 | `http://127.0.0.1:5173/ = 200` |
| UI 與 adapter 基本對位成立 | `5173` 與 `18011/agents/control` 數據基本對位 |
| primary breakpoint | 必須為 `none` |
| warning 狀態 | 若存在 warning，必須在契約中已被定義為**非阻塞 warning** |

### 正式宣告口徑

只有在滿足上述條件時，才允許在 phase6 主計劃或 README 中寫：

```
`running_reality_promoted` 可正式宣告
`full stack promotion verified`
```

---

## 4. Warning 升級規則

### 契約化非阻塞 Warning

以下 warning 已被契約定義為**非阻塞**，存在時不影響 promotion success 判定：

| 組件 | Warning | 契約依據 |
|------|---------|----------|
| Adapter | `plist reality` 未通過 launchctl 檢查 | launchd 重啟覆蓋可見性，API/process 正常時不阻塞 |

### Warning 升級流程

```
warning 出現
    ↓
是否在契約中定義為非阻塞？
    ├── 是 → 記錄為 warning，繼續
    └── 否 → 自動升級為 finding
                 ↓
            是否會導致運行現實判斷歧義？
                ├── 是 → 升級為 P1 finding
                └── 否 → 升級為 P2 finding
```

**核心規則：** warning 不能無限制存在。只有「被契約化的 warning」才能繼續作為 warning 存在。

---

## 5. 文檔回填規則

### 常態回填（每次 promotion）

| 動作 | 寫入位置 |
|------|----------|
| 每次 promotion | adoption verification records |

### 條件回填（满足条件时）

| 條件 | 寫入位置 |
|------|----------|
| 出現新 warning 類別 | adoption contract（第 4 章 warning 清單） |
| 出現新 success 判定條件 | promotion success definition |
| 形成可重複階段結論 | phase6 主計劃或 phase6 README |

### 不需要每次都改的文檔

| 文檔 | 回填條件 |
|------|----------|
| 根 README | 只有當結果跨階段影響已有結論時 |
| phase5 README | 只有當結果跨階段影響已有結論時 |

---

## 6. 路由驗證：使用現有記錄回放

以下用 `2026-04-20` 六組驗證記錄回放路由邏輯，驗證路由是否清晰：

### 樣例 1：Runtime 單組件成功

| 字段 | 值 |
|------|-----|
| Target | `runtime` |
| Result | `running_reality_promoted` |
| Primary Breakpoint | `none` |
| Warning | 無 |

**路由：**
- Layer 1 → `promotion_20260420_000136.log` ✓
- Layer 2 → adoption verification records (A-1) ✓
- Layer 3 → **不寫入**（不是 full stack）

### 樣例 2：Adapter 單組件成功（帶已知非阻塞 Warning）

| 字段 | 值 |
|------|-----|
| Target | `adapter` |
| Result | `running_reality_promoted` |
| Primary Breakpoint | `none` |
| Warning | `plist reality` warning（契約化非阻塞） |

**路由：**
- Layer 1 → `promotion_20260420_000143.log` ✓
- Layer 2 → adoption verification records (A-2)，註明 warning ✓
- Layer 3 → **不寫入**（不是 full stack）

### 樣例 3：Runtime + Adapter + UI 全鏈路成功

| 字段 | 值 |
|------|-----|
| Target | `runtime+adapter+ui` |
| Result | `running_reality_promoted` |
| Primary Breakpoint | `none` |
| Health Check | `8765=200`, `18011=200`, `5173=200` |
| UI Alignment | 成立 |
| Warning | `plist reality`（契約化非阻塞） |

**路由：**
- Layer 1 → `promotion_20260420_000232.log` ✓
- Layer 2 → adoption verification records (C-1) ✓
- Layer 3 → **寫入 phase6 主計劃**，宣告 "full running reality promotion verified" ✓

---

## 7. 快速參考卡

### 結果出來了，寫哪裡？

```
結果出來了
    ↓
是 promotion 日誌？
    └── 是 → Layer 1: tools/verification/logs/promotion_*.log（永遠寫）
    ↓
是 adoption 驗證？
    └── 是 → Layer 2: OmniMemora_Adoption_Verification_Records_*.md（永遠寫）
    ↓
是 full stack (runtime+adapter+ui) 成功，且無未契約化 warning？
    └── 是 → Layer 3: phase6 README 或主計劃（只有這時才寫）
```

### Warning 出來了，怎麼處理？

```
Warning 出來了
    ↓
在契約的「非阻塞 Warning」清單裡？
    ├── 是 → 記錄為 warning，繼續
    └── 否 → 升級為 finding（至少 P2）
```

### 什麼情況算正式宣告成功？

```
正式宣告 success
    ↓
target = runtime+adapter+ui？
    ↓
8765 = 200？
    ↓
18011 = 200？
    ↓
5173 可訪問 + 對位成立？
    ↓
primary_breakpoint = none？
    ↓
所有 warning 都是契約化非阻塞？
    ↓
全部滿足 → 正式宣告 "full running reality promotion verified"
```

---

## 8. 附錄：已有契約化非阻塞 Warning 清單

| 組件 | Warning 描述 | 為何非阻塞 |
|------|-------------|-----------|
| Adapter | `plist reality` 未通過 launchctl 檢查 | launchd 重啟覆蓋可見性，API (`18011/health = 200`) 和 process 正常 |

**更新規則：** 新增契約化非阻塞 warning 必須同時滿足：
1. 已在 production 環境觀察到
2. 明確記錄 warning 現象
3. 明確記錄為何不影響 running reality 判斷
4. 更新本文件第 4 章 warning 清單
5. 更新 `OmniMemora_Adoption_Contract.md`
