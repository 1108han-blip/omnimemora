# PRODUCT_CONFIGURATION_AND_BOUNDARY_BASELINE.md

**Status:** FINAL  
**Role:** 產品配置真相與邊界基線  
**Effective Date:** 2026-04-18  
**Supersedes:** 所有與「靜默模型映射」「產品另存一套 LLM 真相」「將網絡出口算入產品邊界」「默認自動接管 agent」衝突的舊表述

---

## 1. 收斂結論

OmniMemora 的產品責任不是替用戶重新定義 LLM 配置，而是：

> **承接用戶已選的 Agent LLM 配置語義，控制入口，完成 compile，再透明送出。**

---

## 2. 固定口徑

### 2.1 必經入口口徑

> **OmniMemora 只有在用戶於 UI 明確開啟某個 agent 的產品路由後，才成為該 agent 的必經入口。未開啟時，不得默認接管。**

### 2.2 透明語義口徑

> **OmniMemora 不應靜默改變用戶的 Provider / base_url / model / auth source 語義。**

### 2.3 配置真相口徑

> **用戶端 Agent 配置是 LLM 真相來源；產品應引用、鏡像或同步這份真相，而不是長期維護第二套會漂移的配置系統。**

### 2.4 控制權口徑

> **是否接入 OmniMemora、是否啟用 OmniMemora，控制權只在 `:5173` UI，由用戶決定；不在 agent 自主行為，也不在啟動腳本默認行為。**

---

## 3. 三段產品邊界

### 3.1 用戶端接入層

包括但不限於：

- Agent 原始配置
- wrapper
- env/base_url/provider/model 改寫
- 用戶 OAuth / API key 來源

這一層屬於**用戶端接入層**，不算產品核心本體。

接入層需要分成兩種動作：

- 低頻接入動作：install / attach / detach / restore
- 高频路由動作：enable / disable product routing

### 3.2 產品層

從 `:18011` 開始，到產品內部 compile/runtime 能力結束為止。

包括：

- `18011` Adapter / Gateway / 入口編排層
- `llm_proxy`
- `gateway_compile`
- `runtime_bridge`
- `8765` local runtime

### 3.3 產品外出口層

包括：

- 系統代理
- Clash / TUN / VPN / 分流
- 真實上游 LLM

這一層可以被觀測，但**不屬於產品責任邊界**。

---

## 4. 模型與上游配置原則

### 4.1 禁止靜默模型重寫

以下行為視為產品錯誤，不應作為正式默認策略：

- `gpt-5.4 -> gemma4:26b`
- 未告知用戶就把雲端模型改成本地模型
- 把 Agent 指定的模型名稱悄悄重寫到另一個 Provider

### 4.2 默認保留用戶語義

默認規則應為：

- 保留用戶請求的 `provider/base_url/model/auth source`
- 只有在顯式配置了某個 profile 或 mapping 時，才允許重寫
- mapping 必須配置化，而不是硬編碼成產品默認值

### 4.3 配置漂移原則

若用戶在 Agent 端更換：

- LLM provider
- API key
- OAuth profile
- model
- base_url

則產品必須能：

- 重新同步
- 或引用同一來源

而不是要求工程團隊長期手工維護第二份獨立配置。

### 4.4 attach / restore 原則

attach 不是高頻產品開關，而是低頻接入動作。

固定要求：

- attach 前必須自動備份原始配置
- detach / uninstall 時必須恢復備份
- 不允許只刪除 OmniMemora 片段卻不恢復原始 provider 狀態

---

## 5. OAuth / API 憑據原則

產品正式方向應是：

- API key：引用 env / SecretRef / 已存在配置來源
- OAuth：引用 Agent 現有 auth store，或經統一憑據橋接入

不應以「把 token 複製進產品配置」作為長期方案。

---

## 5.1 Truth Governance v2 固定口徑

### 唯一執行契約

所有 Claude / Codex / OpenClaw 請求在真正送出上游前，必須先解析為同一個 `ResolvedTruthContract`。

這個 contract 至少固定承載：

- `provider_requested / provider_ref / provider_resolved`
- `base_url_requested / endpoint_ref / base_url_resolved`
- `model_requested / model_ref / model_resolved`
- `auth_ref / auth_source / auth_resolved`
- `wire_api_resolved`
- `fallback_used`
- `resolution_rule / resolution_reason`
- `conflict_detected / conflict_types / source_priority_chain`

`llm_proxy` 不應再分散內聯決定主要 truth；它只能消費 resolved contract。

### 固定優先級鏈

Truth Source Bridge v2 的預設 precedence 順序固定為：

1. `emergency_runtime_override`
2. `runtime_override`
3. `product_policy_binding`
4. `agent_truth_bridge`
5. `agent_payload_explicit`
6. `local_default_profile`
7. `provider_default`

若未來調整此順序，必須同步更新測試、事件字段與本基線文檔。

### 衝突顯式化口徑

多來源不一致時，不允許只保留最終值而吞掉衝突。

