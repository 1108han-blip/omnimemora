# OmniMemora Cloud Reset Batch 5 Cutover Execution (2026-04-23)

## Scope
- Batch type: cutover execution (cloud asset rationalization only)
- In-scope:
  - Railway custom domain unbind for `api.doloclaw.com`
  - Railway legacy env var removal: `VIKING_URL`, `VIKING_API_KEY`
  - Cloudflare continuity-first verification for `doloclaw.com`
- Out-of-scope:
  - no local runtime topology changes (`18011` / `8765` / `5173`)
  - no candidate-source implementation changes
  - no aggressive Cloudflare delete while domain continuity depends on legacy Pages project

## Auth Mode Used
- Cloudflare: `CLOUDFLARE_AUTH_EMAIL` + `CLOUDFLARE_GLOBAL_API_KEY`
- Railway: `RAILWAY_TOKEN` + `RAILWAY_PROJECT_ID`

## Pre-State Snapshot

### Railway (before execution)
- Project: `omnimemora-adapter` (`08ddc7b8-8442-4570-b2b8-2b3eea9fb665`)
- Environment: `production` (`b3465248-7580-481f-8ffd-5daeeb478e3a`)
- Service: `omnimemora-adapter` (`c23a163a-f3d7-4bc5-a818-376451784a14`)
- Custom domain present: `api.doloclaw.com` (`930d7327-62f9-485e-9545-c7971c4ef45a`)
- Legacy vars present:
  - `VIKING_URL` (`64f44cdc-7ee7-425e-b347-258d1de9831b`)
  - `VIKING_API_KEY` (`19fc51f8-1460-411a-9a57-a97ff65ac7a7`)

### Cloudflare (before/continuity baseline)
- Zone `doloclaw.com` exists and active (`a0722cdf150055ca689fae73b565c42b`)
- Legacy Pages project `openviking-site` exists and still carries:
  - `doloclaw.com`
  - `www.doloclaw.com`

## Execution Actions

### Railway actions executed
1. `customDomainDelete(id="930d7327-62f9-485e-9545-c7971c4ef45a")`
   - target: `api.doloclaw.com`
   - result: HTTP `200`, mutation success
2. `variableDelete(input={projectId, environmentId, serviceId, name:"VIKING_URL"})`
   - result: HTTP `200`, mutation success
3. `variableDelete(input={projectId, environmentId, serviceId, name:"VIKING_API_KEY"})`
   - result: HTTP `200`, mutation success

### Cloudflare actions executed
- No destructive action executed.
- Continuity-first policy applied (legacy Pages retained as pending-retire because it still carries official domains).

## Post-State Verification

### Railway verification
- `api.doloclaw.com` no longer appears in Railway custom domains ✅
- `VIKING_URL` no longer appears in active Railway variables ✅
- `VIKING_API_KEY` no longer appears in active Railway variables ✅

### Cloudflare verification
- `doloclaw.com` zone still present and active ✅
- `doloclaw.com` / `www.doloclaw.com` continuity preserved ✅
- `openviking-site` status aligned to reality: **pending retire** (not deleted in this batch) ✅

### Non-regression verification (local reality)
- `8765/health` reachable and healthy ✅
- `18011/health` reachable and healthy ✅
- `5173` reachable (`HTTP 200`) ✅
- No local topology changes made in this batch ✅

## Asset Disposition Outcome

### Retired in Batch 5
- Railway custom domain `api.doloclaw.com`
- Railway env var `VIKING_URL`
- Railway env var `VIKING_API_KEY`

### Kept (continuity critical)
- Cloudflare zone `doloclaw.com`
- Domain continuity for `doloclaw.com` and `www.doloclaw.com`

### Pending retire (explicit)
- Cloudflare Pages project `openviking-site`
  - Reason: currently still carries official domain continuity
  - Condition to retire: replacement control-plane project takes over domain bindings and continuity is verified

## Remaining Inputs for Next Batch
1. Stand up or confirm replacement Cloudflare control-plane project with current naming.
2. Rebind `doloclaw.com` / `www.doloclaw.com` from `openviking-site` to replacement project.
3. After continuity validation, retire `openviking-site`.
4. Continue Railway scope reduction to candidate-state/async-only operational profile (without reintroducing ingress semantics).

## Batch 5 Status
- Result: **已收口 ✓（cutover execution scoped to Railway rationalization + Cloudflare continuity hold）**
