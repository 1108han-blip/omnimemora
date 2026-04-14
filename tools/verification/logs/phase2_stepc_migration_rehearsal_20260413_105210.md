# Phase 2 Step C Migration Rehearsal

- Timestamp: 2026-04-13 10:52:14 +08:00
- Runtime URL: http://127.0.0.1:8765
- Adapter URL: http://127.0.0.1:18011
- Total checks: 7
- Passed: 6
- Failed: 1

## Results

| Check | Result | Evidence |
|---|---|---|
| Health: runtime /health | PASS | port=8765 |
| Health: adapter /health | PASS | port=18011 |
| Runtime: write success | PASS | memory_id_present=True |
| Runtime: query recalls written content | FAIL | total=0 |
| Adapter: query success | PASS | request_id_present=True |
| Adapter: request_count grows | PASS | before=1, after=2 |
| Adapter: token savings endpoint available | PASS | saved_tokens_total=74 |

## Acceptance

- Runtime + Adapter health: True
- Write/query closed-loop: False
- request_count growth observed: True
- token savings endpoint available: True

## Note

- Services are kept running after this script for continued Phase 2/3 work.
