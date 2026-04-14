# Phase 3 Memory Leak Sampling

- Timestamp: 2026-04-13 12:20:43 +08:00
- DurationSeconds: 600
- RequestIntervalSeconds: 2
- SampleIntervalSeconds: 30
- Runtime PID: 6156
- Adapter PID: 12768

## Request Summary

- request_success: 282
- request_fail: 0
- fail_rate_percent: 0

## Memory Delta (Private MB)

- runtime_private_mb_start: 53.36
- runtime_private_mb_end: 55.36
- runtime_private_mb_delta: 2
- adapter_private_mb_start: 64.56
- adapter_private_mb_end: 63.24
- adapter_private_mb_delta: -1.32

## Health After Run

- runtime_health: True
- adapter_health: True

## Verdict

- no_obvious_memory_leak: True

## Samples

| t | runtime_ws_mb | runtime_pm_mb | adapter_ws_mb | adapter_pm_mb |
|---|---:|---:|---:|---:|
| 12:10:43 | 61.93 | 53.36 | 77.91 | 64.56 |
| 12:11:15 | 61.99 | 53.42 | 78.82 | 65.05 |
| 12:11:44 | 61.99 | 53.42 | 81.13 | 67.79 |
| 12:12:14 | 62.16 | 53.58 | 73.95 | 60.44 |
| 12:12:43 | 62.3 | 53.75 | 73.39 | 59.85 |
| 12:13:13 | 62.31 | 53.75 | 74.11 | 60.58 |
| 12:13:43 | 62.34 | 53.77 | 75.04 | 62 |
| 12:14:15 | 62.72 | 54.21 | 75.96 | 62.54 |
| 12:14:44 | 62.78 | 54.27 | 73.51 | 60.1 |
| 12:15:14 | 62.81 | 54.52 | 73.5 | 59.97 |
| 12:15:44 | 63.02 | 54.81 | 74.74 | 61.53 |
| 12:16:14 | 63.13 | 54.94 | 75.64 | 62.68 |
| 12:16:44 | 63.13 | 54.94 | 76.85 | 63.33 |
| 12:17:14 | 62.96 | 54.69 | 74.12 | 60.71 |
| 12:17:44 | 62.97 | 54.69 | 75.03 | 61.89 |
| 12:18:13 | 62.97 | 54.69 | 75.93 | 63.17 |
| 12:18:43 | 63.03 | 54.69 | 76.86 | 63.46 |
| 12:19:13 | 63.43 | 55.14 | 75.2 | 62.16 |
| 12:19:43 | 63.55 | 55.32 | 76.16 | 63.06 |
| 12:20:13 | 63.58 | 55.36 | 76.51 | 63.24 |