事件與聚合層至少要顯式輸出：

- `conflict_detected`
- `conflict_types`
- `resolution_rule`
- `resolution_reason`
- `source_priority_chain`

衝突類型至少覆蓋：

- `provider_conflict`
- `base_url_conflict`
- `model_conflict`
- `auth_conflict`
- `wire_api_conflict`
- `fallback_policy_conflict`
- `base_url_provider_mismatch`
- `model_provider_mismatch`
- `auth_provider_mismatch`
- `wire_api_provider_mismatch`
- `unknown_model_alias`
- `unknown_endpoint_ref`
- `illegal_override_attempt`

### 引用化口徑

產品內部應優先以 canonical refs 傳播真相，而不是依賴散落字符串：

- `provider_ref`
- `endpoint_ref`
- `model_ref`
- `auth_ref`

字符串值可以保留作為 requested/resolved 顯示層，但不應再是唯一治理依據。

---

## 6. 測試與驗證原則

### 6.1 本機網絡背景

本機若已存在：

- 系統代理
- Clash
- TUN
- VPN

測試必須承認這個現實背景。

允許驗證：

- `Agent -> OmniMemora -> 本機現有網絡出口 -> 上游`

但不應為了測試方便，強行要求繞過本機既有代理體系。

### 6.2 產品內觀測口徑

工程/UI/驗證口徑應優先表述為：

- 是否進入產品
- 是否完成編譯
- 是否正確送出到產品外
- 是否收到返回
- 是否進入受控旁路

而不是把「是否經過 Clash」表述成產品責任。

---

## 7. 18011 與 8765 的固定定位

- `18011` 不是單純轉發層，而是產品入口與編排層
- `8765` 不是獨立對外產品入口，而是產品內部 context compile / runtime 能力層
- 產品核心目標是 **context compile 以節省 token**
- Agent ID、多租戶、隔離等模組存在的目的，是避免多 Agent / 多實例編譯串線，而不是把產品擴張成獨立記憶平台

### 7.1 5173 的固定定位

- `5173` 是父級 agent 控制卡片所在的正式 UI 控制面
- `5173` 不只是觀測面，也承擔接入與路由控制
- 卡片粒度默認保持在父級可管理對象
- 臨時 subagent 只作為運行態統計與活動信息展示，不默認升級成獨立控制卡片

---

## 8. 文檔一致性任務清單

### P0：必須同步到 LIVE 文檔

- [ ] [README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/README.md) 不再使用任何會導向「產品自帶固定模型映射」的表述
- [ ] [README.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/README.md) 補入「雙開關模型、禁止默認 auto-attach、父級卡片粒度」
- [ ] [CONSTITUTION.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/CONSTITUTION.md) 明確寫出「受控旁路」和「產品不重定義用戶上游語義」
- [ ] [0_blueprint/DEFAULT_IN_CONTROL_PLANE.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/DEFAULT_IN_CONTROL_PLANE.md) 增補「禁止靜默模型重寫」
- [ ] [9_adr/ADR-0003-interface-access-paths.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/9_adr/ADR-0003-interface-access-paths.md) 明確三段邊界與 `18011/8765` 層級
- [ ] [0_blueprint/PRODUCT_DEFINITION.md](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/0_blueprint/PRODUCT_DEFINITION.md) 補入「用戶端配置是真相來源」與「產品外出口不屬於產品責任」

### P1：接入與工程文檔需要同步

- [ ] OpenClaw / Codex / Claude 接入文檔改為「產品承接用戶現有 LLM 語義」，不再鼓勵產品側硬編碼模型映射
- [ ] 安裝/attach 腳本說明補充「哪些是用戶端接入層配置，哪些是產品層配置」，並明確 attach 是低頻接入動作
- [ ] UI/觀測文檔統一改成「送出到產品外」而不是「是否經過 Clash」
- [ ] Dashboard/UI 文檔補入「高頻路由開關」與「低頻接入開關」分離原則

### P2：代碼與文檔對齊待辦

- [x] 移除或配置化目前 OpenAI 模型默認 remap 邏輯
- [x] 驗證 OpenClaw 常用 OAuth/GPT 路徑可經 `18011` 進入產品、完成 compile 並正常返回
- [x] 落地 Truth Source Bridge v1：統一輸出 `provider/base_url/model/auth/fallback` 的最終解析結果到 proxy/compile 事件
- [ ] 定義產品如何正式引用 Agent OAuth / API key 真相來源
- [ ] 為 OpenClaw/Codex/Claude 的 LLM 真相同步做成統一配置橋，而不是各自散落 patch

---

## 9. 下一步執行優先級

1. 定義產品如何正式引用 Agent OAuth / API key 真相來源，減少手工雙邊配置。
2. 為 OpenClaw/Codex/Claude 的 LLM 真相同步收斂成統一配置橋。
3. 批量同步 LIVE 文檔與 UI 文案，讓產品邊界、受控旁路和觀測口徑一致。
