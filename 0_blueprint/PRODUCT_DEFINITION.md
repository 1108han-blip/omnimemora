# OmniMemora — Product Definition

> ⚠️ **2026-04-16 更新：** 本文件作為當前產品定義基線，正式收斂「入口映射原則」。
> 舊版「optional call / default-in optimization layer」等表述，如與本文衝突，一律以本文為準。

---

## 1. 核心定位

OmniMemora 是一個**本地 LLM Gateway（入口層）**，並帶有一個由 UI 控制的 agent 接入/路由控制面。

其責任是在用戶明確開啟某個 agent 後，接管該 agent 的 LLM 請求路徑，並在轉發前完成 memory recall、context compile、token 壓縮與 context 注入。

OmniMemora 的產品邊界是**入口層治理**，不是模型供應方，也不是 Agent 工具插件。

### One-line Vision

> Keep it on, or things get worse.

---

## 2. 設計原則（必須遵守）

### 原則 1：不改用戶上游語義

OmniMemora 不改變以下內容：

- 用戶原本使用的 LLM Provider（如 MiniMax / OpenAI / Anthropic）
- 用戶原本使用的 API Key / OAuth 登錄態 / 賬號歸屬
- 用戶原本配置的 model 名稱
- 用戶原本的 provider 選擇與調用邏輯

統一要求：

> 用戶原來怎麼連上游 LLM，OmniMemora 接入後應保持該語義不變。

補充要求：

- 用戶端已配置的 `provider / base_url / auth / model` 應視為**第一真相源**
- 產品端優先透傳該真相，不得默認以產品內部模型表覆蓋
- 僅在用戶端未提供足夠上游真相時，產品端才可使用最小必要的 fallback/default

明確禁止：

> 不得把 OmniMemora 做成一個需要持續追蹤市場模型變化、並逐個維護模型適配規則的中心。

### 原則 2：只在用戶授權後接管請求路徑

OmniMemora 的唯一強制行為是：

> 某個 agent 一旦在 UI 中被明確開啟「使用 OmniMemora」，其 LLM 請求必須先進入 OmniMemora Gateway，再由 OmniMemora 轉發到原始上游。

也就是：

```text
Agent -> OmniMemora Gateway -> Original Upstream LLM
```

OmniMemora 接管的是**入口路徑**，不是**模型決定權**；是否接管由用戶 UI 控制，而不是 agent 自主決定。

### 原則 3：透明轉發

Gateway 必須實現 Transparent Forwarding：

- 不改變原始請求語義
- 不破壞原始 provider 調用方式
- 不引入 provider 偽裝
- 不要求用戶重配模型
- 不要求用戶切換既有賬戶體系
- 路由關閉時仍可經過 Gateway，但只能透明直通，不執行 compile / recall / inject

標準轉發路徑：

```text
Agent Request
  -> OmniMemora (compile / recall / inject)
  -> Original Upstream (MiniMax / OpenAI / Anthropic)
```

透明轉發的精確含義：

- 進來是什麼協議，送回上游時仍保持什麼協議
- 產品可修改的是 context 內容與必要的請求內嵌信息，不是外層協議語義
- 產品不得把用戶原有請求改寫成另一種客戶端/上游無法識別的輸出格式

補充判準：

> 協議理解只允許服務於產品功能本身，例如讀取請求、插入 compile 結果、保持原協議返回；不得演變成替用戶重定義接入或替市場模型逐一做產品側適配。

### 原則 4：編譯執行內置於請求路徑

OmniMemora 的核心能力必須在 Gateway 內部自動執行，包括：

- memory recall
- context compile
- token 壓縮
- context 注入

這些能力不作為工具調用暴露給 Agent，也不依賴 Agent 主動觸發。

統一要求：

> 編譯能力屬於入口層內建能力，不屬於 Agent 可選工具能力。

### 原則 5：用戶體驗必須像工具一樣簡單

安裝後必須做到：

- 不要求用戶理解 Gateway 架構
- 不要求用戶重寫複雜配置
- 不要求用戶切換原有模型使用方式
- 不要求用戶理解 attach/detach 與路由控制的底層差異
- 但必須允許用戶在 UI 裡明確控制「接入」與「使用」

用戶感知應統一為：

> 我原來怎麼用，現在還是怎麼用，但上下文效果更好、token 更省。

---

## 3. 非目標（必須明確）

OmniMemora 不做：

- 替代 LLM Provider 本身
- 強制用戶切換模型
- 管理用戶 API Key 生命周期
- 作為一個由 Agent 主動調用的工具插件存在
- 把是否使用 OmniMemora 的決定權交給 Agent
- 通過 prompt 提示、建議或軟約束引導 Agent 使用
- 在檢測到 agent 後自動 attach 或自動開啟產品路由

統一邊界：

> OmniMemora 不是一個由 agent 自主決定是否調用的增強工具；它是一個由用戶在 UI 中顯式控制接入與路由的本地網關層。

---

## 4. 技術實現約束

### 必須實現

- 本地 Gateway 統一入口
- UI 顯式控制的雙開關模型
- 接入前自動備份，卸載時恢復備份
- 純本地模式默認不啟用雲端策略更新與數據上報
- 開啟雲端策略更新時，最小必要遙測數據默認隨之啟用
- 請求級路徑接管，而不是工具級調用
- 基於原始請求語義的上游動態轉發
- 編譯前置執行機制（pre-forward hook）
- 保持原有上游 provider 語義不變的透明轉發能力
- 用戶端 `provider / base_url / auth / model` 的優先透傳
- 同協議接入、同協議送回的最小協議理解層

### 禁止實現

