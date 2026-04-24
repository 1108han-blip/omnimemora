---
doc_id: PHASE6-ACCESSPLAN-ACTUAL-ENFORCEMENT-RUNNING-REVALIDATION-AFTER-RESTART-REPAIR-2026-04-24
title: OmniMemora AccessPlan Actual Enforcement Running Revalidation After Restart Repair
doc_type: running-validation-record
status: completed
date: 2026-04-24
repo_commit_validated: 51b268a
previous_blocked_validation: 36b80e9
adapter_actual_trace_repair: 8975395
runtime_restart_truth_repair: 51b268a
---

# OmniMemora AccessPlan Actual Enforcement Running Revalidation After Restart Repair (2026-04-24)

## Scope

This batch validates non-Codex running reality only.

Validation chain:

`planned access_plan -> runtime enforcement_trace -> adapter meter -> request_evidence`

Included objects:

- Claude Code default
- Claude Code `cc-haha` profile
- OpenClaw

Excluded:

- code changes
- promotion repair
- Codex install, attach, or live request

Codex boundary:

`Codex is product-compatible in principle, but protected/deferred as a local validation client.`

## Pre-flight

- Worktree before validation: clean
- Current repo commit: `51b268a`
- Baseline commits recorded:
  - `8975395` adapter actual trace repair
  - `51b268a` runtime promotion restart truth repair
  - `36b80e9` previous blocked validation

Pre-promotion health and fingerprint:

- `GET http://127.0.0.1:8765/health`
  - `status=ok`
  - `mode=local`
  - `uptime_seconds=1330`
  - `store_type=sqlite`
- `GET http://127.0.0.1:18011/debug/runtime_fingerprint`
  - `pid=27068`
  - `started_at=2026-04-24T04:43:16.765593Z`
  - `memory_backend_url=http://127.0.0.1:8765`
  - `code_source_main=/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`
- `GET http://127.0.0.1:18011/health`
  - `status=healthy`
  - `mode=full`
  - `routing_requested=true`
  - `routing_effective=true`

## Promotion

Executed:

```bash
./tools/promotion/promotion.sh runtime+adapter+ui
```

Promotion log:

- `/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/tools/verification/logs/promotion_20260424_130532.log`

Required restart-truth checks:

- `runtime_restart_truth=changed`
- `runtime_pre_pid=26605`
- `runtime_post_pid=31046`
- `runtime_pre_pid != runtime_post_pid`: yes
- `runtime_post_command=/Users/sc/.omnimemora/service/current/tools/omnimemora-runtime serve`
- `adapter_restart_truth=changed`
- adapter pre fingerprint:
  - `pid=27068`
  - `started_at=2026-04-24T04:43:16.765593Z`
- adapter post fingerprint:
  - `pid=31501`
  - `started_at=2026-04-24T05:05:46.509578Z`
- final status: `running_reality_promoted`

Post-promotion health and fingerprint:

- `GET http://127.0.0.1:8765/health`
  - `status=ok`
  - `uptime_seconds=33`
- `GET http://127.0.0.1:18011/debug/runtime_fingerprint`
  - `pid=31501`
  - `started_at=2026-04-24T05:05:46.509578Z`
  - `code_source_main=/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`
- `GET http://127.0.0.1:18011/health`
  - `status=healthy`
  - `routing_requested=true`
  - `routing_effective=true`

Promotion gate decision:

- Runtime rollover: pass
- Adapter rollover: pass
- Live request gate: entered

## Live Requests

### Claude Code Default

- Trigger:
  - `claude -p "ACCESSPLAN-ACTUAL-DEFAULT-20260424 token only: AP-ACTUAL-DEFAULT-SEQ"`
- Endpoint/path:
  - `POST /llm/v1/messages`
- Client command exit:
  - `0`
- Proxy event status:
  - `success`
- HTTP status:
  - `200` by successful gateway response path
- request_id:
  - `941a65ec4c90`
- observed identity:
  - `family=claude_code`
  - `instance=claude_code`
- user-side flow disturbed:
  - no

### Claude Code `cc-haha`

