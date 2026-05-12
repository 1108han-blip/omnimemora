# OmniMemora Cloudflare Clean Install Closeout (2026-04-30)

> **2026-05-10 supersession**: 本记录中的 `5173` 可达性为历史本地非干扰检查。当前产品口径以 OmniMemora Desktop app 为控制/展示面，`5173` 为 legacy/dev。

## Scope

- Project: OmniMemora only.
- Platform: Cloudflare `doloclaw.com` zone.
- Objective: remove conflicting legacy `openviking-site` project and reinstall current OmniMemora control-entry behavior.
- Explicitly out of scope: unrelated Cloudflare projects, `prompt.doloclaw.com`, R2 assets, email routing, Railway deployment changes, local product runtime changes.

## Version And Release Posture

- Worker install package version used: `1.0.0-beta.1`.
- Support email used: `support@doloclaw.com`.
- Release posture: proprietary controlled beta; not an open-source product release.

## Actions Executed

1. Reinstalled Cloudflare Worker `omnimemora-control-entry` from `6_console/control-entry/worker.js`.
2. Added current product control-entry endpoints:
   - `/`
   - `/health`
   - `/download`
   - `/api/control/recommendation/candidates/latest`
   - `/api/policy/candidates/latest`
3. Preserved local-first policy semantics:
   - candidate pointer endpoint returns `status=not_configured`
   - candidate payload is `null`
   - `candidate_auto_promote=false`
   - `cloud_compile=false`
4. Rebound `doloclaw.com` and `www.doloclaw.com` DNS away from `openviking-site.pages.dev`.
5. Set both official OmniMemora DNS records to proxied Worker-route placeholder A records:
   - `doloclaw.com -> 192.0.2.1`
   - `www.doloclaw.com -> 192.0.2.1`
6. Deleted Cloudflare Pages project `openviking-site`.

## Cloudflare Reality After Execution

- Pages projects list: empty.
- `openviking-site` no longer exists.
- Worker routes remain:
  - `doloclaw.com/* -> omnimemora-control-entry`
  - `www.doloclaw.com/* -> omnimemora-control-entry`
- `prompt.doloclaw.com` remains unchanged and still points to `76.76.21.21`.
- `api.doloclaw.com` remains absent; it is not reintroduced.

## Live Verification

| Probe | Result |
|-------|--------|
| `GET https://doloclaw.com/` | HTTP 200, `service=omnimemora-control-entry` |
| `GET https://doloclaw.com/health` | HTTP 200, `status=healthy` |
| `GET https://doloclaw.com/api/control/recommendation/candidates/latest` | HTTP 200, `schema_version=omnimemora-cloud-candidate-pointer-v1`, `status=not_configured` |
| `GET https://doloclaw.com/missing` | HTTP 404 |

## Download Availability

Release `1.0.0-beta.1` artifacts are publicly reachable from R2 through `assets.doloclaw.com`:

| Artifact | Result |
|----------|--------|
| `omnimemora-darwin-arm64.zip` | HTTP 200 |
| `omnimemora-darwin-amd64.zip` | HTTP 200 |
| `omnimemora-windows-amd64.zip` | HTTP 200 |
| `SHA256SUMS.txt` | HTTP 200 |
| `RELEASE_INDEX.txt` | HTTP 200 |

R2 object listing confirms the same five objects under `omnimemora/beta/1.0.0-beta.1/`.

The public download page now links through Worker-tracked redirect paths:

| Public path | Redirect target |
|-------------|-----------------|
| `/download/file/darwin-arm64` | `omnimemora-darwin-arm64.zip` |
| `/download/file/darwin-amd64` | `omnimemora-darwin-amd64.zip` |
| `/download/file/windows-amd64` | `omnimemora-windows-amd64.zip` |
| `/download/file/sha256sums` | `SHA256SUMS.txt` |

These paths preserve the simple R2 file layout while giving Cloudflare HTTP analytics a stable project-owned path to count.

## Feedback Email Fix

Cloudflare Email Routing status:

- domain routing status: `ready`
- target address `1108.han@gmail.com`: verified
- route created: `support@doloclaw.com -> 1108.han@gmail.com`
- disabled default drop-all rule remains disabled

This fixes the prior support-email gap where the UI and download page pointed to `support@doloclaw.com`, but Cloudflare had no enabled forwarding rule for that address.

## Current Usage Visibility

Current measurable surfaces:

- GitHub traffic API reports repository views and clones.
- Cloudflare HTTP analytics is available for the last 24h on the current plan.
- Download attempts can now be counted by Cloudflare `clientRequestPath` for `/download/file/...`.
- R2 object listing confirms artifact existence, but does not provide historical per-object download user counts.

Observed on 2026-04-30:

- GitHub repository views for the reported 14-day window: `0` total, `0` unique.
- GitHub repository clones for the reported 14-day window: `300` total, `64` unique.
- Cloudflare last-24h analytics showed bot/scanner traffic against `doloclaw.com` and `assets.doloclaw.com`.
- Exact historical direct-R2 product download counts before the tracked redirect change cannot be reconstructed reliably.
- Download tracking is active from the Worker redirect deployment onward; analytics may lag before new path rows appear.

Download count query shape:

- source: Cloudflare GraphQL HTTP analytics
- filter: `clientRequestHTTPHost == "doloclaw.com"`
- paths: `/download/file/darwin-arm64`, `/download/file/darwin-amd64`, `/download/file/windows-amd64`, `/download/file/sha256sums`
- retention: current-plan analytics window only unless a later paid log-retention path is enabled
- privacy: no personal user database is created by this change

## Railway Non-Interference

- Railway project `omnimemora-adapter` remains present.
- Production service domain remains `omnimemora-adapter-production.up.railway.app`.
- Railway custom domains remain empty.
- No Railway deploy/restart/config mutation was executed in this batch.

## Local Non-Interference

- `GET http://127.0.0.1:18011/health` remains healthy.
- `GET http://127.0.0.1:5173/` remains reachable.
- No local promotion was run.

## Closeout

Cloudflare legacy conflict is removed. Current OmniMemora control entry is reinstalled and verified. Future strategy update capacity is reserved through a candidate pointer endpoint, but no cloud candidate is active and no cloud path can auto-promote or override local active policy.