- 修改 Agent 內部邏輯
- 重寫 Agent SDK
- 依賴 prompt 引導觸發使用
- 依賴建議、提示或軟約束讓 Agent 使用 OmniMemora
- 通過 provider 偽裝改變用戶原始模型語義
- 將入口接管降級為可選工具調用
- 將 UI 父級卡片粒度擴張成所有臨時 subagent 都單獨控制
- 將產品做成市場模型白名單/模型適配中心
- 為了接入而重寫用戶原始 `provider / base_url / auth / model` 真相
- 把協議兼容擴大成替用戶重定義上游語義

---

## 5. 架構位置

```text
[ Agent ]
     ↓
[ OmniMemora Gateway ]
     ↓  (compile / recall / inject)
[ Original Upstream LLM ]
     ↓
[ Response -> Agent ]
```

Gateway 位於本機應用層，先於用戶系統代理生效。

它只控制「請求先經過你」，不接管、不破壞用戶原有系統代理、VPN、Clash、TUN 分流體系。

### 固定入口口徑

- `:5173` = 用戶控制入口
- `:18011` = 用戶開啟產品路由後的唯一產品數據入口
- `:8765` = 內部 memory plane

## 5.1 Agent Identity Mature-State Target

本節用於凍結「當前過渡態」與「目標成熟態」的產品約束。後續 identity 實作必須朝成熟態收斂，不得把過渡態誤寫成 current reality 的終態定義。
當前實作被明確認定為過渡態；後續不得繼續圍繞單一客戶端表象做語義修補。
本節與 [ADR-0009-agent-identity-mature-state](/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/9_adr/ADR-0009-agent-identity-mature-state.md) 同步，若有衝突以 ADR-0009 的成熟態契約為準。

### 當前狀態（過渡態，非終態）

- 當前為 canonical-first 過渡實作
- 存在 unmapped passthrough
- control shell 由 family 視角主導

### 目標狀態（成熟態）

產品正式區分三層身份：

- `runtime agent_id`
- `source_agent_id`
- `agent_family`

`runtime agent_id` 是正式 principal：

- 用於 scope
- 用於 memory isolation
- 用於 record attribution
- 用於 metering
- 用於 connector ownership
- 用於 layered integration

`source_agent_id` 是上游輸入身份：

- 完整保留
- 用於對接
- 用於回傳
- 用於診斷
- 用於映射追蹤
- 不自動成為正式 principal

`agent_family` 是 control shell / 聚合視圖：

- 用於 control card
- 用於 family routing
- 用於 summary view
- 不等於正式 principal

### 固定邊界

- `8765` 是 `agent_id` 語義基準層
- `18011` 承擔 admission + preservation
- `5173` 只投影產品真相，不反向定義 identity
- admission 原則：只有穩定、顯式、可復現的 source identity 才能提升為正式 `runtime agent_id`
- 推斷型 identity 不得直接寫入正式 principal

本節只定義成熟態契約，不宣稱 current reality 已達成成熟態。

---

## 6. 工程口徑

### 核心判斷標準

> 這個改動有沒有增強「路徑控制權」？

- 沒有：不應進入主線
- 有：才屬於 OmniMemora 主產品能力

補充判準：

> 控制面入口與產品數據入口不可混寫；`5173` 管控制，`18011` 管數據路徑，`8765` 不對用戶暴露為產品入口。

### 標準入口表達

| Agent | Request Format | OmniMemora Entry | Upstream Role |
|------|----------------|------------------|---------------|
| Claude Code | Anthropic Messages API | `/llm/v1/messages`、`/v1/messages`、`/llm/anthropic`（legacy alias） | 保持原始上游語義 |
| OpenClaw | OpenAI Chat Completions | `/llm/chat` | 保持原始上游語義 |
| Codex CLI | OpenAI-compatible / Responses-compatible | `/v1/chat/completions` 或兼容入口 | 保持原始上游語義 |

### Claude Code ingress contract

- `llm_proxy` 必須保留真實 ingress path
- `gateway_compile` 協議判定必須優先依據真實 ingress path
- 不允許 compile 僅靠 payload 猜測 Anthropic / OpenAI 協議

### Anthropic diagnostics contract

Anthropic payload trace 是正式診斷能力，必須可開關：

- `OMNIMEMORA_TRACE_ANTHROPIC_PAYLOAD=true|false`
- `OMNIMEMORA_TRACE_REDACT=true|false`

默認要求：

- trace 默認關閉
- redact 默認開啟
- trace 需按 `request_id` 串聯 inbound / post-compile / upstream response status

### 核心能力位置

memory recall / context compile / token 壓縮 / context 注入：

- 必須在 Gateway 內部執行
- 必須發生在轉發前
- 不暴露為 Agent 工具

### 上游真相優先級

產品在選擇上游時必須遵守以下優先級：

1. 用戶端當前請求所攜帶的 `provider / base_url / auth / model`
2. 用戶端已配置且可觀測到的 agent/provider truth
3. 產品端最小 fallback/default

約束：

- 產品端 fallback 只能補缺，不能反客為主
- 產品端不得因市場模型增多而持續把模型名映射維護變成主設計
- 產品端應主要按**協議族**維持最小理解能力，而不是按**模型市場**維持逐個適配能力

---

## 7. 一句話產品定義

OmniMemora 是一個不改變用戶模型選擇的本地 LLM Gateway；用戶可在 UI 中決定哪些 agent 接入、哪些 agent 啟用產品路由，並在啟用後獲得上下文優化與 token 壓縮。

---

## 8. 團隊統一認知語句

> 我們不是在做一個「讓 Agent 調用的工具」，而是在做一個「Agent 無法繞開的入口層」。
