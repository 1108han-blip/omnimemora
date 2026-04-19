# Phase 6 Plan

## Current Status

### Sub-Workstreams

| Workstream | Status |
|------------|--------|
| Promotion Workflow Adoption | **已收口 ✓** |

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
