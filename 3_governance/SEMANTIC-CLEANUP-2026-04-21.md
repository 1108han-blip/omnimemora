---
doc_id: GOV-SEMANTIC-CLEANUP-2026-04-21
title: OpenClaw Semantic Cleanup & UI Truth Disclosure (Product Boundary Priority)
owner: doc-team
status: active
version: 2.0.0
effective_date: 2026-04-21
scope: Semantic cleanup — model naming + three-section truth surface + product boundary clarity
---

# OpenClaw Semantic Cleanup & UI Truth Disclosure (Product Boundary Priority)

**Date**: 2026-04-21
**Batch Type**: Semantic cleanup + UI truth disclosure + product boundary enforcement
**Not**: Main route recovery, new phase advancement, or audit

---

## 1. Batch Goal

Eliminate the three-layer conflation in current OpenClaw user-facing surfaces and establish product boundary clarity:

- `OmniMemora` is the gateway/ingress name (`18011`), **NOT a model name**
- `MiniMax-M2.7` is the current OpenClaw main model truth
- `18011/sse` is the MCP tool attachment; `18011/llm` is an internal debug path, **NOT a user-facing model**
- No proven "OpenClaw main conversation stable via 18011" conclusion exists yet
- Product **observes** user-side configuration; it does **not rename or productize** user configs

### Core Principle: Product Boundary First

- `18011` is the **product entry truth**
- User-side `provider / base_url / model / auth` are **user-side truths**
- Product only declares "did I receive a real request, did I complete compile/forward" — it does **NOT** declare "which model you should use"

---

## 2. Changes Made

### 2.1 OpenClaw User Config — `~/.openclaw/openclaw.json`

| Change | Before | After |
|--------|--------|-------|
| Default visible model alias | `omnimemora/gemma4:26b` → "OmniMemora Gemma 4" | Removed from `agents.defaults.models` |
| Primary model | `minimax/MiniMax-M2.7` | Unchanged |
| MCP server | `omnimemora` → `http://127.0.0.1:18011/sse` | Unchanged |
| Provider `omnimemora` in `models.providers` | Retained for internal/debug use | Retained, NOT user-facing |

**Note**: Removing from `agents.defaults.models` alias list hides it from default model selection UI without deleting the provider configuration. The MCP attachment remains intact.

### 2.2 `18011 /agents/control` — Five-Field Truth Surface

The backend now provides a structured truth field group per control card:

| Field | Type | Description |
|-------|------|-------------|
| `integration_truth` | `detached \| mcp_attached \| attached_with_backup` | User-side MCP integration state |
| `route_truth` | `off \| intent_on \| effective` | Product routing intent and effectiveness |
| `traffic_truth` | `no_recent_evidence \| internal_only \| real_request_observed` | Whether real product requests reached 18011 |
| `observed_client_truth` | `{provider, model, base_url, base_url_class}` | Observed user-side config (observation only, not product naming) |
| `truth_message` | `string` | User-facing explanation of current state |

**Derivation rules**:
- `integration_truth`: derived from `installed` + `backup_available` on the runtime payload
- `route_truth`: derived from `routing_enabled` + runtime health
- `traffic_truth`: derived from `compile_store` telemetry — only `openclaw` family is checked for `real_request_observed`; others default to `no_recent_evidence` unless compile events exist
- `observed_client_truth`: passed through from runtime payload, classified by `base_url_class` (local / remote_http / remote_websocket / unknown)
- `truth_message`: assembled from integration + route + traffic truth states

**Evidence rules for `traffic_truth`**:
- `real_request_observed`: requires compile events with `proxied_requests > 0` AND at least one of `compile_success` or `compile_skipped` (not all failed/bypassed)
- `internal_only`: openclaw with compile events but only bootstrap/handshake quality
- `no_recent_evidence`: no compile events in window

### 2.3 5173 `AgentsDashboard` — Three-Section Truth Surface

The agents page now displays a three-badge truth surface per card:

| Section | Badge Colors | Labels |
|---------|-------------|--------|
| Integration | gray=detached, blue=mcp_attached, green=attached_with_backup | 未接入 / MCP / 接入+備份 |
| Route | gray=off, amber=intent_on, green=effective | 路由關閉 / 路由意圖 / 路由生效 |
| Traffic | gray=no_recent_evidence, blue=internal_only, green=real_request_observed | 無證據 / 僅內部 / 真實流量 |

The message area now shows `truth_message` (from backend) with fallback to `message`.

---

## 3. What This Batch Does NOT Claim

- ❌ NOT main route recovery — does not restore OpenClaw main requests via `18011`
- ❌ NOT a phase advancement
- ❌ NOT a new audit
- ❌ Does not prove `18011/llm` is a production model
- ❌ Does not change any backend API contract (fields are backward-compatible)
- ❌ Product does not rename user-side configurations as "product models"

---

## 4. Current State Summary

| Layer | Current Truth |
|-------|--------------|
| MCP attachment | ✅ Via `18011/sse` — confirmed |
| Main model | `MiniMax-M2.7` — confirmed |
| Local provider `omnimemora` | Present as internal debug path; NOT user-facing |
| `OmniMemora` naming | Gateway/ingress name only; not a model |
| Main conversation via `18011` | **Not yet evidenced** |
| User-side observed truth | `observed_client_truth.base_url_class` shows "local" for 127.0.0.1 paths |

---

## 5. Three-Section Truth Architecture

```
┌─────────────────────────────────────────────────────┐
│  Integration Truth    Route Truth    Traffic Truth  │
│  (MCP attached?)     (routing?)    (real traffic?) │
├─────────────────────────────────────────────────────┤
│  detached / mcp_attached / attached_with_backup    │
│  off / intent_on / effective                        │
│  no_recent_evidence / internal_only / real_request  │
└─────────────────────────────────────────────────────┘
Product only observes user config via observed_client_truth.
Product does NOT rename user models as "product models".
```

---

## 6. Verification Checkpoints

| Check | Expected | Status |
|-------|----------|--------|
| `~/.openclaw/openclaw.json` models alias | No "OmniMemora Gemma 4" entry | ✅ |
| `agents.defaults.model.primary` | Still `minimax/MiniMax-M2.7` | ✅ |
| `18011/sse` MCP | Config intact | ✅ |
| `integration_truth` field | Present on all cards from `/agents/control` | ✅ |
| `route_truth` field | Present on all cards | ✅ |
| `traffic_truth` field | Present, values derived from compile_store | ✅ |
| `observed_client_truth` field | Observed user config, not product rename | ✅ |
| `truth_message` field | User-facing explanation | ✅ |
| Three-section badge in AgentsDashboard | Shows integration + route + traffic badges | ✅ |
| No "OmniMemora Gemma 4" in default user-facing UI | Enforced via removed model alias | ✅ |

---

## 7. Exit State

Semantic cleanup batch **complete**. Product boundary is now clearly expressed:
- User-side config is observed, not product-renamed
- Truth surface shows three independent dimensions (integration / route / traffic)
- `routing_enabled=true` does not automatically mean real traffic is observed
- Subsequent work that re-establishes real main request path through `18011` requires separate documentation update and will update `traffic_truth` to `real_request_observed`.