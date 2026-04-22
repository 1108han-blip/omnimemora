# OmniMemora Cloud Reset Batch 3 Inventory (2026-04-23)

## Scope
- Batch type: inventory-only (no create/update/delete on cloud resources)
- Goal: align cloud running reality with post-Batch1/Batch2 repo boundary
- Boundary baseline: Cloudflare=control entry, Railway=candidate state/async, Local=execution truth

## Inventory Date
- Date: 2026-04-23
- Operator context: Codex local session

## Auth Mode Used
- Cloudflare preferred mode required by plan: `CLOUDFLARE_AUTH_EMAIL` + `CLOUDFLARE_GLOBAL_API_KEY`
- Cloudflare actual mode used (initial run): `CLOUDFLARE_API_TOKEN` fallback
- Cloudflare actual mode used (Batch 4.1 closure): `CLOUDFLARE_AUTH_EMAIL` + `CLOUDFLARE_GLOBAL_API_KEY`
- Reason: initial run lacked global-key visibility; Batch 4.1 restored system-level launchd visibility for preferred auth mode
- Railway mode used: `RAILWAY_TOKEN` + `RAILWAY_PROJECT_ID`
- Railway API endpoint selection:
- `https://backboard.railway.app/graphql/v2` `me` -> status `403`
- `https://backboard.railway.app/graphql/v2` `project` -> status `403`
- `https://backboard.railway.com/graphql/v2` `me` -> status `403`
- `https://backboard.railway.com/graphql/v2` `project` -> status `403`
- `https://api.railway.app/graphql/v2` `me` -> status `200`
- `https://api.railway.app/graphql/v2` `project` -> status `200`
- Railway fallback decision: dashboard-assisted fallback not required (API succeeded at `api.railway.app/graphql/v2`)

## Reality Separation
- Repo reality:
  - Batch1+Batch2 already removed active openviking backend path and moved legacy docs/migrations to archive.
  - Cloud split in repo is fixed: local-first, cloud optional candidate source.
- Cloud/running reality:
  - Cloudflare domain remains active and bound to a legacy-named Pages project.
  - Railway project still exposes legacy ingress/domain/env naming surfaces.
- Target architecture:
  - Cloudflare only as control entry.
  - Railway only as candidate state/async carrier.
  - Local remains execution truth (`8765` / `18011` / `5173`).

## Cloudflare Asset Table
| resource_type | name | id | status | current_role | boundary_fit | disposition |
| --- | --- | --- | --- | --- | --- | --- |
| zone | doloclaw.com | a0722cdf150055ca689fae73b565c42b | active | control_entry | fit | keep |
| pages_project | openviking-site | 46dbc321-53bc-474a-b3c7-2eab274517dc | active | control_entry | conflict | retire |
| domain_binding | doloclaw.com | openviking-site:doloclaw.com | active | control_entry | fit | keep |
| domain_binding | www.doloclaw.com | openviking-site:www.doloclaw.com | active | control_entry | fit | keep |
| d1_database | omnimemora-leads | e7481f9d-a1f2-482c-90e6-d56949bd42e2 | active | control_plane_supporting_store | fit | keep |
| r2_bucket | doloclaw-assets-v2 | doloclaw-assets-v2 | active | candidate_state_or_async_storage | needs_mapping | migrate_reference_only |
| r2_bucket | seancorliss | seancorliss | active | candidate_state_or_async_storage | needs_mapping | migrate_reference_only |

### Cloudflare Notes
- Endpoint failures observed:
  - `/user` -> `403` (`Valid user-level authentication not found`)
  - `/user/tokens/verify` -> `401` (`Invalid API Token`)
  - `/accounts/<id>/d1/database` -> `401` (`Authentication error`)
