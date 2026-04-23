# OmniMemora D1 Non-Codex Claude User-Path Validation Record (2026-04-24)

## Validation Boundary
- Included scenarios only:
  - Claude Code default profile
  - Claude Code `cc-haha` profile
- Excluded from this record:
  - Codex live validation

## Scenario A: Claude Code Default Profile
- Client instance: Claude Code default profile (`~/.claude/settings.json`)
- Trigger command:
  - `claude -p "D1-LIVE-DEFAULT-20260424 token only: D1-DEFAULT-SEQ"`
- Request path (from proxy events): `/llm/v1/messages`
- Request ID: `86d863760cc8`
- Request evidence lookup:
  - `GET /debug/request_evidence?request_id=86d863760cc8` => found
  - `request.agent_family=claude_code`
  - `status.request_status=warning`
- Meter lookup:
  - `GET /requests/86d863760cc8/meter` => found
  - `agent=claude_code`, `client=claude_code-gateway`
- 5173/Control truth observations (via backend truth source consumed by 5173):
  - `family_id=claude_code`
  - `traffic_truth=real_request_observed`
  - `identity_scope=family`
  - `scope_note` present and explicit about `cc-haha` as family aggregate
- Judgement: pass

## Scenario B: Claude Code cc-haha
- Client instance: Claude Code `cc-haha` profile (`CLAUDE_CONFIG_DIR=~/.claude/cc-haha`)
- Trigger command:
  - `CLAUDE_CONFIG_DIR="$HOME/.claude/cc-haha" claude -p "D1-LIVE-CCHAHA-20260424 token only: D1-CCHAHA-SEQ"`
- Request path (from proxy events): `/llm/v1/messages`
- Request ID: `763983c298bd`
- Request evidence lookup:
  - `GET /debug/request_evidence?request_id=763983c298bd` => found
  - `request.agent_family=claude_code`
  - `status.request_status=warning`
- Meter lookup:
  - `GET /requests/763983c298bd/meter` => found
  - `agent=claude_code`, `client=claude_code-gateway`
- 5173/Control truth observations:
  - No standalone `cc-haha` control card surfaced
  - Claude card remains family-scope (`identity_scope=family`)
  - `scope_note` explicitly states profile-level validation should use request evidence
- Judgement: pass (family-scope semantics preserved)

## Claude Aggregate Conclusion
- Default + `cc-haha` both produced real requests through `18011` and both are queryable by `request_id` in `request_evidence`.
- `cc-haha` did not get promoted into an independent control card; family-scope contract is intact.
