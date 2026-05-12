# OmniMemora D1 Non-Codex Promotion Record (2026-04-24)

> **2026-05-10 supersession**: 本记录中的 `5173` 可达性属于当时 running reality 证据。当前产品口径为 Desktop app 控制/展示面；`5173` 不再是默认依赖。

## Scope
- Batch scope: D1 closeout (non-Codex gate only)
- Promotion target: `adapter+ui`
- Repo revision: `3fa82a1`

## Promotion Execution
- Command: `./tools/promotion/promotion.sh adapter+ui`
- Datetime: 2026-04-24 00:43:45 CST
- Log file: `tools/verification/logs/promotion_20260424_004345.log`

## Running Reality Before
- runtime `8765/health`: healthy
- adapter `18011/health`: healthy
- ui `5173`: reachable (`200`)
- adapter process: `_run_adapter.py` present
- ui process: `vite --host 127.0.0.1 --port 5173` present

## Running Reality After
- runtime `8765/health`: healthy
- adapter `18011/health`: healthy
- ui `5173`: reachable (`200`)
- adapter process: `_run_adapter.py` present
- ui process: `vite --host 127.0.0.1 --port 5173` present

## Promotion Result
- `promotion_type`: `adapter+ui`
- `result`: `running_reality_promoted`
- `primary_breakpoint`: `none`
- `declaration`: running reality promoted for adapter+ui scope

## Notes
- `adapter+ui` succeeded and no ingress-promotion drift requiring auto-escalation to `runtime+adapter+ui` was observed at promotion stage.
- D1 acceptance still depends on user-path truth consistency checks (recorded separately).
