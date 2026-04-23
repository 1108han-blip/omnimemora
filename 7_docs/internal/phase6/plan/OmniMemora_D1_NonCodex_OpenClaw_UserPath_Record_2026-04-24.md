# OmniMemora D1 Non-Codex OpenClaw User-Path Validation Record (2026-04-24)

## Validation Boundary
- Included scenario only: OpenClaw live request
- Excluded from this record: Codex live validation

## Scenario: OpenClaw
- Client instance: OpenClaw (gateway mode)
- Trigger command:
  - `openclaw infer model run --gateway --json --model minimax/MiniMax-M2.7 --prompt "D1-LIVE-OPENCLAW-20260424 token only: D1-OPENCLAW-SEQ"`
- Supplemental verification trigger:
  - `openclaw infer model run --gateway --json --model minimax/MiniMax-M2.7 --prompt "请给出一个 Python API 登录模块的实现要点，包含输入校验、token 生命周期与错误处理。"`
- Request path (from proxy events): `/llm/v1/messages`
- Representative request IDs:
  - `32253c6f2e55` (token prompt)
  - `5d1339cbd64d` (long task prompt)

## Evidence Checks
- `GET /debug/request_evidence?request_id=32253c6f2e55` => found
- `GET /debug/request_evidence?request_id=5d1339cbd64d` => found
- `GET /requests/5d1339cbd64d/meter` => found
  - `agent=openclaw`
  - `client=openclaw-gateway`
  - `baseline_tokens_estimate=127` (non-tiny request)

## Attach Truth / Boundary Check
- OpenClaw attach marker exists: `~/.openclaw/.omnimemora.attach.marker`
- `GET /agents/control` shows:
  - `family_id=openclaw`
  - `installed=true`
  - `integration_truth=attached_with_backup`
  - no attach rollback observed

## 5173/Control vs Evidence Consistency Check
- Evidence side: OpenClaw request evidence is queryable and meter exists.
- Control side (backend truth consumed by 5173): `openclaw.traffic_truth=no_recent_evidence`.
- This forms a control-vs-evidence semantic mismatch for this validation window.

## Judgement
- Partial pass:
  - real request + request_id + request_evidence: pass
  - attach truth non-regression: pass
  - control/evidence consistency: fail (mismatch)
