# OmniMemora Cloud Reset Batch 1 Spec

Date: 2026-04-22
Status: Active (roadmap外治理增强线)

## 1. Cloud Role Split

### Cloudflare (`doloclaw.com`)

Responsibilities:

- sole external domain entry
- control-plane API/auth/tenant/billing/policy access
- recommendation candidate fetch entry

Non-responsibilities:

- primary memory plane
- primary compile engine
- `/memory/*` primary write/read/delete product path

### Railway

Responsibilities:

- recommendation candidate snapshots/state storage
- lightweight async aggregation jobs
- low-cost persistence for candidate pipeline support

Non-responsibilities:

- primary `/memory/*`
- main compile path

### Local (`18011` + `8765` + `5173`)

Responsibilities:

- execution truth remains local-first
- `18011` is product ingress when routing is enabled
- `8765` is internal memory plane
- promotion determines active policy effect
- cloud candidate is optional and cannot override local active directly

## 2. Candidate Source Contract (Batch 1 Skeleton)

- Cloudflare returns `candidate pointer` (`candidate_id`, `policy_version`, `snapshot_id`)
- Railway returns snapshot payload for `snapshot_id`
- local loader priority:
  1. local active (authoritative)
  2. local candidate (if present)
  3. cloud candidate (optional fallback candidate only)

## 3. Deleted Assets in Batch 1

- `6_console/ui-prototype/`
- `4_core/adapter-raw/archive/`
- `云端产品现状CC报告(临时）/CLOUD_CURRENT_STATE.md`

## 4. Naming Cleanup Scope

Batch 1 removed legacy naming from active entry surfaces:

- active ADR cloud boundary docs
- root/customer-facing README surfaces
- current connector/plugin exposed defaults and docs

Compatibility internals may remain temporarily in deep legacy branches but are out of active entry scope.

## 5. Deferred Legacy Purge (Next Batch)

Deferred to `legacy compatibility purge`:

- deep migration scripts and archived historical artifacts
- internal compatibility-only branches not used as active entry surfaces
- full cloud candidate management workflow beyond skeleton contract

## 6. Non-Regression Target

Batch 1 must not alter running reality baseline:

- `18011 / 8765 / 5173` behavior remains unchanged by cloud reset cleanup
