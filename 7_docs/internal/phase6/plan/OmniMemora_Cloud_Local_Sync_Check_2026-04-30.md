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

## Drift Signal Snapshot

`python3 tools/verification/operational_drift_check.py`

- result: `No audit-triggering drift`
- P2 signals present:
  - PBK-001 (promotion success log without corresponding Layer 2 adoption record)
  - PBK-002 (UI promotion claimed without corresponding verification record)
  - DRA-001 (repo HEAD ahead of deployed marker)

## Sync Decision

- `repo reality` and local `running reality` are aligned enough for local validation.
- `cloud reality` is not verifiable in this run due to DNS/timeout failures.
- Therefore, **cloud-local sync is partially verified only** (local pass, cloud blocked).

## Required Next Actions

1. Re-run cloud probes from a network environment that can resolve `api.doloclaw.com`.
2. If Railway timeout persists, verify deployment health/logs in platform console before claiming sync.
3. Close PBK-001/PBK-002 Layer 2 record gaps before any new phase-level promotion declaration.

## Product Messaging (MVP-safe)

- OmniMemora keeps one product ingress (`18011`) with user-controlled integration (`5173`) and internal memory plane (`8765`).
- Current local product line remains stable and low-latency; cloud continuity requires a follow-up verification window.
- Public-facing wording must describe a proprietary controlled-beta/product release, not an open-source release.