- This means D1 inventory is currently permission-blocked under available token mode.
- Legacy naming hit detected: Pages project `openviking-site`.
- Batch 4 follow-up (2026-04-23): D1 endpoint re-probe still returns `401`; blocker remains auth-scope related.
- Batch 4.1 closure (2026-04-23):
  - `launchctl` now exposes `CLOUDFLARE_AUTH_EMAIL` and `CLOUDFLARE_GLOBAL_API_KEY`
  - D1 list endpoint and per-database detail endpoint both returned `200`
  - Blocker root cause confirmed as auth visibility gap, not product boundary conflict

## Railway Asset Table
| resource_type | name | id | status | current_role | boundary_fit | disposition |
| --- | --- | --- | --- | --- | --- | --- |
| railway_project | omnimemora-adapter | 08ddc7b8-8442-4570-b2b8-2b3eea9fb665 | active | legacy_adapter_host | conflict | migrate_reference_only |
| railway_environment | production | b3465248-7580-481f-8ffd-5daeeb478e3a | active | runtime_env | conflict | migrate_reference_only |
| railway_variable | OMNIMEMORA_ADMIN_API_TOKEN | 0c50109a-12c9-4a7f-8316-6d92dcc7a98b | active | service_config | unknown | migrate_reference_only |
| railway_variable | OMNIMEMORA_REGISTRY_SYNC_ENABLED | 0c95de9d-ab4f-4863-ba4a-becb31f694b5 | active | service_config | unknown | migrate_reference_only |
| railway_variable | VIKING_API_KEY | 19fc51f8-1460-411a-9a57-a97ff65ac7a7 | active | service_config | conflict | retire |
| railway_variable | OMNIMEMORA_REGISTRY_SYNC_URL | 1b11b6f4-f532-42ae-ac8c-aa722b084361 | active | service_config | unknown | migrate_reference_only |
| railway_variable | OMNIMEMORA_REGISTRY_SYNC_TOKEN | 336975c0-cb13-4e7f-ae63-82b8bcea087a | active | service_config | unknown | migrate_reference_only |
| railway_variable | LOG_LEVEL | 4c8a8763-c6b5-4f14-be21-00b8c4b32756 | active | service_config | unknown | migrate_reference_only |
| railway_variable | VIKING_URL | 64f44cdc-7ee7-425e-b347-258d1de9831b | active | service_config | conflict | retire |
| railway_variable | OMNIMEMORA_TRIAL_QUOTA_TOKENS | 858c15ed-d747-4806-9c91-92a8e3541ed8 | active | service_config | unknown | migrate_reference_only |
| railway_variable | OMNIMEMORA_INTERNAL_API_TOKEN | ddfc5705-4300-4ac0-ab45-d0741af40243 | active | service_config | unknown | migrate_reference_only |
| railway_variable | OMNIMEMORA_TRIAL_DAYS | f3bcbfef-4899-471f-9d97-4c260f6ce17c | active | service_config | unknown | migrate_reference_only |
| railway_service_instance | omnimemora-adapter | 19a64b54-7c3d-48e3-8a75-61c4f0a4185e | SUCCESS | adapter_runtime | conflict | migrate_reference_only |
| railway_domain | omnimemora-adapter-production.up.railway.app | 7a0b616e-46d3-49a2-94bb-91086a2d1d3b | active | railway_service_domain | conflict | migrate_reference_only |
| railway_domain | api.doloclaw.com | 930d7327-62f9-485e-9545-c7971c4ef45a | active | custom_domain_binding | conflict | retire |
| railway_service | omnimemora-adapter | c23a163a-f3d7-4bc5-a818-376451784a14 | active | adapter_service | conflict | migrate_reference_only |

### Railway Notes
- Project detected: `omnimemora-adapter`
- Service domain detected: `omnimemora-adapter-production.up.railway.app`
- Custom domain detected: `api.doloclaw.com` (legacy ingress semantic under new split)
- Legacy variable names detected: `VIKING_URL`, `VIKING_API_KEY`

