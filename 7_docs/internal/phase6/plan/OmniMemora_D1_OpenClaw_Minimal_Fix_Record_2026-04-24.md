# OmniMemora D1 OpenClaw Minimal Fix Record (2026-04-24)

## Scope
- Batch: OpenClaw D1 minimal fix
- Fixed chain only: control read-model observed-request truth
- Excluded: Codex live validation, ingress behavior changes, attach-truth changes, frontend reinterpretation

## Code Changes
- `5_connectors/adapter/application/status_read_model.py`
  - Added shared observed-meter helper: `_collect_observed_family_meters()`
  - `derive_traffic_truth()` now uses the shared observed helper
  - `compute_family_24h_metrics()` now aligns observed semantics:
    - `observed_requests_24h` from observed helper
    - `last_request_at` prioritizes observed meter timestamp, then compile fallback
  - Added fallback reads for observed collection:
    - persisted meter index snapshot
    - recent proxy request ids resolved via meter getter
- `5_connectors/adapter/__tests__/test_status_read_model.py`
  - Added OpenClaw-focused regression tests (observed non-value, tiny ping, last_request_at priority, persisted fallback)
- `5_connectors/adapter/agent_control_api.py`
  - Unified `status_read_model` import path with diagnostics surface import style to avoid split-module assembly risk

## Repo Checks
- `python3 -m pytest -q 5_connectors/adapter/__tests__/test_status_read_model.py`
  - result: `21 passed`
- `python3 -m py_compile`
  - result: pass

## Running Reality
Promotions executed during this batch:
- `tools/verification/logs/promotion_20260424_010632.log`
- `tools/verification/logs/promotion_20260424_010751.log`
- `tools/verification/logs/promotion_20260424_010954.log`

All promotion runs reported:
- `promotion_target=adapter+ui`
- `final_status=running_reality_promoted`
- health: `8765/18011/5173` healthy

## OpenClaw-only Revalidation
### Revalidation request ids (real gateway requests)
- `b0897daa5e78`
- `e231f55d6456`
- `1cb59cd753c4`

For each request id:
- path observed from proxy events: `/llm/v1/messages`
- `GET /debug/request_evidence?request_id=...` => found
- `request.agent_family=openclaw`

### Control card check (`GET /agents/control`)
Observed after each revalidation:
- `family_id=openclaw`
- `integration_truth=attached_with_backup` (no attach-truth regression)
- `traffic_truth=no_recent_evidence`
- `last_request_at=null`

## Decision
- Minimal fix batch executed and verified at repo/running layers.
- OpenClaw D1 acceptance gap remains unresolved:
  - evidence side confirms real request and request_id lookup
  - control side still reports `no_recent_evidence` and null `last_request_at`

## Residual Conflict (No Scope Expansion)
- Current residual conflict is unchanged and isolated:
  - control read-model still not reflecting OpenClaw observed requests in running reality.
- This record intentionally does not expand into new architecture lines.
