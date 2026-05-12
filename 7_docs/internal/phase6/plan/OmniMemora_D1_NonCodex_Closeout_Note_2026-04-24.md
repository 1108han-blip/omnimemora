# OmniMemora D1 Non-Codex Closeout Note (2026-04-24)

> **2026-05-10 supersession**: 本记录中的 `5173` 健康性属于历史证据快照。当前产品口径为 Desktop app 控制/展示面；`5173` 仅 legacy/dev 使用。

## Scope
- Batch scope: D1 closeout (non-Codex only)
- Included: Claude default, Claude `cc-haha`, OpenClaw
- Excluded: Codex live validation

## Final Gate Decision
- Decision: **Passed**
- Final classification:
  - repository reality: pass
  - running reality: pass
  - user-path reality (non-Codex): pass
- Final explanation:
  - D1 non-Codex acceptance is established after adapter restart-truth repair.
  - The earlier OpenClaw control/evidence mismatch is classified as a promotion restart-truth problem, not a remaining OpenClaw read-model logic failure under the updated running instance.

## Layered Conclusion

### 1. Repository Reality
- Candidate remained in the intended D1 file scope.
- No README/main-plan sync or Batch 3 work was mixed into this D1 closeout batch.
- D1-related code paths are limited to:
  - ingress compile+meter convergence
  - control/read-model truth alignment
  - 5173 family-scope contract alignment
  - adapter promotion restart-truth enforcement

### 2. Running Reality
- `adapter+ui` promotion is now validated with runtime fingerprint change evidence, not only API reachability.
- Current adapter runtime fingerprint snapshot:
  - `pid=53983`
  - `started_at=2026-04-23T17:18:44.473230Z`
  - `code_source_main=/Users/sc/.omnimemora/service/current/5_connectors/adapter/main.py`
- `8765 / 18011 / 5173` are healthy in the promoted running reality.

### 3. User-Path Reality (Non-Codex)
- Claude default profile:
  - pass
  - real request and `request_evidence` confirmed in `OmniMemora_D1_NonCodex_Claude_UserPath_Record_2026-04-24.md`
- Claude `cc-haha`:
  - pass
  - family-scope contract preserved; no extra control card
- OpenClaw:
  - pass
  - post-restart aligned request: `21c8ad3c8dd8`
  - `request_evidence` lookup: pass
  - control card aligned: `traffic_truth=real_request_observed`
  - `last_request_at=2026-04-23T17:19:22.300286Z`
  - `integration_truth=attached_with_backup`

## Evidence Chain
- Non-Codex promotion record:
  - `OmniMemora_D1_NonCodex_Promotion_Record_2026-04-24.md`
- Claude user-path validation:
  - `OmniMemora_D1_NonCodex_Claude_UserPath_Record_2026-04-24.md`
- OpenClaw initial user-path validation:
  - `OmniMemora_D1_NonCodex_OpenClaw_UserPath_Record_2026-04-24.md`
- OpenClaw minimal fix batch:
  - `OmniMemora_D1_OpenClaw_Minimal_Fix_Record_2026-04-24.md`
- Restart-truth repair and final alignment:
  - `OmniMemora_D1_Restart_Truth_Repair_Record_2026-04-24.md`

## Historical Resolution Path
- Initial D1 non-Codex run:
  - Claude paths passed
  - OpenClaw request evidence existed but control truth under-reported live traffic
- OpenClaw minimal read-model fix:
  - repo checks passed
  - running instance still did not reflect the expected truth
- Restart-truth repair:
  - promotion gate tightened to require real adapter process replacement
  - new running instance fingerprint changed
  - OpenClaw control/evidence alignment passed under the updated process

## Current Running Snapshot
- `GET /debug/runtime_fingerprint` confirms the promoted adapter instance is the current service process.
- `GET /agents/control` current snapshot confirms:
  - `openclaw.traffic_truth=real_request_observed`
  - `openclaw.last_request_at=2026-04-23T17:19:22.300286Z`
  - `openclaw.integration_truth=attached_with_backup`
- No new validation scene was added for this closeout snapshot; it preserves the already-established post-restart evidence chain.

## Explicit Gate Statement
- D1 non-Codex gate is closed as **Passed**.
- Codex live validation remains paused and excluded from this D1 gate.
- README/main-plan sync and Batch 3 non-Codex planning belong to the next batch, not this closeout.
