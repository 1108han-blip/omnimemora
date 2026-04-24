# OmniMemora DLP Batch 3 Running Validation - Non-Destructive Maintenance (2026-04-25)

## 1. Scope

Validate Batch 1/2 behavior in running reality only:

- scheduler auto-maintenance actually runs after adapter startup
- summary + ledger artifacts are queryable on running host
- `/agents/control` stays schema-stable and request path is not blocked by maintenance
- stale summary and legacy fallback paths are usable

Boundary kept:

- no code changes
- no destructive maintenance
- no product core memory change
- no user-side memory operations
- no new 5173 maintenance UI
- no Codex validation gate

---

## 2. Promotion and Restart Truth

Command:

```bash
./tools/promotion/promotion.sh adapter+ui
```

Evidence:

- promotion log: `tools/verification/logs/promotion_20260425_005112.log`
- repo revision promoted: `aedc4de`
- adapter restart truth: `changed`
  - pre fingerprint: `pid=19185, started_at=2026-04-24T15:51:06.349611Z`
  - post fingerprint: `pid=37937, started_at=2026-04-24T16:51:15.860417Z`

Note: timestamps above are UTC from promotion log; local Asia/Shanghai time is 2026-04-25 00:51+.

---

## 3. DLP Runtime Artifacts

Paths:

- `~/.omnimemora/adapter/data_lifecycle/family_window_summary.json` -> exists
- `~/.omnimemora/adapter/data_lifecycle/maintenance_state.jsonl` -> exists

Ledger evidence (tail):

- `trigger=startup_warm`, `status=success`
- `trigger=interval_refresh`, `status=success`

Sample entries:

```json
{"cycle_id":"30a404d6a865","trigger":"startup_warm","status":"success","bytes_scanned":38618648}
{"cycle_id":"79da2ac22e5c","trigger":"interval_refresh","status":"success","bytes_scanned":38618648}
```

---

## 4. `/agents/control` Schema Stability

Endpoint:

- `GET http://127.0.0.1:18011/agents/control`

Observed top-level keys:

- `agents`
- `count`
- `system_status`

Observed agent card keys remained in established contract set (including):

- identity/control truth fields: `family_id`, `installed`, `routing_enabled`, `integration_truth`, `route_truth`, `traffic_truth`
- metrics fields: `requests_24h`, `saved_tokens_24h`, `savings_ratio_24h`, `observed_requests_24h`
- observability fields: `observed_client_truth`, `truth_message`, `last_request_at`, `scope_note`

No schema expansion/regression was observed in this validation.

---

## 5. Load Sampling (120x, timeout=4s)

Method:

- 120 sequential `GET /agents/control` calls
- timeout per request: 4s
- sample adapter process CPU/RSS by `ps -p <pid> -o %cpu=,rss=`

Results:

- sample size: `120`
- timeout ratio: `0.00%` (0/120)
- error ratio: `0.00%` (0/120)
- latency:
  - `p50=8.95ms`
  - `p95=1978.87ms`
  - `max=2445.15ms`
  - `mean=174.61ms`
- adapter CPU:
  - `mean=18.38%`
  - `p95=89.30%`
  - `max=92.50%`
- adapter RSS:
  - `mean=504401.20 KB`
  - `p95=505632.00 KB`
  - `max=511008 KB`

Interpretation:

- timeout tail did not regress (no timeout observed)
- request path remained responsive under maintenance-enabled runtime
- CPU p95 residual is still visible under burst sampling; this batch does not claim full backend performance closure

---

## 6. Fresh/Stale/Fallback Path Verification

Manual path checks were executed against runtime summary file (temporary mutation, then restored):

1. stale-usable summary (`generated_at = now - 120s`, with TTL=30s and stale window default 3600s):
   - `/agents/control` -> HTTP 200, `count=3`
2. stale-unusable summary (`generated_at = now - 7200s`):
   - `/agents/control` -> HTTP 200, `count=3` (legacy fallback path usable)
3. summary missing (temporary rename):
   - `/agents/control` -> HTTP 200, `count=3` (legacy fallback path usable)

Summary file content was restored after verification.

---

## 7. Validation Conclusion

DLP Batch 1/2 behavior is validated in running reality for non-destructive maintenance:

- scheduler cycles are observable in ledger
- summary and ledger are traceable on running host
- `/agents/control` schema remains stable
- stale summary and legacy fallback both remain serviceable
- maintenance plane does not block request path

Destructive maintenance remains explicitly deferred to later gated batches.
