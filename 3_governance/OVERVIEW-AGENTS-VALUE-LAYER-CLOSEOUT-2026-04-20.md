---
doc_id: GOV-OVERVIEW-AGENTS-VALUE-LAYER-2026-04-20
title: Overview / Agents Value Layer Enhancement Line — Closeout
owner: doc-team
status: closed
version: 1.0.0
effective_date: 2026-04-20
scope: 5173 control surface — overview/agents information architecture & value visualization
classification: explicit enhancement line outside current roadmap
decision: code-logic pass
---

# Overview / Agents Value Layer Enhancement Line — Closeout

**Date**: 2026-04-20
**Decision**: Enhancement line complete — code-logic pass
**Roadmap Impact**: None — explicit enhancement line outside terminal Phase 5

---

## Worktree Scope (9 files)

| File | Change |
|------|--------|
| `5_connectors/adapter/agent_control_api.py` | Family alias normalization + card-level 24h benefit fields + rescan status feedback |
| `5_connectors/adapter/diagnostics_surface.py` | New `/metrics/summary_24h` endpoint |
| `5_connectors/adapter/metrics_service.py` | `_collect_meters_24h()` + `compute_metrics_summary_24h()` |
| `6_console/demo-dashboard/src/App.tsx` | Dual summary fetch (24h + all-time); HeroMetrics front/back toggle; agent usage click-to-agents jump + highlight |
| `6_console/demo-dashboard/src/api.ts` | `fetchMetricsSummary24h()` + `fetchMetricsTrend()` |
| `6_console/demo-dashboard/src/components/AgentUsagePanel.tsx` | `onAgentClick` prop + row hover cursor |
| `6_console/demo-dashboard/src/components/AgentsDashboard.tsx` | `highlightFamilyId` prop; rescan feedback banner; amber highlight ring |
| `6_console/demo-dashboard/src/components/HeroMetrics.tsx` | Front: 24h default; Back: 7-day trend + all-time vs 24h comparison |
| `6_console/demo-dashboard/src/types.ts` | `MetricsSummary.period`; `MetricsTrend` + `MetricsTrendPoint`; `AgentControlCard` 24h fields; `AgentControlResponse` rescan fields |

---

## Completed Outcomes

### 1. `/agents/control` card-level 24h benefit truth
- Each card now carries `requests_24h`, `saved_tokens_24h`, `savings_ratio_24h`, `last_request_at`
- Family alias normalization maps meter agent IDs (`openclaw`, `openclaw-agent`, `openclaw-bundle-mcp`) to canonical `openclaw` family before aggregation
- Overview `Agent Usage` (② Agent Breakdown) now renders as a direct projection of control cards — no independent usage list

### 2. Overview → Agents jump + highlight
- Clicking any `Agent Usage` row switches to `agents` tab
- URL gains `highlight=<family_id>`
- Target card renders with `border-amber-400 ring-2 ring-amber-400`
- Highlight auto-clears after 3 seconds; URL param also removed

### 3. Core Metrics: 24h front / 7-day trend back + all-time comparison
- **Front** (default): 4 cards — Token Saving %, Saved Tokens (24h), Requests (24h), Avg Context Reduction %
- **Back** (toggle): 7-day bar chart (by-day saved tokens) + two comparison cells — "全历史累计 Saved" (from all-time summary) vs "最近 24h" (from `summary24h`)
- Front/back toggle button labeled "背面 (7天趋势)" / "← 正面 (24h)"

### 4. `rescan` explicit status feedback
- Backend returns `rescan_status` (`added` | `removed` | `no_change`) + `rescan_message` (Chinese)
- Frontend banner: green for `added`, amber for `removed`, gray for `no_change`
- Banner auto-clears after 5 seconds

### 5. Overview / Agents consistency rule
- `Agent Usage` row set = control card set — both sourced from `/agents/control`
- Cards appearing/disappearing on `agents` page are同步 reflected in `Agent Usage` rows on overview

---

## Residual Risk

| Risk | Note |
|------|------|
| TypeScript build not verified | TS compilation environment unavailable (`node` not found in harness). Validation is **static code logic review only**, not build pass. |

---

## Validation Level

- **Python interface logic**: ✅ static code review pass
- **Frontend type & wiring logic**: ✅ static code review pass
- **TypeScript compilation**: ⚠️ environment-limited (not a product semantics failure)
- **Build-verified pass**: ❌ not performed (environment constraint)

---

## Next Steps

- If continued: next logical thread is either (a) overview 下半区链路图形化 (Live Request Flow / Context Before-After / Call Chain as node+edge diagram) or (b) control page object lifecycle management
- This batch does **not** default to continuing expansion — explicit decision required before next batch
- No roadmap advancement implied or triggered by this batch

---

## Relationship to Phase 5

- Phase 5 terminal baseline (`ROADMAP.md`: Phase 5 = "已完成 — 可选") is **unchanged**
- This enhancement line is **explicitly outside the active roadmap**
- Does not advance `ROADMAP.md` phase pointer
- Does not require new phase gate or advancement record
