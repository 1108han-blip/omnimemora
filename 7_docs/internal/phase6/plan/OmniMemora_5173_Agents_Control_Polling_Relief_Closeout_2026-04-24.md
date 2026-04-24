# OmniMemora 5173 Agents-Control Polling Relief Closeout (2026-04-24)

## 1. Scope

This is a docs-only closeout for UI pressure-relief commit `51cba0b`.

Conclusion scope is strictly limited to:

- `5173` no longer amplifies `/agents/control` polling from Overview.
- This record does **not** claim that `18011 /agents/control` root cause is solved.

No code changes, no backend semantic changes, and no schema changes are included in this closeout.

## 2. Repo Reality

- Commit under closeout: `51cba0b`
- Commit summary: `ui(dashboard): decouple controls polling and add visibility-aware backoff`
- Changed files (from commit):
  - `6_console/demo-dashboard/src/App.tsx`
  - `6_console/demo-dashboard/src/components/AgentsDashboard.tsx`

Static behavior aligned with relief intent:

- Overview no longer does unconditional 5s `/agents/control` polling.
- Agent control page keeps polling but with visibility-aware pause and slower cadence.

## 3. Promotion / Build Evidence

- Promotion log: `tools/verification/logs/promotion_20260424_232108.log`
- Log facts:
  - `[3/6] 执行 npm run build ...`
  - `UI build 成功`
  - `ui:promoted`
  - UI checks passed for `/` and `/agents?tenant=all`

## 4. Running Observation (Frequency Scope)

Running observation is limited to pressure amplification behavior:

- After `51cba0b`, Overview polling path is decoupled from `/agents/control` by implementation.
- `/agents/control` is no longer on the default 5s Overview loop path.
- This reduces control-surface request amplification from `5173`.

This record intentionally does not use this UI-side relief to assert backend performance recovery.

## 5. Boundary Statement

- Proven: UI pressure reduction at `5173` side.
- Not proven here: `18011 /agents/control` latency/timeout root cause eliminated.
- Next batch required: backend diagnosis-only (sampling + call graph + scale profile).

## 6. Traceability

- Closeout date: 2026-04-24
- Evidence type: docs-only closeout with promotion log + repo static check

