# Phase 6 Plan

## Current Status

### Sub-Workstreams

| Workstream | Status | 文档位置 |
|------------|--------|----------|
| Promotion Workflow Adoption | **已收口 ✓** | 本目录 |
| Promotion Evidence Routing | **已收口 ✓** | 本目录 |
| Promotion Workflow Usage Governance | **已收口 ✓** | `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md` |
| Operational Drift Detection | **已收口 ✓** | `OmniMemora_Operational_Drift_Detection.md` |

---

## Promotion Evidence Routing

**狀態：** 已收口
**收口日期：** 2026-04-20

### 目標

把「已經成立的 adoption 結果」接進 phase docs、驗證記錄、running reality 宣告規則，形成正式 evidence routing。

### 核心變更

1. **三層落點固定**
   - Layer 1：`tools/verification/logs/promotion_*.log`（原始日誌）
   - Layer 2：`OmniMemora_Adoption_Verification_Records_*.md`（執行記錄）
   - Layer 3：phase6 README / 主計劃（只有正式宣告條件滿足時才寫入）

2. **結果路由矩陣固定**
   - `running_reality_promoted` → 寫 Layer 1 + Layer 2，若 full stack 成功可提升到 Layer 3
   - `running_reality_partial` → 寫 Layer 1 + Layer 2，不得寫 Layer 3
   - `promotion_failed` → 寫 Layer 1 + Layer 2，若觸及主線目標需形成 finding
   - `prerequisite_failed` → 寫 Layer 1 + Layer 2，不自動歸類為產品失敗

3. **正式宣告條件固定**
   - 必須是 `runtime+adapter+ui`
   - `8765/health = 200`, `18011/health = 200`, `5173` 可訪問
   - UI 與 adapter 基本對位成立
   - primary breakpoint = `none`
   - 所有 warning 都是契約化非阻塞

4. **Warning 升級規則固定**
   - 契約化非阻塞 warning：僅有 `adapter plist reality`（API/process 正常時）
   - 未契約化 warning → 自動升級為 finding（至少 P2）

### Evidence Routing 文檔

| 文檔 | 說明 |
|------|------|
| [OmniMemora_Promotion_Evidence_Routing.md](./OmniMemora_Promotion_Evidence_Routing.md) | 完整路由規則、快速參考卡、驗證樣例 |

### 路由驗證樣例

| 場景 | Layer 1 | Layer 2 | Layer 3 |
|------|---------|---------|---------|
| runtime 單組件成功 | ✓ 寫 | ✓ 寫 | ✗ 不寫 |
| adapter 單組件成功（帶 plist warning） | ✓ 寫 | ✓ 寫 | ✗ 不寫 |
| runtime+adapter+ui 全鏈路成功 | ✓ 寫 | ✓ 寫 | ✓ 寫（正式宣告） |

### 後續執行者無需判斷

- promotion 成功後寫哪份記錄 ✓
- 哪些 warning 可以忽略 ✓
- 什麼條件下能在 phase6 中正式宣告成功 ✓

---

## Promotion Workflow Adoption

**狀態：** 已收口
**收口日期：** 2026-04-20

### Adoption 文檔四件套

| 文檔 | 說明 |
|------|------|
| [OmniMemora_Adoption_Contract.md](./OmniMemora_Adoption_Contract.md) | 誰可以用、哪些場景必須用、不該用的場景 |
| [OmniMemora_Promotion_Success_Definition.md](./OmniMemora_Promotion_Success_Definition.md) | runtime/adapter/ui 成功標準、組合標準、失敗定義 |
| [OmniMemora_Adoption_Runbook.md](./OmniMemora_Adoption_Runbook.md) | 入口命令、推薦順序、驗證命令、記錄模板 |
| [OmniMemora_Adoption_Verification_Records_2026-04-20.md](./OmniMemora_Adoption_Verification_Records_2026-04-20.md) | 三批六組驗證記錄 |

### 執行入口

```bash
cd /Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora
./tools/promotion/promotion.sh <target>
```

### 驗證矩陣

| Target | Result |
|--------|--------|
| `runtime` | `running_reality_promoted` |
| `adapter` | `running_reality_promoted` |
| `ui` | `running_reality_promoted` |
| `runtime+adapter` | `running_reality_promoted` |
| `adapter+ui` | `running_reality_promoted` |
| `runtime+adapter+ui` | `running_reality_promoted` |

### 已知非阻塞 Warning

| 組件 | Warning |
|------|---------|
| Adapter | `plist reality` 未通過 launchctl 檢查（launchd 重啟覆蓋可見性，API/process 正常） |

---

## Promotion Workflow Usage Governance

**狀態：** 已收口
**收口日期：** 2026-04-20
**文檔位置：** `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md`

### 核心變更

1. **使用邊界三元組**
   - 必須走 promotion：runtime/adapter/UI 變更影響在線行為
   - 禁止繞過：手工複製、繞過 launchd、不經記錄回填
   - 不需要走：純文檔、未準備提升到 running reality

2. **執行前後檢查項固化**
   - 執行前：15 項強制確認
   - 執行後：結構化日誌 + 三層驗證 + 記錄回填

3. **失敗即停住規則**
   - 單組件失敗 = 停止，不繼續組合驗證
   - 組合失敗 = 停止，不並行修多個面
   - warning 未契約化 = 先升級 finding，再繼續

4. **宣告職責規則**
   - 運行成功 ≠ 階段完成
   - 三層宣告（Layer 1/2/3）職責分離

### Governance Validation Record

| 驗證日期 | 場景 | 結果 |
|----------|------|------|
| 2026-04-20 | adapter-only 真實場景 | PASS |

Validation Record：`docs/phase6/adoption_verification/20260420_adapter_only_validation.md`