- Trigger:
  - `CLAUDE_CONFIG_DIR="$HOME/.claude/cc-haha" claude -p "ACCESSPLAN-ACTUAL-CCHAHA-20260424 token only: AP-ACTUAL-CCHAHA-SEQ"`
- Endpoint/path:
  - `POST /llm/v1/messages`
- Client command exit:
  - `0`
- Proxy event status:
  - `success`
- HTTP status:
  - `200` by successful gateway response path
- request_id:
  - `5fd005303f09`
- observed identity:
  - `family=claude_code`
  - `instance=claude_code`
- user-side flow disturbed:
  - no
- profile note:
  - The live request was triggered from the `cc-haha` Claude config directory. Runtime evidence remains family-scoped under `claude_code`, matching the existing control contract that `cc-haha` is not represented as an independent control card.

### OpenClaw

- Trigger:
  - `openclaw infer model run --gateway --json --model minimax/MiniMax-M2.7 --prompt "ACCESSPLAN-ACTUAL-OPENCLAW-20260424 token only: AP-ACTUAL-OPENCLAW-SEQ"`
- Endpoint/path:
  - `POST /llm/v1/messages`
- Client command exit:
  - `0`
- Proxy event status:
  - `success`
- HTTP status:
  - `200` by successful gateway response path
- request_id:
  - `89e922878065`
- observed identity:
  - `family=openclaw`
  - `instance=openclaw`
- user-side flow disturbed:
  - no

## Evidence and Meter Cross-check

Validation commands:

```bash
curl -sS "http://127.0.0.1:18011/debug/request_evidence?request_id=<request_id>"
curl -sS "http://127.0.0.1:18011/requests/<request_id>/meter"
```

### Claude Code Default: `941a65ec4c90`

`request_evidence`:

- `access_plan`: present and non-empty
- `actual_enforcement`: present
- `actual_enforcement.status`: not emitted, therefore not `unavailable`
- `enforcement_trace`: present and non-empty
- planned read domain:
  - `domain_id=default:instance_private:claude_code`
  - `scope_type=instance_private`
  - `scope_key=claude_code`
  - `sharing_mode=isolated`
- actual enforced domain:
  - `domain_id=default:instance_private:claude_code`
  - `operation=search`
  - `decision=applied`
  - `scope_ref.tenant_id=default`
  - `scope_ref.agent_id=claude_code`
  - `scope_ref.scope=agent`
  - `scope_ref.sharing_mode=isolated`

Meter:

- `access_plan`: present
- `actual_enforcement`: present
- `enforcement_trace`: present
- `agent=claude_code`
- `client=claude_code-gateway`

Trace field coverage:

- `operation`: emitted
- `decision`: emitted
- `domain_id`: emitted
- `scope_ref`: emitted
- `reason`: not emitted
- `provenance`: not emitted
- `attempted_domains`: not emitted
- `applied_domains`: represented by `actual_enforced_domains[].decision=applied`
- `rejected_domains`: not emitted

Judgement:

- planned + actual enforcement evidence: pass
- actual trace source: pass, because meter contains `actual_enforcement` and `enforcement_trace` as persisted runtime-result fields separate from planned `access_plan`

### Claude Code `cc-haha`: `5fd005303f09`

`request_evidence`:

- `access_plan`: present and non-empty
- `actual_enforcement`: present
- `actual_enforcement.status`: not emitted, therefore not `unavailable`
- `enforcement_trace`: present and non-empty
- planned read domain:
  - `domain_id=default:instance_private:claude_code`
  - `scope_type=instance_private`
  - `scope_key=claude_code`
  - `sharing_mode=isolated`
- actual enforced domain:
  - `domain_id=default:instance_private:claude_code`
  - `operation=search`
  - `decision=applied`
  - `scope_ref.tenant_id=default`
  - `scope_ref.agent_id=claude_code`
  - `scope_ref.scope=agent`
  - `scope_ref.sharing_mode=isolated`

Meter:

- `access_plan`: present
- `actual_enforcement`: present
- `enforcement_trace`: present
- `agent=claude_code`
- `client=claude_code-gateway`

Trace field coverage:

