# OmniMemora D1 Adapter Promotion Restart Truth Repair Record (2026-04-24)

## Scope
- Batch: Adapter Promotion Restart Truth Repair
- Fixed chain only:
  - promotion gate for adapter restart effectiveness
  - launchd restart primary path + fingerprint-based running-instance truth
- Excluded:
  - Codex live validation
  - ingress/API product contract changes
  - new frontend/type contracts

## Code Change
- File: `tools/promotion/promotion.sh`

### Implemented changes
1. Adapter restart truth gate tightened:
   - pre/post fetch of `GET /debug/runtime_fingerprint`
   - recorded fields:
     - `adapter_pre_pid`
     - `adapter_pre_started_at`
     - `adapter_post_pid`
     - `adapter_post_started_at`
     - `adapter_restart_truth`
     - `adapter_code_source`
     - `adapter_restart_method`
   - success now requires:
     - adapter API reachable
     - `code_source["5_connectors.adapter.main"]` points to `~/.omnimemora/service/current/...`
     - `started_at` changed
     - `pid` changed
2. Restart path changed:
   - primary: `launchctl kickstart -k gui/$(id -u)/com.omnimemora.adapter`
   - fallback: `stop/start`
   - fallback: direct `kill+start`
3. Failure classification:
   - unchanged/unknown restart truth => `adapter:failed:adapter_restart_not_effective`
   - code source mismatch => `adapter:failed:code_source_mismatch`
   - API unreachable => `adapter:failed:api_unreachable`

## Repo Check
- `bash -n tools/promotion/promotion.sh` => pass

## Running Reality Validation
### Fingerprint before promotion
- `pid=1287`
- `started_at=2026-04-23T13:44:27.566171Z`
- `code_source_main=/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`

### Promotion execution
- Command: `./tools/promotion/promotion.sh adapter+ui`
- Log: `tools/verification/logs/promotion_20260424_011841.log`
- Adapter segment evidence in log:
  - `adapter_restart_method=launchctl_kickstart_k`
  - `adapter_restart_truth=changed`
  - `adapter_pre_pid=1287`
  - `adapter_post_pid=53983`
  - `adapter_pre_started_at=2026-04-23T13:44:27.566171Z`
  - `adapter_post_started_at=2026-04-23T17:18:44.473230Z`

### Fingerprint after promotion
- `pid=53983`
- `started_at=2026-04-23T17:18:44.473230Z`
- `code_source_main=/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`

Restart truth conclusion: changed (effective)

## OpenClaw-only Revalidation (post-restart-truth)
- Live request executed via gateway mode
- Request ID: `21c8ad3c8dd8`
- `GET /debug/request_evidence?request_id=21c8ad3c8dd8` => found
- `GET /agents/control` (OpenClaw card):
  - `traffic_truth=real_request_observed`
  - `last_request_at=2026-04-23T17:19:22.300286Z`
  - `integration_truth=attached_with_backup`

## Decision
- Restart-truth repair: pass
- OpenClaw post-restart single-scene alignment: pass
- Classification: previous D1 conflict was promotion restart-truth related, not remaining OpenClaw read-model logic failure under updated running instance.
