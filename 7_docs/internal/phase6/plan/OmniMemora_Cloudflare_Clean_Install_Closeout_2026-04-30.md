# OmniMemora Cloudflare Clean Install Closeout (2026-04-30)

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
