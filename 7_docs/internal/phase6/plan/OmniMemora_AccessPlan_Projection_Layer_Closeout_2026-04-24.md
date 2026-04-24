# OmniMemora AccessPlan Projection Layer Closeout (2026-04-24)

## Batch Scope

- Batch name: `AccessPlan Projection Pre-Promotion Hardening`
- Decision: **Passed**
- Scope boundary: `AccessPlan projection layer` only

This batch is limited to projection/read-model traceability and compatibility hardening.
It is not a runtime multi-domain read/write enforcement batch.

## Canonical Conclusion

`Identity Spine + AccessPlan projection is available in meter/request_evidence and verified in running reality; runtime multi-domain read/write enforcement remains a later batch.`

## What Was Verified

1. `18011` ingress/application meter paths now persist `identity + access_plan` projection fields.
2. Legacy `tenant/user` aggregation semantics remain intact:
   - legacy aggregate field stays in `tenant` / `user`
   - new identity field is carried by `tenant_id`
3. `request_evidence` keeps stable compatibility:
   - old meter: stable projection fallback is returned
   - new meter: top-level `access_plan` is non-empty
4. `adapter+ui` promotion passed with adapter restart-truth changed.
5. OpenClaw live request under running reality can be traced back with `identity/access_plan`.
6. OpenClaw control truth ultimately aligned to `real_request_observed`.
7. Codex remained excluded from live gate (protected/deferred boundary preserved).

## Running Reality Promotion Record

- promotion command: `./tools/promotion/promotion.sh adapter+ui`
- promotion log: `tools/verification/logs/promotion_20260424_100321.log`
- repo revision at promotion: `5e466f9`
- result: `running_reality_promoted`

Adapter restart-truth evidence from promotion log:

- pre fingerprint:
  - `pid=53983`
  - `started_at=2026-04-23T17:18:44.473230Z`
  - `code_source=/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`
- post fingerprint:
  - `pid=86352`
  - `started_at=2026-04-24T02:03:23.526666Z`
  - `code_source=/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`
- restart truth: `changed`

## OpenClaw Live Revalidation Record

Validation target: OpenClaw only (non-Codex scope)

### Request A (first observation)

- request path: `POST /llm/v1/messages`
- request_id: `62e7fe0eead9`
- request_evidence:
  - `request.identity.family_id=openclaw`
  - `request.identity.instance_id=openclaw`
  - `request.identity.tenant_id=tenant-openclaw-live-1`
  - `access_plan.read_domains[0].scope_type=instance_private`
  - `workspace_shared` domain present (workspace header provided)
- observation at first control check:
  - OpenClaw card `traffic_truth=internal_only`
- note:
  - this request was `task_non_value`, baseline token estimate = `15` (tiny request window),
    so it did not satisfy observed-request elevation threshold.

### Request B (final alignment)

- request path: `POST /llm/v1/messages`
- request_id: `02c7e8879115`
- request_evidence:
  - `request.identity.family_id=openclaw`
  - `request.identity.instance_id=openclaw`
  - `request.identity.tenant_id=tenant-openclaw-live-1`
  - `access_plan.read_domains[0].scope_type=instance_private`
  - `workspace_shared` domain present (workspace header provided)
- control truth after request B:
  - `traffic_truth=real_request_observed`
  - `integration_truth=attached_with_backup`
  - `last_request_at=2026-04-24T02:05:04.405966Z`

Final OpenClaw judgement: pass (running reality aligned)

## Interface/Contract Notes

- `tenant_id` is the new identity-spine tenant field.
- `tenant` remains legacy aggregate field in this batch.
- `request_evidence.access_plan` is a projection truth contract, not proof that runtime domain enforcement is already active.

## Deferred / Next Batch Boundary

Deferred to next batch:

- `AccessPlan -> runtime memory domain enforcement`
  - actual runtime multi-domain read/write execution semantics
  - private/workspace_shared/shared_read_only enforcement path

Out of current gate:

- Codex live validation (kept protected/deferred)
