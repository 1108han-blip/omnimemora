---
doc_id: PHASE6-TOKEN-SAVING-EFFECTIVENESS-GATE-2026-04-24
title: OmniMemora Token Saving Effectiveness Gate
doc_type: running-validation-record
status: completed
date: 2026-04-24
repo_commit_validated: 5a95b1b
running_code_revision: 51b268a
previous_closeout_commit: 5a95b1b
---

# OmniMemora Token Saving Effectiveness Gate (2026-04-24)

## Scope

This batch defines and executes the minimum product effectiveness gate for token saving.

Goal:

- Verify that controlled context compilation produces explainable token saving evidence in real non-Codex requests.
- Verify that this does not obviously degrade answer quality.
- Verify that client flow is not disturbed.

Included validation objects:

- Claude Code default
- Claude Code `cc-haha`
- OpenClaw

Excluded:

- Codex install/run/live validation
- new memory capability
- new identity model
- promotion unless required by repo/running drift
- UI changes
- heavyweight evaluator or benchmark system

## Pre-flight

- Worktree before validation: clean
- Repo HEAD before validation: `5a95b1b`
- Running promotion state:
  - `repo_revision=51b268a`
  - `target=runtime+adapter+ui`
  - `final_status=running_reality_promoted`
  - `primary_breakpoint=none`
  - `log_file=/Users/sc/Documents/AI2/Vault/13_OmniMemora/OmniMemora/tools/verification/logs/promotion_20260424_130532.log`
- Promotion decision for this batch:
  - no promotion executed
  - reason: HEAD `5a95b1b` is docs-only closeout; running code revision `51b268a` is already the validated AccessPlan actual enforcement runtime

Health snapshot:

- `GET http://127.0.0.1:8765/health`
  - `status=ok`
  - `mode=local`
  - `uptime_seconds=2263`
- `GET http://127.0.0.1:18011/debug/runtime_fingerprint`
  - `pid=31501`
  - `started_at=2026-04-24T05:05:46.509578Z`
  - `code_source_main=/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`
- `GET http://127.0.0.1:18011/health`
  - `status=healthy`
  - `mode=full`
  - `routing_requested=true`
  - `routing_effective=true`

## Repo Reality Audit

Existing surfaces are sufficient for the minimum effectiveness gate.

Meter fields already available:

- `baseline_tokens_estimate`
- `actual_tokens_estimate`
- `saved_tokens_estimate`
- `savings_ratio`
- `packed_memory_count`
- `local_cards_used`
- `coverage_satisfied`
- `packing_enabled`
- `context_bypass`
- `access_plan`
- `actual_enforcement`
- `enforcement_trace`

`request_evidence` fields already available:

- `request.request_id`
- `request.agent_family`
- `request.identity`
- top-level `access_plan`
- top-level `actual_enforcement`
- top-level `enforcement_trace`
- `context.before_tokens`
- `context.after_tokens`
- `context.saved_tokens`
- `context.savings_ratio`
- `context.context_state`
- selected/dropped memory counts

Repo audit decision:

- no code change needed
- no new UI needed
- no complex evaluator needed
- proceed directly to running validation

## Minimal Gate Definition

Required evidence per object:

- request evidence can be queried by `request_id`
- `access_plan` is present
- `actual_enforcement` is present and not unavailable
- `enforcement_trace` is present
- before/after token estimates are present
- compiled context token count is explainable as `actual_tokens_estimate` / `context.after_tokens`
- estimated saved tokens are present and non-negative
- quality status can be judged from current-request preservation
- client flow status can be judged from command exit / gateway response

Pass condition:

- all required evidence exists
- `saved_tokens_estimate >= 0`
- the response preserves the requested marker and simple factual task
- client command returns successfully

Failure condition:

- evidence missing
- actual enforcement unavailable
- token saving cannot be calculated
- obvious response-quality regression
- obvious client-flow disturbance

Quality rubric for this minimum gate:

- `not_degraded`: response preserves the prompt marker and answers the simple arithmetic task correctly
- `uncertain`: response returns but does not provide enough content to judge
- `degraded`: response loses the user request, answers incorrectly, or fails due to the product path

Client-flow rubric:

- `not_disturbed`: client command exits successfully and proxy event status is success
- `disturbed`: client command fails, gateway response is failed, or user-visible flow is broken

## Running Validation

### Claude Code Default

Trigger:

```bash
claude -p "TOKEN-SAVING-GATE-DEFAULT-20260424. Reply with marker DEFAULT-GATE-OK and answer 7+5 in one short sentence."
```

Observed client output:

- `DEFAULT-GATE-OK 7+5 equals 12.`

Evidence:

- request_id: `5b827a546f74`
- endpoint/path: `POST /llm/v1/messages`
- proxy status: `success`
- agent family: `claude_code`
- instance: `claude_code`
- planned `access_plan`: present
- `actual_enforcement`: present
- `enforcement_trace`: present
- actual enforced domain:
  - `domain_id=default:instance_private:claude_code`
  - `operation=search`
  - `decision=applied`
  - `scope_ref.agent_id=claude_code`
  - `scope_ref.sharing_mode=isolated`

Token saving evidence:

- context before tokens: `137`
- compiled context token count / after tokens: `13`
- estimated saved tokens: `124`
- savings ratio: `0.905`
- meter `baseline_tokens_estimate=137`
- meter `actual_tokens_estimate=13`
- meter `saved_tokens_estimate=124`
- meter `savings_ratio=0.905`
- saved token estimate is non-negative: yes

Quality and flow judgement:

