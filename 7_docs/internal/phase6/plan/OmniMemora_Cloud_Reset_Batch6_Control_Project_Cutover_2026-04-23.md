# OmniMemora Cloud Reset Batch 6 Control Project Cutover (2026-04-23)

> **2026-05-10 supersession**: 本记录中的 `5173` 可达性为历史非回归证据。当前产品口径为 Desktop app 控制/展示面；`5173` 仅 legacy/dev。

## Scope
- Batch type: replacement control-entry establishment + official domain rebind
- In-scope:
  - create replacement Cloudflare control-plane entry project (Workers)
  - rebind `doloclaw.com` and `www.doloclaw.com` serving path to replacement project
  - remove official domain carrying role from `openviking-site`
- Out-of-scope:
  - no changes to local execution topology (`18011` / `8765` / `5173`)
  - no candidate-source implementation changes
  - no Railway ingress reintroduction

## Replacement Project
- Type: Cloudflare Workers script
- Name: `omnimemora-control-entry`
- Role: control entry / control-plane ingress shell
- Explicit boundary:
  - no memory plane execution
  - no compile engine responsibility
  - no `/memory/*` legacy semantics exposed

## Domain Cutover (Pre -> Action -> Post)

### Pre-state
- `openviking-site` domains:
  - `openviking-site.pages.dev`
  - `doloclaw.com`
  - `www.doloclaw.com`
- Workers routes for zone `doloclaw.com`: none

### Actions executed
1. Created/updated Workers script `omnimemora-control-entry`.
2. Created Workers route `doloclaw.com/* -> omnimemora-control-entry`.
3. Created Workers route `www.doloclaw.com/* -> omnimemora-control-entry`.
4. Unbound Pages custom domain `doloclaw.com` from `openviking-site`.
5. Unbound Pages custom domain `www.doloclaw.com` from `openviking-site`.

### Post-state
- Workers routes:
  - `doloclaw.com/* -> omnimemora-control-entry`
  - `www.doloclaw.com/* -> omnimemora-control-entry`
- `openviking-site` domains:
  - only `openviking-site.pages.dev`
- Conclusion:
  - official domains no longer carried by legacy project
  - official entry serving moved to replacement control-entry project

## Continuity Verification
- `https://doloclaw.com` -> HTTP `200` (served by `omnimemora-control-entry`) ✅
- `https://www.doloclaw.com` -> HTTP `200` (served by `omnimemora-control-entry`) ✅
- Zone `doloclaw.com` remains active ✅

## Legacy Project Final State
- `openviking-site` status: **retired from official domain carrying role**
- Physical deletion: not executed in this batch (risk-minimized continuity strategy)
- Rationale:
  - running reality no longer depends on `openviking-site` for formal domains
  - project can be removed in a minimal follow-up retire-cleanup batch if desired

## Railway / Non-Regression Verification
- Railway still has no `api.doloclaw.com` custom domain ✅
- Railway active env still has no `VIKING_URL` / `VIKING_API_KEY` ✅
- Local runtime unchanged:
  - `8765/health` healthy ✅
  - `18011/health` healthy ✅
  - `5173` reachable (`200`) ✅

## Closeout Assessment
- Batch 6 result: **已收口 ✓（replacement control-entry established + official domains rebounded）**
- Remaining optional cleanup:
  - physical delete/disable of `openviking-site` (no longer a running-reality dependency)
