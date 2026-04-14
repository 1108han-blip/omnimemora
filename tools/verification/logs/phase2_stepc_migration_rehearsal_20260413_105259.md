# Phase 2 Step C Migration Rehearsal

- Timestamp: 2026-04-13 10:53:03 +08:00
- Runtime URL: http://127.0.0.1:8765
- Adapter URL: http://127.0.0.1:18011
- Total checks: 7
- Passed: 7
- Failed: 0

## Results

| Check | Result | Evidence |
|---|---|---|
| Health: runtime /health | PASS | port=8765 |
| Health: adapter /health | PASS | port=18011 |
| Runtime: write success | PASS | memory_id_present=True |
| Runtime: query recalls written content | PASS | total=1 |
| Adapter: query success | PASS | request_id_present=True |
| Adapter: request_count grows | PASS | before=3, after=4 |
| Adapter: token savings endpoint available | PASS | saved_tokens_total=148 |

## Acceptance

- Runtime + Adapter health: True
- Write/query closed-loop: True
- request_count growth observed: True
- token savings endpoint available: True

## Note

- Services are kept running after this script for continued Phase 2/3 work.
