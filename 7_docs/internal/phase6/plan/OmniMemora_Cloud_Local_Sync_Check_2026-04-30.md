# OmniMemora Cloud-Local Sync Check (2026-04-30)

## Scope

- Objective: check and align cloud-vs-local product reality for OmniMemora.
- Date: 2026-04-30
- Boundary: this record separates `repo reality`, `running reality`, and `cloud reality`.
- Release posture: proprietary controlled-beta/product release; not an open-source release claim.
- Project boundary: this record is only for OmniMemora under `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora`.

## Startup Compliance

- Active phase docs loaded from `7_docs/internal/phase6/plan/README.md`.
- Working-principles/SOP loaded from `docs/phase6/PROMOTION_USAGE_GOVERNANCE.md`.
- Product entry validation stays on `http://127.0.0.1:18011`.

## Repo Reality

- Branch at execution start: `master`
- HEAD: `2f91372` (`fix(sfe): stop expiring product memory by default`)
- Worktree status at execution start: clean (`0` uncommitted files)

## Release Version Check

Version surfaces checked on 2026-04-30:

| Component | Source | Observed Value | Release Decision |
|-----------|--------|----------------|------------------|
| OpenClaw plugin | `5_connectors/omni-omnimemora-plugin/package.json` | `1.0.0` | confirm or bump before release |
| Dashboard | `6_console/demo-dashboard/package.json` | `0.0.0`, `private=true` | keep private or assign product release version before packaging |
| Runtime release notes | `4_core/local-runtime/scripts/release/RELEASE_NOTES.txt` | `{{PACKAGE_VERSION}}` | package process must fill concrete version |
| Runtime license | `4_core/local-runtime/scripts/release/LICENSE.txt` | proprietary beta template | keep version synchronized with package artifact |

Release conclusion: do not publish an external product release until the target version is explicitly chosen and written into the release package metadata.

## Running Reality (Local)

Validation probes on 2026-04-30:

1. `GET http://127.0.0.1:8765/health`
- result: healthy (`status=ok`, `mode=local`)

2. `GET http://127.0.0.1:18011/health`
- result: healthy (`status=healthy`, `product_entry_port=18011`)

3. `GET http://127.0.0.1:5173/`
- result: reachable (HTML returned)

Conclusion (running reality): local stack is healthy and usable.

## Cloud Reality

Cloud probes on 2026-04-30:

1. `GET https://api.doloclaw.com/health`
- result: failed (`Could not resolve host`)

2. `GET https://omnimemora-adapter-production.up.railway.app/health`
- result: failed (`timeout after 8s`)

Conclusion (cloud reality): cloud health could not be confirmed from current network/runtime context.

## Cloudflare Platform Reality

Platform checks on 2026-04-30:

- `doloclaw.com` zone is active in Cloudflare.
- Public nameservers match Cloudflare zone nameservers: `aarav.ns.cloudflare.com`, `rafe.ns.cloudflare.com`.
- `api.doloclaw.com` has no Cloudflare DNS record.
- Worker script `omnimemora-control-entry` exists.
- Worker routes exist:
  - `doloclaw.com/* -> omnimemora-control-entry`
  - `www.doloclaw.com/* -> omnimemora-control-entry`
- Live `https://doloclaw.com/` returns HTTP 200 with `service=omnimemora-control-entry`.
- Live `https://www.doloclaw.com/` returns HTTP 301 to `https://doloclaw.com/`.

Cloudflare drift note:

- DNS still contains proxied CNAME records:
  - `doloclaw.com -> openviking-site.pages.dev`
  - `www.doloclaw.com -> openviking-site.pages.dev`
- The Worker route currently overrides the official entry path, but the old Pages target remains in DNS and should be treated as residual cloud configuration drift.

Conclusion (Cloudflare platform reality): official root entry works through the Worker route; `api.doloclaw.com` is intentionally or currently absent; residual `openviking-site` DNS targets remain.

## Railway Platform Reality

Platform checks on 2026-04-30:

- Railway CLI is logged in as the expected operator account.
- Railway project exists: `omnimemora-adapter`.
- Production service exists: `omnimemora-adapter`.
- Latest deployment status: `SUCCESS`.
- Railway service domain exists: `omnimemora-adapter-production.up.railway.app`.
- Railway custom domains list is empty; `api.doloclaw.com` is not attached to Railway.
- Production variable keys do not include `VIKING_URL` or `VIKING_API_KEY`.
- Public `GET https://omnimemora-adapter-production.up.railway.app/health` timed out after 10s.

Conclusion (Railway platform reality): legacy public custom-domain and `VIKING_*` surfaces remain removed, but the Railway default domain is not health-confirmed from this run.

## Drift Signal Snapshot

`python3 tools/verification/operational_drift_check.py`

- result: `No audit-triggering drift`
- P2 signals present:
  - PBK-001 (promotion success log without corresponding Layer 2 adoption record)
  - PBK-002 (UI promotion claimed without corresponding verification record)
  - DRA-001 (repo HEAD ahead of deployed marker)

## Sync Decision

- `repo reality` and local `running reality` are aligned enough for local validation.
- Cloudflare root entry is platform-verified and live on the Worker route.
- Railway platform inventory is verified, but Railway public health is blocked by timeout.
- `api.doloclaw.com` has no Cloudflare DNS record and does not resolve.
- Therefore, **cloud-local sync is partially verified only** (local pass, Cloudflare root pass, Railway health blocked, API subdomain absent).

## Required Next Actions

1. Re-run cloud probes from a network environment that can resolve `api.doloclaw.com`.
2. If Railway timeout persists, verify deployment health/logs in platform console before claiming sync.
3. Close PBK-001/PBK-002 Layer 2 record gaps before any new phase-level promotion declaration.
4. Decide whether residual `openviking-site.pages.dev` DNS targets should be removed or explicitly kept as non-active fallback metadata.

## Product Messaging (MVP-safe)

- OmniMemora keeps one product ingress (`18011`) with user-controlled integration (`5173`) and internal memory plane (`8765`).
- Current local product line remains stable and low-latency; cloud continuity requires a follow-up verification window.
- Public-facing wording must describe a proprietary controlled-beta/product release, not an open-source release.
