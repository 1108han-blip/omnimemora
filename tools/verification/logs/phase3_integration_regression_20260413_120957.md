# Phase 3 Integration + Regression

- Timestamp: 2026-04-13 12:09:58 +08:00
- Total checks: 8
- Passed: 8
- Failed: 0

## Results

| Check | Result | Evidence |
|---|---|---|
| Integration: Codex attach command succeeds | PASS | Codex is already configured. |
| Integration: memory call works after Codex attach | PASS | request_id=req-ae945415 |
| Integration: main flow unaffected | PASS | runtime=True, adapter=True |
| Regression: write->query->delete->query | PASS | before=1, after=0 |
| Regression: agent scope isolation | PASS | agent-b total=0 |
| Regression: token savings usage increments | PASS | before=0, after=1, saved=37 |
| Regression: invalid scope returns 501 | PASS | status=501 |
| Regression: empty result path is normal | PASS | total=0 |