## Carrying-Relation Matrix
| surface | current_reality | target_role | conflict | required_action |
| --- | --- | --- | --- | --- |
| doloclaw.com (Cloudflare zone + Pages binding) | Bound to Pages project `openviking-site` and www alias | Cloudflare control entry | Project naming is legacy (`openviking-site`) | Retire legacy project naming/cut over to current-naming control project; keep zone/domain entry on Cloudflare |
| Railway project `omnimemora-adapter` | Runs adapter service with custom domain `api.doloclaw.com` | Railway candidate state / async only | Current workload is legacy API ingress-style runtime, outside target split | Migrate to candidate-state/async scope only, then retire ingress semantics |
| Railway env vars | Contains `VIKING_URL` and `VIKING_API_KEY` plus OMNIMEMORA vars | No legacy VIKING naming in active path | Legacy naming still active in running cloud env | Retire VIKING_* vars in cutover batch and replace with current naming only if service remains |
| Local runtime (`8765`)+ingress (`18011`)+UI (`5173`) | Repo boundary fixed local-first with cloud-optional candidate skeleton | Execution truth stays local | No conflict in this inventory batch | Keep unchanged in Batch 4 rationalization |

## Decision Lists

### keep
- `zone` `doloclaw.com`
- `domain_binding` `doloclaw.com`
- `domain_binding` `www.doloclaw.com`
- `d1_database` `omnimemora-leads`

### migrate_reference_only
- `r2_bucket` `doloclaw-assets-v2`
- `r2_bucket` `seancorliss`
- `railway_project` `omnimemora-adapter`
- `railway_environment` `production`
- `railway_variable` `OMNIMEMORA_ADMIN_API_TOKEN`
- `railway_variable` `OMNIMEMORA_REGISTRY_SYNC_ENABLED`
- `railway_variable` `OMNIMEMORA_REGISTRY_SYNC_URL`
- `railway_variable` `OMNIMEMORA_REGISTRY_SYNC_TOKEN`
- `railway_variable` `LOG_LEVEL`
- `railway_variable` `OMNIMEMORA_TRIAL_QUOTA_TOKENS`
- `railway_variable` `OMNIMEMORA_INTERNAL_API_TOKEN`
- `railway_variable` `OMNIMEMORA_TRIAL_DAYS`
- `railway_service_instance` `omnimemora-adapter`
- `railway_domain` `omnimemora-adapter-production.up.railway.app`
- `railway_service` `omnimemora-adapter`

### retire
- `pages_project` `openviking-site`
- `railway_variable` `VIKING_API_KEY`
- `railway_variable` `VIKING_URL`
- `railway_domain` `api.doloclaw.com`

## Boundary-Fit Judgment
- Cloudflare:
  - `doloclaw.com` zone/domain entry fits control-entry target and should be kept.
  - Legacy-named Pages project conflicts with current product naming and should be retired/replaced in cutover.
  - D1 visibility is now complete under preferred global-key auth mode; D1 can be evaluated as control-plane supporting store.
- Railway:
  - Current project/service operate as legacy ingress-style runtime surface, not candidate-state/async-only.
  - Legacy env/domain naming confirms boundary conflict.
  - Railway inventory itself is complete via API path.

## Next-Batch Inputs (Batch 4: Rationalization / Cutover Prep)
1. Cloudflare: prepare replacement plan for `openviking-site` while preserving `doloclaw.com` entry continuity.
2. Cloudflare: carry `omnimemora-leads` as control-plane supporting-store candidate in cutover prep records (no structural change in this batch).
3. Railway: plan cutover to remove `api.doloclaw.com` from Railway and retire `VIKING_*` vars.
4. Railway: decide keep-vs-rebuild for project `omnimemora-adapter` as candidate-state/async carrier only.
5. Local path (`8765/18011/5173`): no change in Batch 4 unless explicitly required by cutover validation.

## Batch 3 Closeout
- Result: **已收口 ✓（inventory complete）**
- Constraint check: no cloud resource created, modified, or deleted in this batch.
