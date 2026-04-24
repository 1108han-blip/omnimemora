---
doc_id: PHASE6-RUNTIME-PROMOTION-RESTART-TRUTH-REPAIR-2026-04-24
title: OmniMemora Runtime Promotion Restart Truth Repair
doc_type: repair-record
status: closed
date: 2026-04-24
previous_stop_rule_source_commit: 36b80e9
---

# OmniMemora Runtime Promotion Restart Truth Repair (2026-04-24)

## 1. Scope

This batch repaired runtime restart truth enforcement in promotion flow only.

In scope:

- `tools/promotion/promotion.sh` runtime promotion gate
- runtime pre/post fingerprint collection
- runtime restart fallback chain and hard gate
- promotion log runtime restart fields

Out of scope:

- no product logic changes in runtime/adapter/UI
- no live validation
- no Codex validation

Codex boundary:

`Codex is product-compatible in principle, but protected/deferred as a local validation client.`

## 2. Problem Source

Previous running revalidation (`36b80e9`) stopped at promotion gate because:

- adapter restart truth changed
- runtime process identity did not change (`pid` unchanged)

So the stop-rule was caused by promotion restart-truth weakness, not AccessPlan enforcement logic itself.

## 3. Implementation Summary

Updated `tools/promotion/promotion.sh` with runtime parity to adapter-grade restart truth:

- added `read_runtime_fingerprint()` with output:
  - `pid|uptime_seconds|command`
- runtime fingerprint collection details:
  - `pid`: launchctl print first, `pgrep -f "omnimemora-runtime.*serve"` fallback
  - `uptime_seconds`: from `GET /health`
  - `command`: `ps -p <pid> -o command=`
- added restart fallback chain:
  1. `launchctl kickstart -k`
  2. `launchctl stop/start`
  3. `direct kill+start` fallback (with `OMNIMEMORA_RUNTIME_PORT` and `OMNIMEMORA_ADAPTER_PORT`)
- each method is followed by health wait + fingerprint re-read
- runtime hard gate now requires:
  - health reachable
  - post pid non-empty/non-unknown
  - pre pid exists => post pid changed
  - if pre/post uptime readable: post uptime must reset (`post < pre`) or be within short window (`<=120`)
  - post command must contain `$CURRENT_SERVICE_DIR/tools/omnimemora-runtime`
- on failure returns non-zero with explicit reasons:
  - `runtime:failed:api_unreachable`
  - `runtime:failed:runtime_restart_not_effective`
  - `runtime:failed:runtime_restart_pid_unchanged`
  - `runtime:failed:command_mismatch`

## 4. Validation Executed

### Static checks

- `bash -n tools/promotion/promotion.sh` ✅
- `git diff --check` ✅

### Promotion-only runtime validation

Executed:

```bash
./tools/promotion/promotion.sh runtime+adapter+ui
```

Promotion log:

- `tools/verification/logs/promotion_20260424_124303.log`

Runtime restart-truth fields in log:

- `runtime_pre_pid=1302`
- `runtime_pre_uptime_seconds=49270`
- `runtime_pre_command=/Users/sc/.omnimemora/service/current/tools/omnimemora-runtime serve`
- `runtime_post_pid=26605`
- `runtime_post_uptime_seconds=0`
- `runtime_post_command=/Users/sc/.omnimemora/service/current/tools/omnimemora-runtime serve`
- `runtime_restart_truth=changed`
- `runtime_restart_method=launchctl_kickstart_k`

Adapter restart-truth remained valid:

- `adapter_pre_pid=24291`
- `adapter_post_pid=27068`
- `adapter_restart_truth=changed`
- `adapter_restart_method=launchctl_kickstart_k`

Post checks:

- runtime launchctl:
  - `pid=26605`
  - `program=/Users/sc/.omnimemora/service/current/tools/omnimemora-runtime`
- runtime health:
  - `uptime_seconds=42` (fresh window)
- adapter fingerprint still points to `service/current`

## 5. Conclusion

Repair result: **passed** for runtime promotion restart-truth gate.

This closes the promotion precondition blocker from `36b80e9` and unlocks next batch re-entry to AccessPlan running revalidation.

## 6. Next Batch

Next batch should resume:

- AccessPlan actual enforcement running revalidation
- non-Codex targets only:
  - Claude Code default
  - Claude Code `cc-haha`
  - OpenClaw

No Codex live validation in that gate.
