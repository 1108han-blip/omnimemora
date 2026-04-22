# OmniMemora Cloud Reset Batch 4 Cutover Prep (2026-04-23)

## Scope
- Batch type: prep-only, read-only cloud verification + disposition/cutover planning
- Explicit non-goals:
  - no Cloudflare/Railway resource create/update/delete
  - no local runtime topology changes (`18011` / `8765` / `5173`)
  - no candidate-source implementation expansion

## D1 Inventory Backfill (Blocking Check)

### Auth visibility check
- `CLOUDFLARE_AUTH_EMAIL`: present (launchctl)
- `CLOUDFLARE_GLOBAL_API_KEY`: present (launchctl)
- `CLOUDFLARE_API_TOKEN`: present (launchctl)

### Read-only D1 probe
- Account listing succeeded via global-key auth.
- D1 list endpoint probes:
  - `GET /accounts/<account_id>/d1/database` -> `200` (success, 1 database)
  - `GET /accounts/<account_id>/d1/database?page=1&per_page=50` -> `200` (success, 1 database)
  - `GET /accounts/<account_id>/d1/database/<db_id>` -> `200` (detail success)
- Observed D1 asset:
  - `name`: `omnimemora-leads`
  - `id`: `e7481f9d-a1f2-482c-90e6-d56949bd42e2`
  - `known binding`: no direct coupling to legacy Pages project detected via inventory endpoints

### D1 gap status
- **Closed** in Batch 4.1.
- Resolution reason: preferred auth mode visibility restored in system-level launchd env.
- Classification update: previous blocker was auth visibility gap, not product-path blocker.

## Final Disposition List (Cutover-Oriented)

### Keep
| asset | current role | target role | cutover precondition | retire owner | blocking risk |
|---|---|---|---|---|---|
| `doloclaw.com` zone | public DNS zone | Cloudflare single official control entry domain | none; keep continuity during cutover | n/a | low |
| `doloclaw.com` binding | points to legacy Pages project | keep domain as control-entry hostname | replacement control-plane project must be ready before rebinding | cloud-ops | medium (traffic switch timing) |
| `www.doloclaw.com` binding | alias to legacy Pages project | optional alias under control-entry project | same as above | cloud-ops | medium |

### Retire
| asset | current role | target role | cutover precondition | retire owner | blocking risk |
|---|---|---|---|---|---|
| Cloudflare Pages `openviking-site` | legacy public entry project | replaced by current-naming control-plane project | new control-plane entry deployed and domain cutover validated | cloud-ops | high (domain continuity if removed too early) |
| Railway custom domain `api.doloclaw.com` | legacy ingress endpoint | no Railway public ingress in target split | Cloudflare control entry fully takes over external API entry | cloud-ops | high (client traffic break if premature) |
| Railway variable `VIKING_URL` | legacy backend endpoint config | removed from active cloud env | Railway service role narrowed to candidate-state/async-only plan | platform-ops | medium |
| Railway variable `VIKING_API_KEY` | legacy backend credential surface | removed from active cloud env | same as above; replacement var surface finalized | platform-ops | medium |

### Migrate Reference Only
| asset | current role | target role | cutover precondition | retire owner | blocking risk |
|---|---|---|---|---|---|
| Railway project `omnimemora-adapter` | legacy adapter-runtime host | candidate-state/async carrier only | scope-reduction plan approved (no ingress semantics) | platform-ops | medium |
| Railway `production` env | mixed runtime config surface | candidate-state/async-only env surface | variable/domain cleanup plan executed | platform-ops | medium |
| Railway service `omnimemora-adapter` | active runtime service | reduced async/candidate worker role or archived reference | decide keep-vs-rebuild architecture in Batch 5 | platform-ops | medium |
| Railway service domain `omnimemora-adapter-production.up.railway.app` | public Railway domain | internal/reference-only or retired | public ingress already removed from Railway | platform-ops | low-medium |
| Cloudflare R2 `doloclaw-assets-v2` | generic object storage | optional support storage (non-memory-plane) | ownership + lifecycle policy defined | cloud-ops | low |
| Cloudflare R2 `seancorliss` | generic object storage | reference-only unless assigned to control-plane support use | explicit ownership declaration | cloud-ops | low |
| Railway variables `OMNIMEMORA_*` set | mixed operational config | curated candidate-state/async config baseline | variable-by-variable allowlist review | platform-ops | medium |
| Railway variable `LOG_LEVEL` | generic runtime tuning | keep only if service retained for async role | async role decision finalized | platform-ops | low |

## Cloudflare / Railway Target Landing (Fixed in Batch 4)

### Cloudflare
- `doloclaw.com` remains the only official external entry domain.
- Legacy Pages project is a retirement target.
- Future control-plane project must use current naming.
- D1 is control-plane supporting store only; it is not a memory plane.

### Railway
- Railway target role is candidate-state / lightweight async only.
- Railway must not remain public ingress for `api.doloclaw.com`.
- Legacy `VIKING_*` config must be removed before/at cutover.

### Local
- Local remains execution truth.
- Batch 4 makes no changes to runtime/routing/compile topology.

## Cutover Preconditions

### Cloudflare preconditions
1. D1 inventory completed (`omnimemora-leads`) and recorded as control-plane supporting-store candidate.
2. Replacement control-plane project defined with current naming.
3. Domain cutover runbook prepared (`doloclaw.com` / `www.doloclaw.com`).
4. Legacy Pages decommission sequence approved.

### Railway preconditions
1. Confirm no required product ingress remains on Railway service/domain.
2. Remove legacy `VIKING_*` variables from active environment at execution time.
3. Decide whether `omnimemora-adapter` is reduced-in-place or archived/replaced.
4. Restrict Railway surface to candidate-state/async responsibilities only.

## Next Batch Inputs (Implementation Batch)
- Batch 5 should execute real asset rationalization and cutover in this order:
1. Provision/verify replacement Cloudflare control-plane project (current naming).
2. Switch domain bindings away from `openviking-site`.
3. Remove Railway custom domain `api.doloclaw.com`.
4. Remove Railway `VIKING_URL` and `VIKING_API_KEY`.
5. Apply Railway scope reduction to candidate-state/async-only.
6. Retire legacy Pages project after traffic cut confirmation.

## Batch 4 Status
- Result: **已收口 ✓（prep complete）**
- Gate impact:
  - cutover prep artifacts are ready,
  - inventory blocker is resolved and status no longer depends on D1 auth visibility.