- quality status: `not_degraded`
- reason: marker preserved and `7+5=12` answered correctly
- client flow status: `not_disturbed`
- reason: command exited successfully and proxy event status was `success`

Conclusion:

- pass

### Claude Code `cc-haha`

Trigger:

```bash
CLAUDE_CONFIG_DIR="$HOME/.claude/cc-haha" claude -p "TOKEN-SAVING-GATE-CCHAHA-20260424. Reply with marker CCHAHA-GATE-OK and answer 8+6 in one short sentence."
```

Observed client output:

- `CCHAHA-GATE-OK: 8 + 6 equals 14.`

Evidence:

- request_id: `e9bd3b614702`
- endpoint/path: `POST /llm/v1/messages`
- proxy status: `success`
- agent family: `claude_code`
- instance: `claude_code`
- profile trigger: `CLAUDE_CONFIG_DIR=$HOME/.claude/cc-haha`
- planned `access_plan`: present
- `actual_enforcement`: present
- `enforcement_trace`: present
- actual enforced domain:
  - `domain_id=default:instance_private:claude_code`
  - `operation=search`
  - `decision=applied`
  - `scope_ref.agent_id=claude_code`
  - `scope_ref.sharing_mode=isolated`

Token saving evidence:

- context before tokens: `137`
- compiled context token count / after tokens: `13`
- estimated saved tokens: `124`
- savings ratio: `0.905`
- meter `baseline_tokens_estimate=137`
- meter `actual_tokens_estimate=13`
- meter `saved_tokens_estimate=124`
- meter `savings_ratio=0.905`
- saved token estimate is non-negative: yes

Quality and flow judgement:

- quality status: `not_degraded`
- reason: marker preserved and `8+6=14` answered correctly
- client flow status: `not_disturbed`
- reason: command exited successfully and proxy event status was `success`

Control/identity note:

- `cc-haha` remains a Claude Code family variant and is not expected to appear as an independent control card.
- Validation is by request evidence / meter, not by a separate control card.

Conclusion:

- pass

### OpenClaw

Trigger:

```bash
openclaw infer model run --gateway --json --model minimax/MiniMax-M2.7 --prompt "TOKEN-SAVING-GATE-OPENCLAW-20260424. Reply with marker OPENCLAW-GATE-OK and answer 9+4 in one short sentence."
```

Observed client output:

- `ok=true`
- `OPENCLAW-GATE-OK 9 加上 4 等于 13。`

Evidence:

- request_id: `86c8bea8faf4`
- endpoint/path: `POST /llm/v1/messages`
- proxy status: `success`
- agent family: `openclaw`
- instance: `openclaw`
- planned `access_plan`: present
- `actual_enforcement`: present
- `enforcement_trace`: present
- actual enforced domain:
  - `domain_id=default:instance_private:openclaw`
  - `operation=search`
  - `decision=applied`
  - `scope_ref.agent_id=openclaw`
  - `scope_ref.sharing_mode=isolated`

Token saving evidence:

- context before tokens: `2532`
- compiled context token count / after tokens: `13`
- estimated saved tokens: `2519`
- savings ratio: `0.995`
- meter `baseline_tokens_estimate=2532`
- meter `actual_tokens_estimate=13`
- meter `saved_tokens_estimate=2519`
- meter `savings_ratio=0.995`
- saved token estimate is non-negative: yes

Quality and flow judgement:

- quality status: `not_degraded`
- reason: marker preserved and `9+4=13` answered correctly
- client flow status: `not_disturbed`
- reason: OpenClaw returned `ok=true` and proxy event status was `success`

Conclusion:

- pass

## Control Consistency

Command:

```bash
curl -sS http://127.0.0.1:18011/agents/control
```

Observed:

- `claude_code`
  - `installed=true`
  - `routing_enabled=true`
  - `traffic_truth=real_request_observed`
  - `route_truth=effective`
  - `integration_truth=attached_with_backup`
  - `identity_scope=family`
  - `last_request_at=2026-04-24T05:44:19.061378Z`
- `openclaw`
  - `installed=true`
  - `routing_enabled=true`
  - `traffic_truth=real_request_observed`
  - `route_truth=effective`
  - `integration_truth=attached_with_backup`
  - `identity_scope=family`
  - `last_request_at=2026-04-24T05:44:47.321706Z`
- `codex_cli`
  - `installed=false`
  - `routing_enabled=false`
  - `traffic_truth=no_recent_evidence`
  - `route_truth=off`
  - `integration_truth=detached`

Consistency judgement:

- no control/evidence contradiction for Claude Code
- no control/evidence contradiction for OpenClaw
- Codex did not participate in this gate

## Overall Result

Result:

`Passed for non-Codex token-saving effectiveness gate`

Acceptance criteria:

- three non-Codex objects have request evidence: pass
- three objects have explainable token saving: pass
- three objects retain actual enforcement: pass
- no obvious quality regression: pass
- no obvious client-flow disturbance: pass
- Codex not installed/run/live-validated: pass

Interpretation:

- This is a minimum executable effectiveness gate, not a quality benchmark.
- The token saving evidence is explainable from current meter/read-model fields.
- The compiled context token count is represented by `actual_tokens_estimate` / `request_evidence.context.after_tokens`.
- The gate does not prove final-answer quality beyond current-request preservation for the selected simple prompts.

Next boundary:

- Do not expand into Codex validation inside this line.
- Do not start a heavyweight benchmark from this record.
- If future product work needs stronger quality claims, open a separate small evaluator line with explicit fixtures and acceptance criteria.
