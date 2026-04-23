# OmniMemora Cloud Reset Closeout (2026-04-23)

## Closeout Decision
- Cloud Reset mainline is **closed**.
- `Batch 6.1` is **optional cleanup only**, not a mainline gate.

## Mainline Objectives and Completion

### Objective: remove legacy cloud-memory-era carrying surfaces
- Completed:
  - Repo-side legacy cloud pollution removed from active code/docs.
  - Active architecture/docs converged to current split.

### Objective: fix cloud split and align running reality
- Completed target split:
  - Cloudflare = control entry
  - Railway = candidate-state / async carrier
  - Local = execution truth

### Objective: remove legacy ingress semantics
- Completed:
  - Railway custom domain `api.doloclaw.com` removed.
  - Railway active `VIKING_URL` and `VIKING_API_KEY` removed.

### Objective: move official domains off legacy project
- Completed:
  - `doloclaw.com` and `www.doloclaw.com` rebound to replacement control-entry project `omnimemora-control-entry`.
  - `openviking-site` no longer carries official domains.

## Batch Completion Map
- Batch 1: cloud boundary/spec reset and active-surface cleanup baseline established.
- Batch 3: live cloud inventory completed.
- Batch 4: cutover prep completed.
- Batch 5: Railway rationalization executed (legacy ingress artifacts removed).
- Batch 6: replacement control-entry established and official domain rebind completed.

## Reality Conclusions

### Repo reality
- Active docs/contracts no longer treat OpenViking naming/paths as current product truth.

### Cloud running reality
- Official entry domains are served by `omnimemora-control-entry`.
- Railway no longer exposes removed legacy ingress surfaces (`api.doloclaw.com`, `VIKING_*`).
  - Platform verification: Railway production service instance no longer lists `api.doloclaw.com` under `customDomains`; only `omnimemora-adapter-production.up.railway.app` remains as a service domain.
  - Live verification: `https://api.doloclaw.com` no longer reaches Railway edge/fallback. Current public response is Cloudflare `530`, which reflects hostname retirement at the Cloudflare boundary rather than a live Railway ingress path.
- `openviking-site` is no longer an official carrying surface.

### Local running reality
- `18011` / `8765` / `5173` remained unchanged across cloud reset execution.

## Final Architecture Boundary
- Cloudflare control entry: established.
- Railway old ingress role: exited.
- Local execution truth: preserved.

## Legacy Project Statement
- `openviking-site` has exited official domain carrying role.
- Physical delete/disable of `openviking-site` is **not required** for Cloud Reset mainline completion.
- If desired, it can be executed as `optional cleanup` (`Batch 6.1`) without reopening mainline gate.

## Optional Cleanup Only
- Optional item:
  - physical disable/delete of `openviking-site`
- Preconditions:
  - continuity for `doloclaw.com` and `www.doloclaw.com` remains verified on `omnimemora-control-entry`
- Classification:
  - asset hygiene only, not architecture/running-reality blocker

## Final Status
- **Cloud Reset mainline: 已收口 ✓**
