---
doc_id: GOV-RECORD-2026-04-20-D-PATCH
title: "Governance Record: D Item Patch — AUDIT_SCHEME.md Section 9"
owner: doc-team
date: 2026-04-20
type: governance_patch
status: closed
---

# Governance Record: D Item Patch — AUDIT_SCHEME.md Section 9

**日期：** 2026-04-20
**類型：** 治理制度補丁
**影響範圍：** `3_governance/AUDIT_SCHEME.md` 第九節

---

## 補丁內容

### AUDIT_SCHEME.md 第九節：明顯衝突判定標準（新增）

**替換內容：** 將原第九節「開放項（待確認）」替換為正式「明顯衝突判定標準」。

**新增四類明顯衝突定義：**

| 類型 | 定義 | 默認等級 |
|------|------|---------|
| Active Docs 明顯衝突 | active docs 結論與 A/B/C 級證據直接矛盾 | 至少 P1 |
| Running Reality 明顯衝突 | 文檔聲稱 running reality 成立，但端口/組件不可達 | 至少 P1 |
| Promotion Automation 明顯衝突 | automation 輸出結論與 success definition 正式條件不符 | 至少 P1 |
| Dashboard Contract 明顯衝突 | 用戶面暴露 internal identity 或 truth source 直接矛盾 | P2（展示層）/ P1（控制失真） |

**附帶內容：**
- 等級映射速查表
- 校準案例：RECORD-B-076（F-01 為何是 P2 不是明顯衝突）
- 校準案例：Promotion Evidence Routing（何時構成 Promotion Automation 明顯衝突）
- 非明顯衝突邊界說明

**版本更新：** `v1.0.0` → `v1.1.0`

---

## 驗證狀態

| 檢查項 | 結果 |
|--------|------|
| 第九節不再是開放項 | ✓ |
| 四類定義完整、可直接引用 | ✓ |
| 每類都能映射到 P0/P1/P2 | ✓ |
| RECORD-B-076 回放：歷史結論仍成立 | ✓ |
| Promotion Evidence Routing 回放：無歧義 | ✓ |
| 不新增開放性術語 | ✓ |

---

## 後續輕審計引用方式

後續每次輕審計在判斷 `Pass / Conditional Pass / Fail` 時，應直接引用：

> 「根據 AUDIT_SCHEME.md v1.1.0 第九節，明顯衝突判定標準如下……」

無需再口頭補充解釋。