- `operation`: emitted
- `decision`: emitted
- `domain_id`: emitted
- `scope_ref`: emitted
- `reason`: not emitted
- `provenance`: not emitted
- `attempted_domains`: not emitted
- `applied_domains`: represented by `actual_enforced_domains[].decision=applied`
- `rejected_domains`: not emitted

Judgement:

- planned + actual enforcement evidence: pass
- actual trace source: pass, because meter contains `actual_enforcement` and `enforcement_trace` as persisted runtime-result fields separate from planned `access_plan`
- profile classification caveat: none for this gate; family-scope identity is expected for `cc-haha`

### OpenClaw: `89e922878065`

`request_evidence`:

- `access_plan`: present and non-empty
- `actual_enforcement`: present
- `actual_enforcement.status`: not emitted, therefore not `unavailable`
- `enforcement_trace`: present and non-empty
- planned read domain:
  - `domain_id=default:instance_private:openclaw`
  - `scope_type=instance_private`
  - `scope_key=openclaw`
  - `sharing_mode=isolated`
- actual enforced domain:
  - `domain_id=default:instance_private:openclaw`
  - `operation=search`
  - `decision=applied`
  - `scope_ref.tenant_id=default`
  - `scope_ref.agent_id=openclaw`
  - `scope_ref.scope=agent`
  - `scope_ref.sharing_mode=isolated`

Meter:

- `access_plan`: present
- `actual_enforcement`: present
- `enforcement_trace`: present
- `agent=openclaw`
- `client=openclaw-gateway`

Trace field coverage:

- `operation`: emitted
- `decision`: emitted
- `domain_id`: emitted
- `scope_ref`: emitted
- `reason`: not emitted
- `provenance`: not emitted
- `attempted_domains`: not emitted
- `applied_domains`: represented by `actual_enforced_domains[].decision=applied`
- `rejected_domains`: not emitted

Judgement:

- planned + actual enforcement evidence: pass
- actual trace source: pass, because meter contains `actual_enforcement` and `enforcement_trace` as persisted runtime-result fields separate from planned `access_plan`
- client-flow caveat: none; OpenClaw returned `ok=true`

## Control Consistency

Command:

```bash
curl -sS http://127.0.0.1:18011/agents/control
```

Observed control truth:

- `claude_code`
  - `installed=true`
  - `routing_enabled=true`
  - `traffic_truth=real_request_observed`
  - `route_truth=effective`
  - `integration_truth=attached_with_backup`
  - `identity_scope=family`
  - `last_request_at=2026-04-24T05:06:52.409607Z`
  - `observed_requests_24h=29`
  - `scope_note` states that independent profiles such as `cc-haha` do not appear as separate control cards and should be validated through request evidence / validation records
- `openclaw`
  - `installed=true`
  - `routing_enabled=true`
  - `traffic_truth=real_request_observed`
  - `route_truth=effective`
  - `integration_truth=attached_with_backup`
  - `identity_scope=family`
  - `last_request_at=2026-04-24T05:07:31.952117Z`
  - `observed_requests_24h=24`

Consistency judgement:

- `claude_code`: no conflict with request evidence
- `cc-haha`: no conflict with request evidence because control is intentionally family-scoped
- `openclaw`: no conflict with request evidence
- no `internal_only` caveat observed in this run

## Conclusion

Result:

`Passed for non-Codex running validation`

Reason:

- promotion restart-truth precondition passed for runtime and adapter
- all three non-Codex objects produced live product-path requests
- all three request_ids are queryable in `request_evidence`
- all three meters contain planned `access_plan` plus actual `actual_enforcement` / `enforcement_trace`
- `actual_enforcement` is not unavailable for any target
- no severe client-flow disturbance was observed
- `/agents/control` does not materially contradict the request evidence

Remaining precision note:

- Current trace payload explains actual enforced domains through `operation=search`, `decision=applied`, `domain_id`, and `scope_ref`.
- It does not currently emit separate `reason`, `provenance`, `attempted_domains`, or `rejected_domains` fields. This is a field-granularity limitation, not a failure of this running validation gate.
